"""Durable, non-authorising local lease state for the H5 execution loop.

This module stores no output, evidence, secrets, Plane fields, or review prose.
Repository review is intentionally outside this store: a local lease may reach
``IN_REVIEW`` but cannot declare task acceptance, Plane ``Done``, or a retry.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from typing import Any
from uuid import UUID


_STATES = frozenset({"SELECTED", "PREFLIGHT_PASSED", "RUNNING", "IN_REVIEW", "BLOCKED"})
_NEXT = {"SELECTED": frozenset({"PREFLIGHT_PASSED", "BLOCKED"}), "PREFLIGHT_PASSED": frozenset({"RUNNING", "BLOCKED"}), "RUNNING": frozenset({"IN_REVIEW", "BLOCKED"}), "IN_REVIEW": frozenset({"BLOCKED"}), "BLOCKED": frozenset()}
_TASK_ID = re.compile(r"^[A-Z][A-Z0-9_-]{0,63}$")
_ITEM_ID = re.compile(r"^[a-z][a-z0-9-]{0,127}$")
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_GIT_REVISION = re.compile(r"^[0-9a-f]{40}$")
_RECEIPT_CODE = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")
_FIELDS = frozenset({"task_id", "item_id", "selector_sha256", "work_plan_sha256", "canonical_task_sha256", "baseline_revision", "configuration_fingerprint", "lease_id", "worker_run_id", "state", "attempt", "updated_at_utc", "receipt_code", "retry_review_record_sha256"})


class ExecutionLoopError(ValueError):
    """The local durable controller record is unsafe or inconsistent."""


def _pairs(items: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in items:
        if key in result:
            raise ExecutionLoopError("loop state has duplicate fields")
        result[key] = value
    return result


class LoopStore:
    """Owner-only, atomic, single-task lease state with explicit recovery."""

    def __init__(self, state_dir: Path):
        self.state_dir, self.path = state_dir, state_dir / "execution-loop.json"

    @staticmethod
    def _private(path: Path, mode: int, label: str, *, directory: bool = False) -> None:
        try:
            info = path.lstat()
        except OSError as exc:
            raise ExecutionLoopError(f"{label} is unavailable") from exc
        if stat.S_ISLNK(info.st_mode) or (not stat.S_ISDIR(info.st_mode) if directory else not stat.S_ISREG(info.st_mode)):
            raise ExecutionLoopError(f"{label} must be a private regular {'directory' if directory else 'file'}")
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != mode:
            raise ExecutionLoopError(f"{label} must be owner-only")

    def _directory(self) -> None:
        if not os.path.lexists(self.state_dir):
            self.state_dir.mkdir(mode=0o700, parents=True)
            os.chmod(self.state_dir, 0o700)
        self._private(self.state_dir, 0o700, "loop state directory", directory=True)

    @contextmanager
    def locked(self):
        self._directory(); lock = self.state_dir / "execution-loop.lock"
        flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(lock, flags, 0o600)
            os.chmod(lock, 0o600)
            self._private(lock, 0o600, "loop state lock")
        except OSError as exc:
            raise ExecutionLoopError("loop state lock is unsafe") from exc
        with os.fdopen(fd, "a+", encoding="utf-8") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def read(self) -> dict[str, Any] | None:
        if not os.path.lexists(self.path): return None
        self._private(self.path, 0o600, "loop state file")
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"), object_pairs_hook=_pairs,
                               parse_constant=lambda _value: (_ for _ in ()).throw(ExecutionLoopError("nonfinite loop state")))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ExecutionLoopError("loop state is invalid") from exc
        self._validate(value); return value

    def select(self, *, task_id: str, item_id: str, selector_sha256: str, work_plan_sha256: str,
               canonical_task_sha256: str, baseline_revision: str, configuration_fingerprint: str,
               lease_id: str, worker_run_id: str, receipt_code: str) -> dict[str, Any]:
        """Start exactly one lease; retry is reserved for a verified adapter."""
        with self.locked():
            current = self.read()
            if current:
                raise ExecutionLoopError("active loop lease already exists")
            record = {"task_id": task_id, "item_id": item_id, "selector_sha256": selector_sha256,
                      "work_plan_sha256": work_plan_sha256, "canonical_task_sha256": canonical_task_sha256,
                      "baseline_revision": baseline_revision, "configuration_fingerprint": configuration_fingerprint,
                      "lease_id": lease_id, "worker_run_id": worker_run_id, "state": "SELECTED", "attempt": 1,
                      "updated_at_utc": self._now(), "receipt_code": receipt_code,
                      "retry_review_record_sha256": None}
            self._validate(record); self._write(record); return record

    def transition(self, target: str, receipt_code: str, *, expected_selector_sha256: str,
                   expected_work_plan_sha256: str, expected_canonical_task_sha256: str) -> dict[str, Any]:
        """Advance one graph edge; repository acceptance is deliberately excluded."""
        with self.locked():
            current = self.read()
            if not current or target not in _NEXT[current["state"]]:
                raise ExecutionLoopError("loop transition is not permitted")
            if (current["selector_sha256"] != expected_selector_sha256 or current["work_plan_sha256"] != expected_work_plan_sha256
                    or current["canonical_task_sha256"] != expected_canonical_task_sha256):
                raise ExecutionLoopError("loop transition has stale selection or canonical digest")
            current.update(state=target, receipt_code=receipt_code, updated_at_utc=self._now())
            self._validate(current); self._write(current); return current

    def recover(self, *, task_id: str, item_id: str, baseline_revision: str, configuration_fingerprint: str,
                lease_id: str, worker_run_id: str, worker_status: str) -> dict[str, str]:
        """Classify a restart without starting a replacement worker.

        Unknown inspection deliberately holds the slot; only a matching completed
        worker is eligible to move on to review by a later fixed adapter.
        """
        with self.locked():
            current = self.read()
            if not current or any(current[key] != value for key, value in {"task_id": task_id, "item_id": item_id, "baseline_revision": baseline_revision, "configuration_fingerprint": configuration_fingerprint, "lease_id": lease_id, "worker_run_id": worker_run_id}.items()):
                raise ExecutionLoopError("restart lease does not match durable state")
            if worker_status not in {"RUNNING", "COMPLETED", "FAILED", "UNKNOWN"}:
                raise ExecutionLoopError("worker inspection state is invalid")
            if worker_status in {"RUNNING", "UNKNOWN"}: return {"outcome": "HOLD_CAPACITY", "state": current["state"]}
            if worker_status == "FAILED" and current["state"] != "BLOCKED":
                current.update(state="BLOCKED", receipt_code="WORKER_FAILED", updated_at_utc=self._now()); self._write(current)
            if worker_status == "COMPLETED" and current["state"] != "RUNNING":
                current.update(state="BLOCKED", receipt_code="LIFECYCLE_DRIFT", updated_at_utc=self._now()); self._write(current)
            return {"outcome": "RESUME_REVIEW" if worker_status == "COMPLETED" and current["state"] == "RUNNING" else "BLOCKED", "state": current["state"]}

    @staticmethod
    def _now() -> str: return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _validate(value: object) -> None:
        if not isinstance(value, dict) or set(value) != _FIELDS: raise ExecutionLoopError("loop state schema is invalid")
        if not isinstance(value["task_id"], str) or not _TASK_ID.fullmatch(value["task_id"]): raise ExecutionLoopError("loop task ID is invalid")
        if not isinstance(value["item_id"], str) or not _ITEM_ID.fullmatch(value["item_id"]): raise ExecutionLoopError("loop item ID is invalid")
        for field in ("selector_sha256", "work_plan_sha256", "canonical_task_sha256", "configuration_fingerprint"):
            if not isinstance(value[field], str) or not _SHA256.fullmatch(value[field]): raise ExecutionLoopError("loop digest is invalid")
        if not isinstance(value["baseline_revision"], str) or not _GIT_REVISION.fullmatch(value["baseline_revision"]): raise ExecutionLoopError("loop baseline revision is invalid")
        for field in ("lease_id", "worker_run_id"):
            try: UUID(str(value[field]))
            except (ValueError, TypeError, AttributeError) as exc: raise ExecutionLoopError(f"loop {field} is invalid") from exc
        if value["state"] not in _STATES or type(value["attempt"]) is not int or not 1 <= value["attempt"] <= 2: raise ExecutionLoopError("loop state or attempt is invalid")
        if not isinstance(value["receipt_code"], str) or not _RECEIPT_CODE.fullmatch(value["receipt_code"]): raise ExecutionLoopError("loop receipt code is invalid")
        if value["retry_review_record_sha256"] is not None and (not isinstance(value["retry_review_record_sha256"], str) or not _SHA256.fullmatch(value["retry_review_record_sha256"])): raise ExecutionLoopError("loop retry review record is invalid")
        if not isinstance(value["updated_at_utc"], str) or not value["updated_at_utc"].endswith("Z"): raise ExecutionLoopError("loop timestamp is invalid")
        try: datetime.fromisoformat(value["updated_at_utc"].replace("Z", "+00:00"))
        except ValueError as exc: raise ExecutionLoopError("loop timestamp is invalid") from exc

    def _write(self, value: dict[str, Any]) -> None:
        self._directory(); fd, temporary_name = tempfile.mkstemp(prefix=".execution-loop-", suffix=".tmp", dir=self.state_dir, text=True)
        temporary = Path(temporary_name)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(value, handle, sort_keys=True, separators=(",", ":")); handle.write("\n"); handle.flush(); os.fsync(handle.fileno())
            os.replace(temporary, self.path)
            directory_fd = os.open(self.state_dir, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0));
            try: os.fsync(directory_fd)
            finally: os.close(directory_fd)
        finally:
            if temporary.exists(): temporary.unlink()
