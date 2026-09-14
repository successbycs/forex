"""Fail-closed, repository-governed scheduling for the H5 Plane board.

This module deliberately contains no HTTP or subprocess implementation.  A
deployment adapter supplies the small ``PlaneClient`` and ``AgentRunner``
interfaces after it has completed its own fixed T480 preflight.  Keeping those
side effects outside the scheduler makes the repository policy testable and
prevents a task record from becoming a generic command-execution surface.
"""
from __future__ import annotations

from dataclasses import dataclass
from contextlib import contextmanager
import copy
from datetime import datetime, timezone
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
from typing import Any, Protocol
from uuid import uuid4


SCHEMA_VERSION = "forex.plane-symphony.v1"
TASK_SOURCE = "docs/milestones/active-delivery-tasks.json"
ROLLOUT_TASK_IDS = ("H5", "A1")
PLANE_STATES = frozenset({"Ready", "In progress", "Review", "Blocked", "Done"})
TASK_STATE_MAP = {
    # Future repository work is visible on Plane but not selectable.  The
    # board has no separate Pending state, so render it as Blocked rather than
    # silently treating it as Ready.
    "PENDING": "Blocked",
    "READY": "Ready",
    "IN_PROGRESS": "In progress",
    "IN_REVIEW": "Review",
    "BLOCKED": "Blocked",
    "BLOCKED_EXTERNAL_PLANE": "Blocked",
    "BLOCKED_EXTERNAL_OBSERVATION": "Blocked",
    "COMPLETE_REVIEWED": "Done",
}
_TASK_ID = re.compile(r"^[A-Z][A-Z0-9_-]{0,63}$")
_OPERATION = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_FORBIDDEN = re.compile(r"(?:broker|mt5|gomarkets|live|trade|shell|command|exec)", re.IGNORECASE)
_SECRET_NAMES = re.compile(r"(?:token|secret|password|api[_-]?key|authorization)", re.IGNORECASE)
_FIXED_POLICY = {
    "H5": {"operations": frozenset({"plane_board_bootstrap", "symphony_service_install"}),
           "preflights": frozenset({"plane_symphony_preflight"})},
    "A1": {"operations": frozenset({"a1_retention_deploy"}),
           "preflights": frozenset({"a1_retention_preflight"})},
}
_ACTIVE_LEASE_STATES = frozenset({"RESERVED", "IN_PROGRESS", "RESUMABLE", "RUNNER_START_UNKNOWN"})
_TASK_TRANSITIONS = {
    "BLOCKED_EXTERNAL_PLANE": frozenset({"READY"}),
    "BLOCKED_EXTERNAL_OBSERVATION": frozenset({"READY"}),
    "BLOCKED_HUMAN_MIGRATION": frozenset({"READY"}),
    "READY": frozenset({"IN_REVIEW"}),
    "IN_REVIEW": frozenset({"COMPLETE_REVIEWED"}),
}


class PlaneSymphonyError(ValueError):
    """A controller input is unsafe or cannot be used deterministically."""


class PlaneClient(Protocol):
    """Minimal adapter boundary; implementations own Plane HTTP details."""

    def find_issue(self, external_id: str, expected_name: str) -> dict[str, Any] | None: ...
    def create_issue(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    def update_issue(self, issue_id: str, payload: dict[str, Any]) -> dict[str, Any]: ...


class AgentRunner(Protocol):
    """Minimal adapter boundary; implementations own Codex App Server calls."""

    def preflight(self, *, task_id: str, commands: tuple[str, ...], baseline_revision: str,
                  configuration_fingerprint: str) -> dict[str, Any]: ...
    def start(self, *, task_id: str, worktree: Path, prompt: str, limits: dict[str, int],
              idempotency_key: str) -> str: ...
    def inspect(self, *, task_id: str, idempotency_key: str, agent_run_id: str | None) -> dict[str, Any]: ...


@dataclass(frozen=True)
class ControllerConfig:
    state_dir: Path
    worktree_root: Path
    max_workers: int
    cpu_limit: int
    memory_mib: int
    pids_limit: int
    execution_authority: bool


@dataclass(frozen=True)
class CanonicalTaskCatalog:
    """Immutable serialized policy snapshot from the only production source."""
    serialized_tasks: bytes
    source_sha256: str

    def snapshot(self) -> dict[str, dict[str, Any]]:
        """Return a new mutable runtime copy; never expose canonical policy."""
        try:
            raw = json.loads(self.serialized_tasks, object_pairs_hook=_pairs)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PlaneSymphonyError("canonical task snapshot is invalid") from exc
        if not isinstance(raw, dict):
            raise PlaneSymphonyError("canonical task snapshot is invalid")
        return validate_task_catalog(raw)

    def task(self, task_id: str) -> dict[str, Any]:
        task = self.snapshot().get(task_id)
        if not isinstance(task, dict):
            raise PlaneSymphonyError("fixed operation task is unavailable")
        return task


def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise PlaneSymphonyError("duplicate JSON field")
        result[key] = value
    return result


def load_json(path: Path) -> dict[str, Any]:
    """Load a regular JSON file, rejecting duplicate fields and non-finite data."""
    if not isinstance(path, Path) or path.is_symlink() or not path.is_file():
        raise PlaneSymphonyError("JSON source must be a regular file")
    try:
        raw = json.loads(path.read_bytes(), object_pairs_hook=_pairs,
                         parse_constant=lambda _: (_ for _ in ()).throw(PlaneSymphonyError("nonfinite JSON")))
    except (OSError, json.JSONDecodeError) as exc:
        raise PlaneSymphonyError("JSON source is invalid") from exc
    if not isinstance(raw, dict):
        raise PlaneSymphonyError("JSON source must be an object")
    return raw


def load_canonical_task_catalog(root: Path) -> CanonicalTaskCatalog:
    """Load the fixed repository task source, never an arbitrary caller dict."""
    root = root.resolve()
    source = (root / TASK_SOURCE).resolve()
    if not source.is_relative_to(root):
        raise PlaneSymphonyError("canonical task source is unsafe")
    try:
        raw_bytes = source.read_bytes()
    except OSError as exc:
        raise PlaneSymphonyError("canonical task source is unavailable") from exc
    raw = load_json(source)
    validate_task_catalog(raw)
    return CanonicalTaskCatalog(raw_bytes, "sha256:" + sha256(raw_bytes).hexdigest())


def _test_catalog(raw: dict[str, Any]) -> CanonicalTaskCatalog:
    """Test-only constructor; production must use load_canonical_task_catalog."""
    validate_task_catalog(raw)
    return CanonicalTaskCatalog(json.dumps(raw, sort_keys=True, separators=(",", ":")).encode(), "sha256:" + _canonical_digest(raw))


def load_config(path: Path) -> ControllerConfig:
    """Load the pinned non-secret controller configuration."""
    raw = load_json(path)
    fields = {"schema_version", "task_source", "state_dir", "worktree_root", "max_workers",
              "cpu_limit", "memory_mib", "pids_limit", "execution_authority"}
    if set(raw) != fields or raw.get("schema_version") != SCHEMA_VERSION:
        raise PlaneSymphonyError("controller configuration schema is invalid")
    if raw.get("task_source") != TASK_SOURCE or raw.get("execution_authority") is not False:
        raise PlaneSymphonyError("controller authority boundary is invalid")
    for key in ("state_dir", "worktree_root"):
        if not isinstance(raw.get(key), str) or not raw[key] or Path(raw[key]).is_absolute() is False:
            raise PlaneSymphonyError("controller local directories must be absolute paths")
    values = ("max_workers", "cpu_limit", "memory_mib", "pids_limit")
    if any(type(raw.get(key)) is not int or raw[key] <= 0 for key in values):
        raise PlaneSymphonyError("controller resource limits are invalid")
    if raw["max_workers"] > 2 or raw["cpu_limit"] > 1 or raw["memory_mib"] > 1536 or raw["pids_limit"] > 128:
        raise PlaneSymphonyError("controller resource limits exceed the H5 bound")
    return ControllerConfig(Path(raw["state_dir"]), Path(raw["worktree_root"]), *(raw[key] for key in values), False)


def validate_task_catalog(raw: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return the H5/A1 scheduling subset after rejecting unsafe task policy."""
    catalog_fields = {"schema_version", "purpose", "active_sequence", "execution_authority", "tasks"}
    if (set(raw) != catalog_fields or raw.get("schema_version") != "forex.active-delivery-tasks.v2"
            or raw.get("execution_authority") is not False or not isinstance(raw.get("tasks"), list)):
        raise PlaneSymphonyError("task catalog schema is invalid")
    selected: dict[str, dict[str, Any]] = {}
    known: set[str] = set()
    for task in raw["tasks"]:
        if not isinstance(task, dict) or not isinstance(task.get("id"), str) or not _TASK_ID.fullmatch(task["id"]):
            raise PlaneSymphonyError("task ID is invalid")
        task_id = task["id"]
        if task_id in known:
            raise PlaneSymphonyError("task IDs must be unique")
        known.add(task_id)
        selected[task_id] = validate_task_policy(task) if task_id in ROLLOUT_TASK_IDS else task
    if not set(ROLLOUT_TASK_IDS).issubset(selected):
        raise PlaneSymphonyError("initial rollout requires exactly H5 and A1")
    return selected


def validate_task_policy(task: dict[str, Any]) -> dict[str, Any]:
    """Validate only the fixed, non-broker scheduling information for a task."""
    required = {"id", "title", "state", "requires", "symphony"}
    if (not required.issubset(task) or not isinstance(task["title"], str) or not task["title"].strip()
            or len(task["title"]) > 160 or "\n" in task["title"] or _SECRET_NAMES.search(task["title"])):
        raise PlaneSymphonyError("task policy identity is invalid")
    if task["state"] not in TASK_STATE_MAP or not isinstance(task["requires"], list):
        raise PlaneSymphonyError("task policy state is invalid")
    if any(not isinstance(value, str) or not _TASK_ID.fullmatch(value) for value in task["requires"]):
        raise PlaneSymphonyError("task dependencies are invalid")
    policy = task["symphony"]
    policy_fields = {"allowed_external_operations", "eligible", "preflight_commands", "review_route"}
    if not isinstance(policy, dict) or set(policy) != policy_fields:
        raise PlaneSymphonyError("task Symphony policy schema is invalid")
    operations = policy["allowed_external_operations"]
    if not isinstance(operations, list) or len(set(operations)) != len(operations):
        raise PlaneSymphonyError("task external-operation allowlist is invalid")
    if any(not isinstance(op, str) or not _OPERATION.fullmatch(op) or _FORBIDDEN.search(op) for op in operations):
        raise PlaneSymphonyError("task policy contains a prohibited operation")
    preflights = policy["preflight_commands"]
    if (not isinstance(preflights, list) or not preflights
            or any(not isinstance(item, str) or not _OPERATION.fullmatch(item) or _FORBIDDEN.search(item) for item in preflights)):
        raise PlaneSymphonyError("task preflight is prohibited or invalid")
    if not isinstance(policy["review_route"], str) or policy["review_route"] != "TERRA_IMPLEMENTATION_ASTRA_REVIEW":
        raise PlaneSymphonyError("task review route is invalid")
    if type(policy["eligible"]) is not bool:
        raise PlaneSymphonyError("task write policy is invalid")
    fixed = _FIXED_POLICY[task["id"]]
    if not operations or not set(operations).issubset(fixed["operations"]):
        raise PlaneSymphonyError("task policy operation is outside the fixed allowlist")
    if set(preflights) != fixed["preflights"]:
        raise PlaneSymphonyError("task preflight is outside the fixed allowlist")
    return task


def bind_fixed_operation(catalog: CanonicalTaskCatalog, *, task_id: str, operation: str) -> dict[str, Any]:
    """Bind one controller operation to a validated canonical task policy.

    Plane labels, agent prose, and generic command strings never reach this
    boundary.  The caller receives only a catalog-declared operation and its
    named preflight identifiers; a deployment adapter owns their implementation.
    """
    if task_id not in ROLLOUT_TASK_IDS or not isinstance(operation, str) or not _OPERATION.fullmatch(operation):
        raise PlaneSymphonyError("fixed operation identity is invalid")
    if not isinstance(catalog, CanonicalTaskCatalog) or not _SHA256.fullmatch(catalog.source_sha256):
        raise PlaneSymphonyError("canonical task catalog is invalid")
    task = catalog.task(task_id)
    validated = validate_task_policy(task)
    if validated["symphony"]["eligible"] is not True:
        raise PlaneSymphonyError("operation task is not eligible")
    if operation not in validated["symphony"]["allowed_external_operations"]:
        raise PlaneSymphonyError("operation is not declared by the canonical task")
    return {"task_id": task_id, "operation": operation,
            "preflight_commands": tuple(validated["symphony"]["preflight_commands"]),
            "canonical_task_sha256": "sha256:" + _canonical_digest(validated), "catalog_source_sha256": catalog.source_sha256}


def redact(value: Any) -> Any:
    """Recursively remove values under secret-shaped names before status/log output."""
    if isinstance(value, dict):
        return {str(key): "[REDACTED]" if _SECRET_NAMES.search(str(key)) else redact(item)
                for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def desired_plane_state(task: dict[str, Any]) -> str:
    """Map repository state to display state; Plane Done never creates acceptance."""
    state = TASK_STATE_MAP[task["state"]]
    accepted = repository_accepted(task)
    return "Done" if state == "Done" and accepted else ("Review" if state == "Done" else state)


def repository_accepted(task: dict[str, Any]) -> bool:
    """Acceptance needs state, independent review, and recorded acceptance results."""
    results = task.get("acceptance_results")
    return (task.get("state") == "COMPLETE_REVIEWED"
            and task.get("review_disposition") == "ACCEPTED_INDEPENDENT_REVIEW"
            and isinstance(results, list) and bool(results)
            and all(isinstance(result, str) and result.strip() for result in results))


def transition_task_state(task: dict[str, Any], target_state: str, *,
                          review_disposition: str | None = None,
                          acceptance_results: list[str] | None = None) -> dict[str, Any]:
    """Return one permitted repository-owned task transition.

    This deliberately has no Plane client, lease, or I/O dependency.  A
    repository review route must explicitly apply the returned record to its
    canonical catalog; Plane display changes cannot call or emulate it.
    """
    if not isinstance(task, dict) or not isinstance(target_state, str):
        raise PlaneSymphonyError("task transition input is invalid")
    source_state = task.get("state")
    if target_state not in _TASK_TRANSITIONS.get(source_state, frozenset()):
        raise PlaneSymphonyError("repository task transition is not permitted")
    updated = copy.deepcopy(task)
    updated["state"] = target_state
    if target_state == "COMPLETE_REVIEWED":
        if review_disposition != "ACCEPTED_INDEPENDENT_REVIEW":
            raise PlaneSymphonyError("completion requires an accepted repository review")
        if not isinstance(updated.get("symphony"), dict) or updated["symphony"].get("review_route") != "TERRA_IMPLEMENTATION_ASTRA_REVIEW":
            raise PlaneSymphonyError("completion requires the declared independent review route")
        if (not isinstance(acceptance_results, list) or not acceptance_results
                or any(not isinstance(result, str) or not result.strip() for result in acceptance_results)):
            raise PlaneSymphonyError("completion requires repository acceptance results")
        updated["review_disposition"] = review_disposition
        updated["acceptance_results"] = copy.deepcopy(acceptance_results)
    elif review_disposition is not None or acceptance_results is not None:
        raise PlaneSymphonyError("review evidence may only be recorded at completion")
    return updated


def issue_payload(task: dict[str, Any]) -> dict[str, Any]:
    """Create the minimal, redacted Plane representation of one canonical task."""
    return {
        "external_id": f"FOREX:{task['id']}",
        "name": f"[FOREX:{task['id']}] {task['title']}",
        "state": desired_plane_state(task),
        "description": "Repository-governed task. Plane displays status only; repository evidence and review decide acceptance.",
    }


class LeaseStore:
    """A local durable lease record.  It contains no evidence or credentials."""
    def __init__(self, state_dir: Path):
        self.state_dir = state_dir
        self.path = state_dir / "leases.json"

    def read(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        raw = load_json(self.path)
        if set(raw) != {"leases"} or not isinstance(raw["leases"], dict):
            raise PlaneSymphonyError("lease state is invalid")
        if any(not isinstance(task_id, str) or not isinstance(lease, dict)
               for task_id, lease in raw["leases"].items()):
            raise PlaneSymphonyError("lease entries are invalid")
        return raw["leases"]

    def write(self, leases: dict[str, dict[str, Any]]) -> None:
        self._ensure_directory()
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"leases": redact(leases)}, sort_keys=True) + "\n", encoding="utf-8")
        os.chmod(tmp, 0o600)
        os.replace(tmp, self.path)

    def _ensure_directory(self) -> None:
        self.state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        if stat.S_IMODE(self.state_dir.stat().st_mode) & 0o077:
            raise PlaneSymphonyError("lease directory must not be group/world accessible")

    @contextmanager
    def locked(self):
        """Serialize reservations across independent controller processes."""
        self._ensure_directory()
        lock_path = self.state_dir / "leases.lock"
        with lock_path.open("a+", encoding="utf-8") as handle:
            os.chmod(lock_path, 0o600)
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def reserve(self, lease: dict[str, Any], *, max_workers: int) -> bool:
        """Atomically reserve a worker slot before any runner side effect."""
        with self.locked():
            leases = self.read()
            if lease["task_id"] in leases:
                return False
            active = sum(record.get("status") in _ACTIVE_LEASE_STATES for record in leases.values())
            if active >= max_workers:
                return False
            leases[lease["task_id"]] = lease
            self.write(leases)
            return True

    def transition(self, task_id: str, **updates: Any) -> None:
        with self.locked():
            leases = self.read()
            if task_id not in leases:
                raise PlaneSymphonyError("lease disappeared during transition")
            leases[task_id].update(updates)
            self.write(leases)


def _canonical_digest(value: dict[str, Any]) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _contains_secret_name(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_SECRET_NAMES.search(str(key)) or _contains_secret_name(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_secret_name(item) for item in value)
    return False


def validate_preflight_receipt(task_id: str, commands: tuple[str, ...], baseline_revision: str,
                               configuration_fingerprint: str, receipt: object,
                               *, now: datetime | None = None) -> dict[str, Any]:
    """Accept fresh retained content whose hash binds task, baseline, and policy."""
    fields = {"task_id", "commands", "baseline_revision", "configuration_fingerprint", "status", "observed_at", "content", "receipt_sha256"}
    if not isinstance(receipt, dict) or set(receipt) != fields or _contains_secret_name(receipt.get("content")):
        raise PlaneSymphonyError("preflight receipt schema is invalid")
    digest = receipt.get("receipt_sha256")
    try:
        observed = datetime.fromisoformat(str(receipt.get("observed_at", "")).replace("Z", "+00:00"))
    except ValueError as exc:
        raise PlaneSymphonyError("preflight receipt timestamp is invalid") from exc
    current = now or datetime.now(timezone.utc)
    if observed.tzinfo is None:
        raise PlaneSymphonyError("preflight receipt timestamp is invalid")
    age = (current - observed.astimezone(timezone.utc)).total_seconds()
    content = receipt.get("content")
    bound = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    if (receipt.get("task_id") != task_id or receipt.get("commands") != list(commands)
            or receipt.get("baseline_revision") != baseline_revision
            or receipt.get("configuration_fingerprint") != configuration_fingerprint
            or receipt.get("status") != "PASS" or not isinstance(content, (dict, list))
            or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)
            or _canonical_digest(bound) != digest or age < 0 or age > 300):
        raise PlaneSymphonyError("preflight did not return a valid PASS receipt")
    return receipt


class Controller:
    """Reconcile display state and lease only eligible, canonical H5/A1 tasks."""
    def __init__(self, config: ControllerConfig, catalog: CanonicalTaskCatalog, client: PlaneClient, runner: AgentRunner | None = None):
        if not isinstance(catalog, CanonicalTaskCatalog):
            raise PlaneSymphonyError("controller requires canonical task catalog")
        self.config, self.catalog, self.tasks, self.client, self.runner = config, catalog, catalog.snapshot(), client, runner
        self.leases = LeaseStore(config.state_dir)

    def sync_once(self) -> list[dict[str, Any]]:
        results = []
        leases = self.leases.read()
        for task_id in ROLLOUT_TASK_IDS:
            payload = issue_payload(self.tasks[task_id])
            runtime_status = leases.get(task_id, {}).get("status")
            if runtime_status == "RUNNER_START_UNKNOWN":
                payload["state"] = "Blocked"
            elif runtime_status in _ACTIVE_LEASE_STATES:
                payload["state"] = "In progress"
            elif isinstance(runtime_status, str) and runtime_status.startswith("BLOCKED"):
                payload["state"] = "Blocked"
            elif runtime_status == "COMPLETED":
                payload["state"] = "Review"
            issue = self.client.find_issue(payload["external_id"], payload["name"])
            if issue is None:
                issue = self.client.create_issue(payload)
                action = "created"
            elif any(issue.get(key) != value for key, value in payload.items() if key != "external_id"):
                issue = self.client.update_issue(str(issue["id"]), payload)
                action = "updated"
            else:
                action = "unchanged"
            results.append({"task_id": task_id, "issue_id": str(issue["id"]), "action": action})
        return results

    def _set_runtime_plane_state(self, task: dict[str, Any], state: str) -> None:
        """Display a non-acceptance runtime state after idempotent reconciliation."""
        if state not in {"In progress", "Review", "Blocked"}:
            raise PlaneSymphonyError("runtime Plane state is invalid")
        payload = issue_payload(task)
        payload["state"] = state
        issue = self.client.find_issue(payload["external_id"], payload["name"])
        if not isinstance(issue, dict) or not isinstance(issue.get("id"), (str, int)):
            raise PlaneSymphonyError("Plane task has not been reconciled")
        self.client.update_issue(str(issue["id"]), payload)

    def eligible(self, plane_states: dict[str, str], *, clean_baseline: bool) -> list[str]:
        leases = self.leases.read()
        active = sum(lease.get("status") in _ACTIVE_LEASE_STATES for lease in leases.values())
        eligible: list[str] = []
        for task_id in ROLLOUT_TASK_IDS:
            task = self.tasks[task_id]
            if (task_id in leases or not task["symphony"]["eligible"]
                    or plane_states.get(task_id) != "Ready"):
                continue
            # The initial rollout has no task-level write waiver.  Treat every
            # possible Codex run as write-capable so a dirty baseline fails closed.
            if not clean_baseline:
                continue
            dependencies = tuple(task["requires"]) + (("H5",) if task_id == "A1" else ())
            if any(not repository_accepted(self.tasks.get(dep, {})) for dep in dependencies):
                continue
            if task["state"] != "READY":
                continue
            if active + len(eligible) >= self.config.max_workers:
                break
            eligible.append(task_id)
        return eligible

    def recover_leases(self, *, baseline_revision: str) -> list[dict[str, str]]:
        """Classify durable leases after restart and block configuration drift.

        This never starts another agent.  A matching lease is resumable by the
        deployment-owned runner; a changed baseline or task policy remains a
        visible blocked record rather than being silently reused.
        """
        if not re.fullmatch(r"[0-9a-f]{7,64}", baseline_revision):
            raise PlaneSymphonyError("baseline revision is invalid")
        with self.leases.locked():
            leases, outcome = self.leases.read(), []
            changed = False
            for task_id, lease in leases.items():
                # A terminal lease is historical operational evidence.  A
                # restart must never turn failure/completion into an active
                # retry; a future reviewed retry operation may add a new
                # lease without overwriting this record.
                if lease.get("status") not in _ACTIVE_LEASE_STATES:
                    outcome.append({"task_id": task_id, "status": str(lease.get("status", "BLOCKED_LIFECYCLE_INVALID"))})
                    continue
                try:
                    canonical = self.catalog.task(task_id)
                    operation = bind_fixed_operation(self.catalog, task_id=task_id,
                                                     operation=canonical["symphony"]["allowed_external_operations"][0])
                    fingerprint = operation["canonical_task_sha256"].removeprefix("sha256:")
                    source_sha = operation["catalog_source_sha256"]
                except (KeyError, IndexError, PlaneSymphonyError):
                    fingerprint, source_sha = "", ""
                if (lease.get("baseline_revision") != baseline_revision
                        or lease.get("configuration_fingerprint") != fingerprint
                        or lease.get("catalog_source_sha256") != source_sha):
                    lease["status"] = "BLOCKED_CONFIGURATION_DRIFT"
                    outcome.append({"task_id": task_id, "status": "BLOCKED_CONFIGURATION_DRIFT"})
                    changed = True
                else:
                    lease["status"] = "RESUMABLE"
                    outcome.append({"task_id": task_id, "status": "RESUMABLE"})
                    changed = True
            if changed:
                self.leases.write(leases)
        return outcome

    def reconcile_runner_lifecycle(self) -> list[dict[str, str]]:
        """Inspect every active reservation before it can release worker capacity."""
        if self.runner is None:
            raise PlaneSymphonyError("agent runner is not configured")
        outcome: list[dict[str, str]] = []
        for task_id, lease in self.leases.read().items():
            if lease.get("status") not in _ACTIVE_LEASE_STATES:
                continue
            task = self.tasks.get(task_id)
            if not isinstance(task, dict) or not isinstance(lease.get("idempotency_key"), str):
                self.leases.transition(task_id, status="BLOCKED_LIFECYCLE_INVALID")
                outcome.append({"task_id": task_id, "status": "BLOCKED_LIFECYCLE_INVALID"})
                continue
            try:
                observation = self.runner.inspect(task_id=task_id, idempotency_key=lease["idempotency_key"],
                                                  agent_run_id=lease.get("agent_run_id"))
                fields = {"task_id", "idempotency_key", "agent_run_id", "status"}
                if (not isinstance(observation, dict) or set(observation) != fields
                        or observation["task_id"] != task_id or observation["idempotency_key"] != lease["idempotency_key"]
                        or observation["agent_run_id"] != lease.get("agent_run_id")
                        or observation["status"] not in {"RUNNING", "COMPLETED", "FAILED", "NOT_STARTED"}):
                    raise PlaneSymphonyError("runner lifecycle observation is invalid")
            except Exception:
                # Capacity remains held if termination cannot be inspected.
                outcome.append({"task_id": task_id, "status": "INSPECTION_UNAVAILABLE"})
                continue
            if observation["status"] == "RUNNING":
                self.leases.transition(task_id, status="IN_PROGRESS")
                outcome.append({"task_id": task_id, "status": "IN_PROGRESS"})
            elif observation["status"] == "COMPLETED":
                # Only this repository-owned transition advances the canonical
                # in-memory task record.  Plane merely reflects the resulting
                # review state and cannot supply acceptance evidence.
                self.tasks[task_id] = transition_task_state(task, "IN_REVIEW")
                task = self.tasks[task_id]
                self.leases.transition(task_id, status="COMPLETED")
                self._set_runtime_plane_state(task, "Review")
                outcome.append({"task_id": task_id, "status": "COMPLETED"})
            else:
                self.leases.transition(task_id, status="BLOCKED_RUNNER_FAILURE")
                self._set_runtime_plane_state(task, "Blocked")
                outcome.append({"task_id": task_id, "status": "BLOCKED_RUNNER_FAILURE"})
        return outcome

    def run_once(self, plane_states: dict[str, str], *, baseline_revision: str, clean_baseline: bool) -> list[dict[str, Any]]:
        if not re.fullmatch(r"[0-9a-f]{7,64}", baseline_revision):
            raise PlaneSymphonyError("baseline revision is invalid")
        if self.runner is None:
            raise PlaneSymphonyError("agent runner is not configured")
        # Idempotent reconciliation establishes the fixed Plane issue before a
        # lease can change its display state.  The concrete client is injected.
        self.sync_once()
        self.recover_leases(baseline_revision=baseline_revision)
        self.reconcile_runner_lifecycle()
        self.sync_once()
        started = []
        for task_id in self.eligible(plane_states, clean_baseline=clean_baseline):
            task = self.tasks[task_id]
            # This is the sole operation/preflight selection boundary before a
            # runner side effect.  Do not read policy strings directly below.
            operation = bind_fixed_operation(
                self.catalog, task_id=task_id,
                operation=task["symphony"]["allowed_external_operations"][0],
            )
            worktree = self.config.worktree_root / task_id.lower()
            fingerprint = operation["canonical_task_sha256"].removeprefix("sha256:")
            prompt = self._prompt(task, baseline_revision)
            lease = {"task_id": task_id, "baseline_revision": baseline_revision,
                     "configuration_fingerprint": fingerprint, "catalog_source_sha256": operation["catalog_source_sha256"],
                     "task_policy_sha256": operation["canonical_task_sha256"], "worktree": str(worktree),
                     "idempotency_key": uuid4().hex, "status": "RESERVED"}
            if not self.leases.reserve(lease, max_workers=self.config.max_workers):
                continue
            if (lease["catalog_source_sha256"] != self.catalog.source_sha256
                    or lease["task_policy_sha256"] != operation["canonical_task_sha256"]):
                self.leases.transition(task_id, status="BLOCKED_CATALOG_DRIFT")
                started.append({"task_id": task_id, "status": "BLOCKED_CATALOG_DRIFT"})
                continue
            try:
                self._set_runtime_plane_state(task, "In progress")
            except Exception:
                self.leases.transition(task_id, status="BLOCKED_PLANE_UPDATE")
                started.append({"task_id": task_id, "status": "BLOCKED_PLANE_UPDATE"})
                continue
            commands = operation["preflight_commands"]
            try:
                receipt = validate_preflight_receipt(task_id, commands, baseline_revision, fingerprint,
                    self.runner.preflight(task_id=task_id, commands=commands, baseline_revision=baseline_revision,
                                          configuration_fingerprint=fingerprint))
                self.leases.transition(task_id, preflight_receipt=receipt)
            except Exception:
                self.leases.transition(task_id, status="BLOCKED_PREFLIGHT")
                self._set_runtime_plane_state(task, "Blocked")
                started.append({"task_id": task_id, "status": "BLOCKED_PREFLIGHT"})
                continue
            try:
                agent_run_id = self.runner.start(task_id=task_id, worktree=worktree, prompt=prompt,
                                                 limits={"cpu": self.config.cpu_limit, "memory_mib": self.config.memory_mib, "pids": self.config.pids_limit},
                                                 idempotency_key=lease["idempotency_key"])
                if not isinstance(agent_run_id, str) or not agent_run_id:
                    raise PlaneSymphonyError("agent runner returned an invalid run ID")
            except Exception:
                # A transport error can occur after a runner accepted the
                # request.  Keep capacity reserved until an explicit inspect.
                self.leases.transition(task_id, status="RUNNER_START_UNKNOWN")
                self._set_runtime_plane_state(task, "Blocked")
                started.append({"task_id": task_id, "status": "RUNNER_START_UNKNOWN"})
                continue
            self.leases.transition(task_id, agent_run_id=agent_run_id, status="IN_PROGRESS")
            started.append({"task_id": task_id, "agent_run_id": agent_run_id})
        return started

    @staticmethod
    def _prompt(task: dict[str, Any], baseline_revision: str) -> str:
        return (f"Task {task['id']} at baseline {baseline_revision}. Follow AGENTS.md and the active ExecPlan. "
                "Plane is display-only: it cannot approve acceptance, evidence, broker activity, trading, commits, pushes, or formal closeout. "
                f"Only these declared external operations are eligible after fixed preflight {', '.join(task['symphony']['preflight_commands'])}: "
                + ", ".join(task["symphony"]["allowed_external_operations"]))


def status_report(config: ControllerConfig, tasks: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Return local, non-secret controller state without contacting Plane."""
    leases = LeaseStore(config.state_dir).read()
    return {"schema_version": SCHEMA_VERSION, "execution_authority": False, "rollout_task_ids": list(ROLLOUT_TASK_IDS),
            "max_workers": config.max_workers, "lease_count": len(leases), "leases": redact(leases),
            "task_states": {key: desired_plane_state(value) for key, value in tasks.items()}}
