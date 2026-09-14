#!/usr/bin/env python3
"""Fixed, fail-closed T480 adapter for the repository H5 controller."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
from html import unescape
import json
import os
from pathlib import Path
import re
import shutil
import stat
import time
import subprocess
import sys
import time
from typing import Any, Callable, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from forex.plane_symphony import Controller, PlaneSymphonyError, load_canonical_task_catalog, load_config  # noqa: E402

DEFAULT_ENV_FILE = Path.home() / ".config" / "forex" / "symphony-h5.env"
STATE_DIR = Path.home() / ".local" / "state" / "forex-symphony-h5"
CACHE_DIR = Path.home() / ".cache" / "forex-symphony-h5"
REPOSITORY_DIR, WORKTREE_DIR = CACHE_DIR / "repository", CACHE_DIR / "worktrees"
USER_UNIT_DIR = Path.home() / ".config" / "systemd" / "user"
UNIT_NAME, UNIT_SOURCE = "forex-symphony-h5.service", ROOT / "t480" / "forex-symphony-h5.service"
AGENT = ROOT / "t480" / "plane_symphony_agent.py"
MIN_MEMORY_BYTES, MIN_C_DRIVE_BYTES, POLL_SECONDS = 4 * 1024**3, 15 * 1024**3, 30
_KEYS = frozenset({"FOREX_PLANE_URL", "FOREX_PLANE_API_TOKEN", "FOREX_PLANE_WORKSPACE", "FOREX_PLANE_PROJECT", "FOREX_SYMPHONY_BASELINE_REVISION"})
_IDENTIFIER, _REVISION = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z"), re.compile(r"[0-9a-f]{40}\Z")
_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z", re.I)
_SECRET = re.compile(r"(?:sk-|token|secret|password|authorization|api[_-]?key)", re.I)
BOARD_STATE_NAME = "plane-board.json"
BOARD_SCHEMA = "forex.plane-board.v1"
WORK_ITEM_STATE_NAME = "plane-work-items.json"
WORK_ITEM_SCHEMA = "forex.plane-work-items.v1"
BOARD_NAME, BOARD_IDENTIFIER = "Forex Delivery", "FXD"
BOARD_SOURCE, BOARD_EXTERNAL_ID = "forex-h5", "forex-delivery-v1"
# Chris explicitly approved the existing public Plane board.  Plane receives
# only redacted delivery metadata; it remains non-authoritative.
BOARD_NETWORK = 2
DEPLOYABLE_H5_PATHS = (
    "scripts/plane_symphony_t480.py",
    "src/forex/plane_symphony.py",
    "t480/plane_symphony_agent.py",
    "t480/forex-symphony-h5.service",
    "config/plane_symphony.json",
    "docs/milestones/active-delivery-tasks.json",
    "docs/plans/harness-h5-production-orchestration.md",
)
REQUIRED_STATES = {
    "Ready": {"group": "unstarted", "color": "#6B7280"},
    "In progress": {"group": "started", "color": "#3B82F6"},
    "Review": {"group": "started", "color": "#8B5CF6"},
    "Blocked": {"group": "started", "color": "#EF4444"},
    "Done": {"group": "completed", "color": "#22C55E"},
}


class H5RuntimeError(RuntimeError): pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        raise H5RuntimeError("Plane endpoint redirected; refusing credential forwarding")


def redact(value: Any) -> Any:
    if isinstance(value, Mapping): return {str(k): "[REDACTED]" if _SECRET.search(str(k)) else redact(v) for k, v in value.items()}
    if isinstance(value, list): return [redact(v) for v in value]
    return "[REDACTED]" if isinstance(value, str) and _SECRET.search(value) else value


def plain_plane_description(value: Any) -> str:
    """Accept only Plane's harmless plain-text or bare-paragraph serialization."""
    if not isinstance(value, str): return ""
    if "<" not in value and ">" not in value:
        return re.sub(r"\s+", " ", unescape(value)).strip()
    match = re.fullmatch(r"<p>([^<>]*)</p>", value)
    if match:
        return re.sub(r"\s+", " ", unescape(match.group(1))).strip()
    # Return the original non-canonical form so controller comparison repairs it.
    return value


def validate_plane_settings(settings: Mapping[str, str]) -> None:
    normalized_plane_origin(settings["FOREX_PLANE_URL"])
    if any(not _IDENTIFIER.fullmatch(settings[k]) for k in ("FOREX_PLANE_WORKSPACE", "FOREX_PLANE_PROJECT")): raise H5RuntimeError("Plane identifiers are unsafe")
    if not _REVISION.fullmatch(settings["FOREX_SYMPHONY_BASELINE_REVISION"]): raise H5RuntimeError("baseline revision must be exact 40-character Git SHA")
    if not 1 <= len(settings["FOREX_PLANE_API_TOKEN"]) <= 1024: raise H5RuntimeError("Plane token length is invalid")


def normalized_plane_origin(value: str) -> str:
    """Return the one canonical origin to which the protected board state binds."""
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc: raise H5RuntimeError("Plane URL must be a plain http(s) origin") from exc
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.path not in {"", "/"}):
        raise H5RuntimeError("Plane URL must be a plain http(s) origin")
    host = parsed.hostname.lower()
    default_port = (parsed.scheme == "http" and port == 80) or (parsed.scheme == "https" and port == 443)
    return f"{parsed.scheme.lower()}://{host}" + (f":{port}" if port is not None and not default_port else "")


def load_local_env(path: Path = DEFAULT_ENV_FILE) -> dict[str, str]:
    try: info = path.stat()
    except FileNotFoundError as exc: raise H5RuntimeError("local Plane environment file is missing") from exc
    if path.is_symlink() or not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600: raise H5RuntimeError("local Plane environment file must be owner-only mode 0600")
    values: dict[str, str] = {}
    for source in path.read_text(encoding="utf-8").splitlines():
        row = source.strip()
        if not row or row.startswith("#"): continue
        if "=" not in row: raise H5RuntimeError("local Plane environment contains invalid line")
        key, value = row.split("=", 1)
        if key not in _KEYS or key in values or not value.strip(): raise H5RuntimeError("local Plane environment contains unsupported setting")
        values[key] = value.strip()
    if set(values) != _KEYS: raise H5RuntimeError("local Plane environment must contain exactly the fixed H5 settings")
    validate_plane_settings(values); return values


def board_state_path(state_dir: Path | None = None) -> Path:
    return (state_dir or STATE_DIR) / BOARD_STATE_NAME


def _require_private_regular_file(path: Path, *, label: str) -> None:
    if path.is_symlink(): raise H5RuntimeError(f"{label} must not be symlink")
    try: info = path.stat()
    except FileNotFoundError as exc: raise H5RuntimeError(f"{label} is missing") from exc
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
        raise H5RuntimeError(f"{label} must be owner-only mode 0600")


def _require_private_directory(path: Path, *, create: bool) -> None:
    if create:
        try: path.mkdir(mode=0o700, parents=True, exist_ok=True)
        except OSError as exc: raise H5RuntimeError("Plane board state directory cannot be created") from exc
    try: info = path.lstat()
    except FileNotFoundError as exc: raise H5RuntimeError("Plane board state directory is missing") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise H5RuntimeError("Plane board state directory must be owner-only mode 0700")


def load_board_state(settings: Mapping[str, str], state_dir: Path | None = None) -> dict[str, str]:
    """Load the non-secret, locally pinned board identity used by work-item calls."""
    directory = state_dir or STATE_DIR
    _require_private_directory(directory, create=False)
    path = board_state_path(directory)
    _require_private_regular_file(path, label="Plane board state file")
    try: value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc: raise H5RuntimeError("Plane board state file is invalid") from exc
    required = {"schema_version", "plane_origin", "workspace_slug", "project_id", "project_name", "project_identifier", "external_source", "external_id"}
    if not isinstance(value, dict) or set(value) != required or any(not isinstance(value.get(k), str) for k in required):
        raise H5RuntimeError("Plane board state has unexpected shape")
    if (value["schema_version"] != BOARD_SCHEMA or value["plane_origin"] != normalized_plane_origin(settings["FOREX_PLANE_URL"])
            or value["workspace_slug"] != settings["FOREX_PLANE_WORKSPACE"]):
        raise H5RuntimeError("Plane board state does not match local configuration")
    if (value["project_name"], value["project_identifier"], value["external_source"], value["external_id"]) != (BOARD_NAME, BOARD_IDENTIFIER, BOARD_SOURCE, BOARD_EXTERNAL_ID):
        raise H5RuntimeError("Plane board state has an unexpected board identity")
    if not _UUID.fullmatch(value["project_id"]): raise H5RuntimeError("Plane board state has unsafe project ID")
    return {k: value[k] for k in required}


def write_board_state(settings: Mapping[str, str], project_id: str, state_dir: Path | None = None) -> dict[str, str]:
    if not _UUID.fullmatch(project_id): raise H5RuntimeError("Plane returned unsafe project ID")
    directory = state_dir or STATE_DIR
    _require_private_directory(directory, create=True)
    target = board_state_path(directory)
    if target.is_symlink(): raise H5RuntimeError("Plane board state target must not be symlink")
    if target.exists(): _require_private_regular_file(target, label="Plane board state target")
    state = {
        "schema_version": BOARD_SCHEMA, "plane_origin": normalized_plane_origin(settings["FOREX_PLANE_URL"]),
        "workspace_slug": settings["FOREX_PLANE_WORKSPACE"], "project_id": project_id,
        "project_name": BOARD_NAME, "project_identifier": BOARD_IDENTIFIER,
        "external_source": BOARD_SOURCE, "external_id": BOARD_EXTERNAL_ID,
    }
    temporary = target.with_name(target.name + ".tmp")
    if temporary.is_symlink() or temporary.exists(): raise H5RuntimeError("Plane board state temporary target already exists")
    try:
        nofollow = getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | nofollow, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(state, handle, sort_keys=True, separators=(",", ":")); handle.write("\n")
        os.chmod(temporary, 0o600); os.replace(temporary, target)
    finally:
        if temporary.exists(): temporary.unlink()
    return state


class WorkItemIdentityStore:
    """Owner-only binding of the two canonical task IDs to Plane UUIDs."""
    def __init__(self, project_id: str, state_dir: Path):
        if not _UUID.fullmatch(project_id): raise H5RuntimeError("unsafe Plane project ID")
        self.project_id, self.state_dir = project_id, state_dir

    @property
    def path(self) -> Path: return self.state_dir / WORK_ITEM_STATE_NAME

    def read(self) -> dict[str, str]:
        if not self.path.exists(): return {}
        _require_private_regular_file(self.path, label="Plane work-item state file")
        try: value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc: raise H5RuntimeError("Plane work-item state is invalid") from exc
        if not isinstance(value, dict) or set(value) != {"schema_version", "project_id", "items"} or value.get("schema_version") != WORK_ITEM_SCHEMA or value.get("project_id") != self.project_id:
            raise H5RuntimeError("Plane work-item state does not match board identity")
        items = value.get("items")
        if not isinstance(items, dict) or any(key not in {"FOREX:H5", "FOREX:A1"} or not isinstance(item_id, str) or not _UUID.fullmatch(item_id) for key, item_id in items.items()):
            raise H5RuntimeError("Plane work-item state has unsafe task identity")
        return dict(items)

    def bind(self, external_id: str, issue_id: str) -> None:
        if external_id not in {"FOREX:H5", "FOREX:A1"} or not _UUID.fullmatch(issue_id): raise H5RuntimeError("unsafe Plane work-item identity")
        _require_private_directory(self.state_dir, create=True)
        items = self.read()
        if external_id in items and items[external_id] != issue_id: raise H5RuntimeError("Plane work-item identity changed")
        if items.get(external_id) == issue_id: return
        items[external_id] = issue_id
        temporary = self.path.with_name(self.path.name + ".tmp")
        if temporary.exists() or temporary.is_symlink(): raise H5RuntimeError("Plane work-item temporary state already exists")
        try:
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump({"schema_version": WORK_ITEM_SCHEMA, "project_id": self.project_id, "items": items}, handle, sort_keys=True, separators=(",", ":")); handle.write("\n")
            os.chmod(temporary, 0o600); os.replace(temporary, self.path)
        finally:
            if temporary.exists(): temporary.unlink()


class PlaneBoardBootstrap:
    """Small, idempotent administrator path for the one H5 Plane board.

    Plane is a scheduling display only.  This class never receives task evidence,
    credentials other than the request header, or agent output.
    """
    def __init__(self, settings: Mapping[str, str], opener: Callable[..., Any] | None = None, state_dir: Path | None = None):
        self.settings, self.opener, self.state_dir = dict(settings), opener or build_opener(_NoRedirect()).open, state_dir

    def _url(self, suffix: str) -> str:
        return f"{self.settings['FOREX_PLANE_URL'].rstrip('/')}/api/v1{suffix}"

    def _request(self, method: str, url: str, body: Mapping[str, Any] | None = None) -> Any:
        raw = json.dumps(dict(body), sort_keys=True, separators=(",", ":")).encode() if body is not None else None
        request = Request(url, data=raw, method=method, headers={"X-API-Key": self.settings["FOREX_PLANE_API_TOKEN"], "Accept": "application/json", **({"Content-Type": "application/json"} if raw else {})})
        try:
            with self.opener(request, timeout=10) as response: status, payload = response.getcode(), response.read()
        except (HTTPError, URLError, OSError, H5RuntimeError) as exc: raise H5RuntimeError("Plane board request failed") from exc
        if status not in {200, 201}: raise H5RuntimeError("Plane board request returned unexpected status")
        try: return json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc: raise H5RuntimeError("Plane board returned invalid JSON") from exc

    def _paged(self, url: str, label: str) -> list[dict[str, Any]]:
        cursor, records = "", []
        while True:
            suffix = "?per_page=100" + ("&cursor=" + quote(cursor, safe=":") if cursor else "")
            payload = self._request("GET", url + suffix)
            page = payload.get("results") if isinstance(payload, dict) else None
            if not isinstance(page, list) or not all(isinstance(record, dict) for record in page):
                raise H5RuntimeError(f"Plane {label} response has unexpected shape")
            records.extend(page)
            if not payload.get("next_page_results"): return records
            cursor = payload.get("next_cursor")
            if not isinstance(cursor, str) or not cursor: raise H5RuntimeError(f"Plane {label} pagination cursor is invalid")

    def projects_url(self) -> str:
        return self._url(f"/workspaces/{quote(self.settings['FOREX_PLANE_WORKSPACE'], safe='')}/projects/")

    def states_url(self, project_id: str) -> str:
        if not _UUID.fullmatch(project_id): raise H5RuntimeError("unsafe Plane project ID")
        return self.projects_url() + quote(project_id, safe="") + "/states/"

    @classmethod
    def _is_managed_board(cls, project: Mapping[str, Any]) -> bool:
        return (project.get("name") == BOARD_NAME and project.get("identifier") == BOARD_IDENTIFIER
                and project.get("external_source") == BOARD_SOURCE and project.get("external_id") == BOARD_EXTERNAL_ID
                and project.get("network") == BOARD_NETWORK)

    def discover(self) -> dict[str, Any]:
        # Plane's public API exposes workspace-scoped projects, not a general
        # workspace-detail resource. In v1.4.2 ProjectBasePermission requires
        # active membership in the requested workspace even for an empty list.
        # A successful authenticated collection read verifies that access;
        # HTTP denial or a malformed collection still fails closed in _paged.
        projects = self._paged(self.projects_url(), "projects")
        return {"endpoint": "v1-workspace-projects", "status": "PASS", "workspace": self.settings["FOREX_PLANE_WORKSPACE"], "project_count": len(projects), "projects": projects}

    def _resolve_project(self, projects: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any] | None, bool]:
        managed = [dict(project) for project in projects if self._is_managed_board(project)]
        conflicts = [project for project in projects if project.get("name") == BOARD_NAME or project.get("identifier") == BOARD_IDENTIFIER]
        if len(managed) > 1: raise H5RuntimeError("multiple managed Forex Delivery projects found")
        if managed:
            if len(conflicts) != 1: raise H5RuntimeError("conflicting Forex Delivery project identity")
            project_id = managed[0].get("id")
            if not isinstance(project_id, str) or not _UUID.fullmatch(project_id): raise H5RuntimeError("managed Forex Delivery project has unsafe ID")
            return managed[0], False
        if conflicts: raise H5RuntimeError("conflicting Forex Delivery project already exists")
        return None, True

    def _create_project(self) -> dict[str, Any]:
        project = self._request("POST", self.projects_url(), {
            "name": BOARD_NAME, "identifier": BOARD_IDENTIFIER,
            "external_source": BOARD_SOURCE, "external_id": BOARD_EXTERNAL_ID,
            "network": BOARD_NETWORK,
        })
        if not isinstance(project, dict) or not self._is_managed_board(project):
            raise H5RuntimeError("Plane did not create the fixed approved Forex Delivery project")
        project_id = project.get("id")
        if not isinstance(project_id, str) or not _UUID.fullmatch(project_id): raise H5RuntimeError("Plane did not return a safe project ID")
        return project

    def _ensure_states(self, project_id: str) -> dict[str, str]:
        states = self._paged(self.states_url(project_id), "states")
        result: dict[str, str] = {}
        for name, specification in REQUIRED_STATES.items():
            group, color = specification["group"], specification["color"]
            matches = [state for state in states if state.get("name") == name]
            if len(matches) > 1: raise H5RuntimeError(f"Plane state {name!r} is ambiguous")
            if matches:
                state = matches[0]
                # Existing Plane defaults may have different display colors.
                # Name and group define H5 scheduling semantics, not cosmetics.
                if state.get("group") != group:
                    raise H5RuntimeError(f"Plane state {name!r} has wrong group")
            else:
                state = self._request("POST", self.states_url(project_id), {"name": name, "group": group, "color": color})
                if not isinstance(state, dict) or state.get("name") != name or state.get("group") != group or state.get("color") != color:
                    raise H5RuntimeError(f"Plane did not create required state {name!r}")
            state_id = state.get("id")
            if not isinstance(state_id, str) or not _UUID.fullmatch(state_id): raise H5RuntimeError(f"Plane state {name!r} has unsafe ID")
            result[name] = state_id
        return result

    def _verify_states(self, project_id: str) -> dict[str, str]:
        states = self._paged(self.states_url(project_id), "states")
        result: dict[str, str] = {}
        for name, specification in REQUIRED_STATES.items():
            matches = [state for state in states if state.get("name") == name]
            if len(matches) != 1 or matches[0].get("group") != specification["group"]:
                raise H5RuntimeError("Plane required state identity mismatch")
            state_id = matches[0].get("id")
            if not isinstance(state_id, str) or not _UUID.fullmatch(state_id): raise H5RuntimeError("Plane required state has unsafe ID")
            result[name] = state_id
        return result

    def verify_existing(self) -> dict[str, Any]:
        """Read-only worker gate: never rebind a retained board UUID."""
        retained = load_board_state(self.settings, self.state_dir)
        discovery = self.discover()
        project, create = self._resolve_project(discovery["projects"])
        if create or project is None or project.get("id") != retained["project_id"]:
            raise H5RuntimeError("Plane retained board identity mismatch")
        states = self._verify_states(retained["project_id"])
        return {"status": "PASS", "project_id": retained["project_id"], "states": sorted(states)}

    def ensure(self) -> dict[str, Any]:
        discovery = self.discover()
        project, create = self._resolve_project(discovery["projects"])
        if create: project = self._create_project()
        assert project is not None  # narrow internal invariant after resolve/create
        project_id = project["id"]
        states = self._ensure_states(project_id)
        state = write_board_state(self.settings, project_id, self.state_dir)
        return {"status": "PASS", "project": {"id": project_id, "name": BOARD_NAME, "identifier": BOARD_IDENTIFIER}, "states": sorted(states), "state_file": str(board_state_path(self.state_dir)), "created_project": create, "board_state": {k: v for k, v in state.items() if k != "project_id"}}


class PlaneWorkItemsV1:
    """Narrow Plane v1 client; no evidence, credentials, or run output is sent."""
    def __init__(self, settings: Mapping[str, str], opener: Callable[..., Any] | None = None, project_id: str | None = None, state_dir: Path | None = None):
        self.settings, self.opener = dict(settings), opener or build_opener(_NoRedirect()).open
        # Direct construction remains useful for narrow probe tests.  Runtime
        # scheduling always passes the protected, discovered immutable UUID.
        self.project_id = project_id or self.settings["FOREX_PLANE_PROJECT"]
        if not _UUID.fullmatch(self.project_id): raise H5RuntimeError("unsafe Plane project ID")
        self.identities = WorkItemIdentityStore(self.project_id, state_dir) if state_dir is not None else None
    def work_items_url(self) -> str:
        return f"{self.settings['FOREX_PLANE_URL'].rstrip('/')}/api/v1/workspaces/{quote(self.settings['FOREX_PLANE_WORKSPACE'], safe='')}/projects/{quote(self.project_id, safe='')}/work-items/"
    def _request(self, method: str, url: str, body: dict[str, Any] | None = None) -> Any:
        raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode() if body is not None else None
        request = Request(url, data=raw, method=method, headers={"X-API-Key": self.settings["FOREX_PLANE_API_TOKEN"], "Accept": "application/json", **({"Content-Type": "application/json"} if raw else {})})
        try:
            with self.opener(request, timeout=10) as response: status, payload = response.getcode(), response.read()
        except (HTTPError, URLError, OSError, H5RuntimeError) as exc: raise H5RuntimeError("Plane request failed") from exc
        if status not in {200, 201}: raise H5RuntimeError("Plane request returned unexpected status")
        try: return json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc: raise H5RuntimeError("Plane returned invalid JSON") from exc
    def _items(self) -> list[dict[str, Any]]:
        cursor, items = "", []
        while True:
            suffix = "?expand=state&per_page=100" + ("&cursor=" + quote(cursor, safe=":") if cursor else "")
            payload = self._request("GET", self.work_items_url() + suffix); page = payload.get("results") if isinstance(payload, dict) else None
            if not isinstance(page, list) or not all(isinstance(x, dict) for x in page): raise H5RuntimeError("Plane work-items response has unexpected shape")
            items.extend(page)
            if not payload.get("next_page_results"): return items
            cursor = payload.get("next_cursor")
            if not isinstance(cursor, str) or not cursor: raise H5RuntimeError("Plane pagination cursor is invalid")
    def probe(self) -> dict[str, Any]: return {"endpoint": "v1-work-items", "status": "PASS", "item_count": len(self._items())}
    def find_issue(self, external_id: str, expected_name: str) -> dict[str, Any] | None:
        if external_id not in {"FOREX:H5", "FOREX:A1"}: raise H5RuntimeError("unsafe Plane external task identity")
        if not isinstance(expected_name, str) or not expected_name.startswith(f"[{external_id}] ") or _SECRET.search(expected_name):
            raise H5RuntimeError("unsafe Plane work-item name")
        items = self._items()
        matches = [item for item in items if isinstance(item.get("name"), str) and item["name"] == expected_name]
        mapped_id = self.identities.read().get(external_id) if self.identities else None
        if mapped_id:
            mapped = [item for item in items if item.get("id") == mapped_id]
            if len(mapped) != 1 or mapped[0].get("name") != expected_name or len(matches) != 1:
                raise H5RuntimeError("Plane work-item identity mismatch")
            item = mapped[0]
        else:
            if len(matches) > 1: raise H5RuntimeError("Plane work-item identity is ambiguous")
            if not matches: return None
            item = matches[0]
            issue_id = item.get("id")
            if not isinstance(issue_id, str) or not _UUID.fullmatch(issue_id): raise H5RuntimeError("Plane work-item has unsafe ID")
            if self.identities: self.identities.bind(external_id, issue_id)
        state = item.get("state")
        if isinstance(state, dict): state = state.get("name")
        if not isinstance(state, str): state = None
        return {"id": item.get("id"), "name": item["name"], "state": state,
                "description": plain_plane_description(item.get("description_html", ""))}
    def _state_id(self, state_name: str) -> str:
        base = self.work_items_url().rsplit("/work-items/", 1)[0]
        payload = self._request("GET", base + "/states/"); states = payload.get("results") if isinstance(payload, dict) else None
        if not isinstance(states, list): raise H5RuntimeError("Plane states response has unexpected shape")
        for state in states:
            if isinstance(state, dict) and state.get("name") == state_name and isinstance(state.get("id"), str): return state["id"]
        raise H5RuntimeError("required Plane state is absent")
    def _body(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        if set(payload) != {"external_id", "name", "state", "description"} or any(not isinstance(payload[k], str) for k in payload) or _SECRET.search(payload["name"]) or _SECRET.search(payload["description"]): raise H5RuntimeError("unsafe Plane payload")
        return {"name": payload["name"], "description_html": payload["description"], "state": self._state_id(payload["state"])}
    def create_issue(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = self._request("POST", self.work_items_url(), self._body(payload))
        if not isinstance(result, dict) or not isinstance(result.get("id"), str): raise H5RuntimeError("Plane did not return work-item ID")
        if self.identities: self.identities.bind(payload["external_id"], result["id"])
        return {"id": result["id"], **payload}
    def update_issue(self, issue_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not _IDENTIFIER.fullmatch(issue_id): raise H5RuntimeError("unsafe Plane work-item ID")
        if self.identities and self.identities.read().get(payload["external_id"]) != issue_id: raise H5RuntimeError("Plane work-item update identity mismatch")
        result = self._request("PATCH", self.work_items_url() + quote(issue_id, safe="") + "/", self._body(payload))
        if not isinstance(result, dict) or not isinstance(result.get("id"), str): raise H5RuntimeError("Plane did not return work-item ID")
        return {"id": result["id"], **payload}


def _wait_for_socket(path: Path, timeout_seconds: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if path.is_socket() and not path.is_symlink(): return True
        time.sleep(0.05)
    return False


class CodexAppServerRunner:
    def __init__(self, *, baseline_revision: str, run: Callable[..., Any] = subprocess.run,
                 wait_for_socket: Callable[[Path], bool] = _wait_for_socket):
        self.baseline_revision, self.run, self.wait_for_socket = baseline_revision, run, wait_for_socket
    def preflight(self, *, task_id: str, commands: tuple[str, ...], baseline_revision: str, configuration_fingerprint: str) -> dict[str, Any]:
        if baseline_revision != self.baseline_revision or commands not in {("plane_symphony_preflight",), ("a1_retention_preflight",)}: raise H5RuntimeError("undeclared task preflight")
        checks: tuple[tuple[str, ...], ...]
        if commands == ("plane_symphony_preflight",):
            checks = (("git", "-C", str(REPOSITORY_DIR), "diff", "--quiet"), ("codex", "login", "status"), ("codex", "app-server", "--help"))
        else:
            # This remains a named, fixed A1 check—not a task-supplied shell command.
            checks = ((sys.executable, str(ROOT / "scripts" / "a1_t480_deploy.py"), "inspect"),)
        for check in checks: self._run(check)
        receipt = {"task_id": task_id, "commands": list(commands), "baseline_revision": baseline_revision, "configuration_fingerprint": configuration_fingerprint, "status": "PASS", "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), "content": {"checks": list(commands)}}
        receipt["receipt_sha256"] = sha256(json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()).hexdigest(); return receipt
    def _run(self, args: Sequence[str], cwd: Path | None = None) -> None:
        result = self.run(list(args), cwd=cwd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode: raise H5RuntimeError("fixed Git/systemd worker operation failed")
    def start(self, *, task_id: str, worktree: Path, prompt: str, limits: dict[str, int], idempotency_key: str) -> str:
        if limits != {"cpu": 1, "memory_mib": 1536, "pids": 128} or not re.fullmatch(r"[0-9a-f]{32}", idempotency_key) or worktree.exists(): raise H5RuntimeError("duplicate worker or invalid worker limits")
        worktree.parent.mkdir(mode=0o700, parents=True, exist_ok=True); self._run(("git", "-C", str(REPOSITORY_DIR), "worktree", "add", "--detach", str(worktree), self.baseline_revision))
        runs = STATE_DIR / "runs"; runs.mkdir(mode=0o700, parents=True, exist_ok=True)
        run_dir = runs / idempotency_key
        run_dir.mkdir(mode=0o700)
        os.chmod(run_dir, 0o700)
        # The App Server host needs only the per-run protocol socket.  Keep
        # worker prompt/status state outside that mount so the host cannot read
        # or alter it merely because it supplies the Codex transport.
        ipc_dir = run_dir / "ipc"
        ipc_dir.mkdir(mode=0o700)
        os.chmod(ipc_dir, 0o700)
        prompt_path, status_path = run_dir / "prompt.txt", run_dir / "status.json"
        prompt_path.write_text(prompt, encoding="utf-8"); os.chmod(prompt_path, 0o600)
        home, codex_home = Path.home(), Path.home() / ".codex"
        codex_bin, codex_install = home / ".local" / "bin" / "codex", home / ".local" / "opt" / "forex-codex"
        socket_path = ipc_dir / "app-server.sock"
        worker_env = (f"HOME={home}", "LANG=C.UTF-8", "LC_ALL=C.UTF-8",
                      f"PATH={home}/.local/bin:/usr/local/bin:/usr/bin:/bin")
        # The host is the only process with OpenAI transport egress. Its Codex
        # workspace-write tool sandbox is explicitly network-denied; this is a
        # per-run CLI override, never a mutable user-global Codex setting.
        # The worker remains in a network namespace and can only proxy App
        # Server protocol bytes over this per-run Unix socket.
        host_unit = f"forex-symphony-h5-host-{idempotency_key}"
        self._run(("systemd-run", "--user", "--unit", host_unit, "--collect",
                   "--property=RuntimeMaxSec=1800",
                   "--property=NoNewPrivileges=yes", "--property=PrivateTmp=yes", "--property=ProtectHome=tmpfs",
                   f"--property=BindReadOnlyPaths={codex_bin} {codex_install} {codex_home}",
                   f"--property=BindPaths={worktree} {ipc_dir}", f"--property=ReadWritePaths={worktree} {ipc_dir}",
                   "/usr/bin/env", "-i", *worker_env, "codex", "app-server",
                   "--config", "sandbox_workspace_write.network_access=false",
                   "--listen", f"unix://{socket_path}"))
        if not self.wait_for_socket(socket_path):
            self._run(("systemctl", "--user", "stop", host_unit))
            raise H5RuntimeError("Codex App Server host socket was not ready")
        try:
            self._run(("systemd-run", "--user", "--unit", f"forex-symphony-h5-{idempotency_key}", "--collect",
                   "--property=CPUQuota=100%", "--property=MemoryMax=1536M", "--property=TasksMax=128",
                   "--property=RuntimeMaxSec=1800",
                   "--property=NoNewPrivileges=yes", "--property=PrivateTmp=yes", "--property=PrivateNetwork=yes",
                   "--property=ProtectHome=tmpfs", f"--property=BindReadOnlyPaths={AGENT} {codex_bin} {codex_install}",
                   f"--property=BindPaths={worktree} {run_dir}", f"--property=ReadWritePaths={worktree} {run_dir}",
                   "/usr/bin/env", "-i", *worker_env, sys.executable, str(AGENT), "--worktree", str(worktree),
                   "--prompt-file", str(prompt_path), "--status-file", str(status_path), "--run-id", idempotency_key,
                   "--app-server-socket", str(socket_path)))
        except Exception:
            self._run(("systemctl", "--user", "stop", host_unit))
            raise
        return idempotency_key
    def inspect(self, *, task_id: str, idempotency_key: str, agent_run_id: str | None) -> dict[str, Any]:
        path = STATE_DIR / "runs" / idempotency_key / "status.json"
        unit = f"forex-symphony-h5-{idempotency_key}.service"
        active = self.run(["systemctl", "--user", "is-active", unit], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        unit_state = active.stdout.strip()
        if unit_state in {"active", "activating", "reloading", "deactivating"}: is_active = True
        elif unit_state in {"inactive", "failed"}: is_active = False
        else: raise H5RuntimeError("worker lifecycle cannot be inspected")
        if not path.is_file():
            if is_active: return {"task_id": task_id, "idempotency_key": idempotency_key, "agent_run_id": agent_run_id, "status": "RUNNING"}
            return {"task_id": task_id, "idempotency_key": idempotency_key, "agent_run_id": agent_run_id, "status": "NOT_STARTED"}
        try: record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc: raise H5RuntimeError("invalid worker status record") from exc
        status = record.get("status")
        if status not in {"RUNNING", "COMPLETED", "FAILED"}: raise H5RuntimeError("invalid worker lifecycle state")
        if status == "RUNNING" and not is_active: status = "FAILED"
        return {"task_id": task_id, "idempotency_key": idempotency_key, "agent_run_id": agent_run_id, "status": status}


class RuntimeAdapter:
    def __init__(self, *, run: Callable[..., Any] = subprocess.run, disk_usage: Callable[[str], Any] = shutil.disk_usage, meminfo_path: Path = Path("/proc/meminfo"), env_file: Path = DEFAULT_ENV_FILE, opener: Callable[..., Any] | None = None): self.run, self.disk_usage, self.meminfo_path, self.env_file, self.opener = run, disk_usage, meminfo_path, env_file, opener
    def _command(self, args: Sequence[str]) -> None:
        try: result = self.run(list(args), check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        except OSError as exc: raise H5RuntimeError(f"required command unavailable: {args[0]}") from exc
        if result.returncode: raise H5RuntimeError(f"required command failed: {args[0]}")
    def _memory_available(self) -> int:
        try: return int(dict(x.split(":", 1) for x in self.meminfo_path.read_text().splitlines() if ":" in x)["MemAvailable"].strip().split()[0]) * 1024
        except (OSError, KeyError, ValueError) as exc: raise H5RuntimeError("available-memory measurement unavailable") from exc
    def clean_baseline(self, expected: str) -> str:
        status = self.run(["git", "status", "--porcelain=v1"], cwd=ROOT, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True); revision = self.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if status.returncode or revision.returncode: raise H5RuntimeError("Git baseline cannot be inspected")
        if status.stdout.strip(): raise H5RuntimeError("Git baseline is dirty; refusing write-capable work")
        if revision.stdout.strip() != expected: raise H5RuntimeError("Git baseline does not match the human-approved revision")
        return expected

    def require_deployable_baseline(self, revision: str) -> None:
        """Refuse a clean SHA that cannot actually run the fixed H5 package."""
        for relative_path in DEPLOYABLE_H5_PATHS:
            probe = self.run(["git", "cat-file", "-e", f"{revision}:{relative_path}"], cwd=ROOT,
                             check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if probe.returncode:
                raise H5RuntimeError("DEPLOYABLE_REVISION_REQUIRED")

    def _board_bootstrap(self, settings: Mapping[str, str]) -> PlaneBoardBootstrap:
        return PlaneBoardBootstrap(settings, self.opener, STATE_DIR)

    def _work_item_client(self, settings: Mapping[str, str]) -> PlaneWorkItemsV1:
        board = load_board_state(settings, STATE_DIR)
        return PlaneWorkItemsV1(settings, self.opener, project_id=board["project_id"], state_dir=STATE_DIR)

    def preflight(self) -> dict[str, Any]:
        settings = load_local_env(self.env_file)
        for command in (("systemctl", "--user", "show-environment"), ("git", "--version"), (sys.executable, "--version"), ("codex", "login", "status"), ("codex", "app-server", "--help")): self._command(command)
        memory, disk = self._memory_available(), self.disk_usage("/mnt/c").free
        if memory < MIN_MEMORY_BYTES: raise H5RuntimeError("T480 available memory is below H5 minimum")
        if disk < MIN_C_DRIVE_BYTES: raise H5RuntimeError("T480 Windows C: capacity is below H5 minimum")
        baseline = self.clean_baseline(settings["FOREX_SYMPHONY_BASELINE_REVISION"])
        self.require_deployable_baseline(baseline)
        discovery = self._board_bootstrap(settings).discover()
        board_status = "CONFIGURED" if board_state_path(STATE_DIR).is_file() else "CONFIGURATION_REQUIRED"
        return {"status": "PASS", "execution_authority": False,
                "plane": {k: v for k, v in discovery.items() if k != "projects"}, "board_bootstrap": board_status,
                "available_memory_bytes": memory, "windows_c_free_bytes": disk, "baseline_revision": baseline}
    def _clone_baseline(self, revision: str) -> None:
        CACHE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
        if not REPOSITORY_DIR.exists(): self._command(("git", "clone", "--no-hardlinks", "--no-checkout", str(ROOT), str(REPOSITORY_DIR)))
        self._command(("git", "-C", str(REPOSITORY_DIR), "checkout", "--detach", revision)); self._command(("git", "-C", str(REPOSITORY_DIR), "clean", "-ffd"))
    def install(self) -> dict[str, Any]:
        report = self.preflight()
        if not UNIT_SOURCE.is_file() or not AGENT.is_file(): raise H5RuntimeError("fixed H5 service package incomplete")
        settings = load_local_env(self.env_file)
        board = self._board_bootstrap(settings).ensure()
        self._clone_baseline(report["baseline_revision"])
        for path in (STATE_DIR, WORKTREE_DIR, USER_UNIT_DIR): path.mkdir(mode=0o700, parents=True, exist_ok=True); os.chmod(path, 0o700)
        target = USER_UNIT_DIR / UNIT_NAME
        if target.is_symlink(): raise H5RuntimeError("systemd unit target must not be symlink")
        shutil.copyfile(UNIT_SOURCE, target); os.chmod(target, 0o600); self._command(("systemctl", "--user", "daemon-reload")); return {"status": "INSTALLED", "unit": UNIT_NAME, "preflight": report, "board_bootstrap": board}
    def systemctl(self, action: str) -> dict[str, Any]:
        if action not in {"start", "stop", "status"}: raise H5RuntimeError("unsupported fixed systemd action")
        if action == "start":
            self.preflight()
            self._work_item_client(load_local_env(self.env_file))
        board_status = "NOT_CHECKED"
        if action == "status":
            try:
                self._work_item_client(load_local_env(self.env_file))
                board_status = "CONFIGURED"
            except H5RuntimeError:
                board_status = "CONFIGURATION_REQUIRED"
        self._command(("systemctl", "--user", action, UNIT_NAME)); return {"status": action.upper(), "unit": UNIT_NAME, "execution_authority": False, "board_bootstrap": board_status}
    def controller_once(self, operation: str) -> dict[str, Any]:
        if operation not in {"sync-once", "run-once"}: raise H5RuntimeError("unsupported fixed controller operation")
        # Display reconciliation has no worktree, lease, agent, external task
        # execution, or repository write.  It must not be coupled to the
        # deliberately stricter worker-capacity/Codex/clean-baseline preflight.
        settings = load_local_env(self.env_file)
        try:
            config, catalog = load_config(ROOT / "config" / "plane_symphony.json"), load_canonical_task_catalog(ROOT)
            tasks = catalog.snapshot()
            if operation == "sync-once":
                board = self._board_bootstrap(settings).ensure()
                client = self._work_item_client(settings)
                result = Controller(config, catalog, client).sync_once()
                return {"status": "CONTROLLER_COMPLETED", "operation": operation, "board_bootstrap": redact(board), "result": redact(result), "execution_authority": False}
            report = self.preflight()
            # A retained UUID alone is insufficient for worker selection. This
            # check is read-only and cannot silently adopt a replacement board.
            self._board_bootstrap(settings).verify_existing()
            client = self._work_item_client(settings)
            controller = Controller(config, catalog, client, CodexAppServerRunner(baseline_revision=report["baseline_revision"], run=self.run))
            controller.sync_once()
            plane_states = {k: (client.find_issue(f"FOREX:{k}", f"[FOREX:{k}] {tasks[k]['title']}") or {}).get("state") for k in ("H5", "A1")}
            result = controller.run_once(plane_states, baseline_revision=report["baseline_revision"], clean_baseline=True)
        except PlaneSymphonyError as exc: raise H5RuntimeError("controller refused operation") from exc
        return {"status": "CONTROLLER_COMPLETED", "operation": operation, "result": redact(result), "execution_authority": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("operation", choices=("preflight", "install", "start", "stop", "status", "sync-once", "run-once")); parser.add_argument("--loop", action="store_true"); args = parser.parse_args(argv)
    if args.loop and args.operation != "run-once": parser.error("--loop only permitted with run-once")
    adapter = RuntimeAdapter()
    try:
        if args.operation == "preflight": report = adapter.preflight()
        elif args.operation == "install": report = adapter.install()
        elif args.operation in {"start", "stop", "status"}: report = adapter.systemctl(args.operation)
        elif args.loop:
            while True: print(json.dumps(redact(adapter.controller_once("run-once")), sort_keys=True), flush=True); time.sleep(POLL_SECONDS)
        else: report = adapter.controller_once(args.operation)
        print(json.dumps(redact(report), sort_keys=True)); return 0
    except H5RuntimeError as exc: print(f"FOREX_H5_T480_REFUSED: {exc}", file=sys.stderr); return 2


if __name__ == "__main__": raise SystemExit(main())
