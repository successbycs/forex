"""Durable, bounded scheduler kernel for the BLS monthly collector.

The kernel owns only a small immutable scheduler ledger.  The supplied
collector owns acquisition and capture-store publication; it runs under the
scheduler-only lock, never under the event-capture-store lock.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Callable, Iterator


POLICY_SCHEMA = "forex.bls-scheduler-policy.v1"
RUN_SCHEMA = "forex.bls-schedule-run.v1"
CLAIM_SCHEMA = "forex.bls-schedule-claim.v1"
RESULT_SCHEMA = "forex.bls-schedule-result.v1"
_ID = re.compile(r"bls-monthly-(20\d\d)(0[1-9]|1[0-2])-b([0-9]+)\Z")
_POLICY_KEYS = {"schema_version", "interval_seconds", "denial_backoff_seconds", "month_offsets", "execution_authority"}
_CLAIM_KEYS = {"schema_version", "capture_id", "bucket", "year", "month", "claimed_at_utc", "policy_sha256", "claim_sha256"}
_RESULT_KEYS = {"schema_version", "capture_id", "claim_sha256", "collector_result", "collector_result_sha256", "completed_at_utc", "store_health", "result_sha256"}


class BLSSchedulerError(ValueError):
    """Invalid scheduler policy or immutable local scheduler state."""


def _unique_pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise BLSSchedulerError("duplicate scheduler JSON field")
        value[key] = item
    return value


def _bad_constant(value):
    raise BLSSchedulerError("nonfinite scheduler JSON constant")


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise BLSSchedulerError("scheduler value is not finite JSON") from exc


def _sha(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _copy(value: Any) -> Any:
    return json.loads(_canonical(value))


def _utc(value: str) -> tuple[datetime, str]:
    if not isinstance(value, str):
        raise BLSSchedulerError("now_utc must be a timezone-aware timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BLSSchedulerError("now_utc is invalid") from exc
    if parsed.tzinfo is None:
        raise BLSSchedulerError("now_utc must include a timezone")
    parsed = parsed.astimezone(timezone.utc)
    return parsed, parsed.isoformat().replace("+00:00", "Z")


def _policy(policy: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(policy, dict) or set(policy) != _POLICY_KEYS:
        raise BLSSchedulerError("scheduler policy fields are invalid")
    if policy.get("schema_version") != POLICY_SCHEMA or policy.get("execution_authority") is not False:
        raise BLSSchedulerError("scheduler policy schema or authority is invalid")
    interval = policy.get("interval_seconds")
    backoff = policy.get("denial_backoff_seconds")
    if (isinstance(interval, bool) or not isinstance(interval, int) or not 3600 <= interval <= 86400):
        raise BLSSchedulerError("interval_seconds must be an integer in 3600..86400")
    if (isinstance(backoff, bool) or not isinstance(backoff, int) or not 86400 <= backoff <= 604800):
        raise BLSSchedulerError("denial_backoff_seconds must be an integer in 86400..604800")
    offsets = policy.get("month_offsets")
    if (not isinstance(offsets, list) or len(offsets) != 2
            or any(isinstance(offset, bool) or not isinstance(offset, int) for offset in offsets)
            or offsets != [0, 1]):
        raise BLSSchedulerError("month_offsets must be exactly [0, 1]")
    return _copy(policy)


def _add_months(now: datetime, offset: int) -> tuple[int, int]:
    index = now.year * 12 + now.month - 1 + offset
    return index // 12, index % 12 + 1


def _capture_id(year: int, month: int, bucket: int) -> str:
    return f"bls-monthly-{year:04d}{month:02d}-b{bucket}"


def _no_symlink(path: Path) -> None:
    if path.is_symlink():
        raise BLSSchedulerError(f"unsafe symlink: {path}")


def _mkdir(path: Path) -> None:
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_dir():
            raise BLSSchedulerError(f"unsafe scheduler directory: {path}")
        return
    try:
        path.mkdir(mode=0o700)
    except FileExistsError:
        if path.is_symlink() or not path.is_dir():
            raise BLSSchedulerError(f"unsafe scheduler directory: {path}") from None
    descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _layout(root: Path) -> dict[str, Path]:
    if not isinstance(root, Path) or not root.exists() or root.is_symlink() or not root.is_dir():
        raise BLSSchedulerError("root must be an explicit existing non-symlink directory")
    for component in (root.absolute(), *root.absolute().parents):
        _no_symlink(component)
    scheduler = root / "scheduler"
    _mkdir(scheduler)
    claims = scheduler / "claims"
    results = scheduler / "results"
    _mkdir(claims)
    _mkdir(results)
    return {"root": root, "scheduler": scheduler, "claims": claims, "results": results}


@contextmanager
def _lock(layout: dict[str, Path]) -> Iterator[None]:
    path = layout["scheduler"] / ".lock"
    if path.exists() and path.is_symlink():
        raise BLSSchedulerError("scheduler lock path is unsafe")
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _publish(path: Path, value: dict[str, Any]) -> None:
    payload = _canonical(value)
    if path.exists() or path.is_symlink():
        raise BLSSchedulerError(f"immutable scheduler artifact already exists: {path.name}")
    descriptor, staged_name = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    staged = Path(staged_name)
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(staged, path, follow_symlinks=False)
        except FileExistsError as exc:
            raise BLSSchedulerError(f"immutable scheduler artifact already exists: {path.name}") from exc
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        # A failed staging write intentionally remains for inspection; only a
        # successfully linked staging inode is disposable implementation debris.
        if path.exists() and staged.exists():
            staged.unlink()


def _read(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise BLSSchedulerError(f"unsafe scheduler artifact: {path.name}")
    try:
        value = json.loads(path.read_bytes(), object_pairs_hook=_unique_pairs, parse_constant=_bad_constant)
    except (OSError, json.JSONDecodeError) as exc:
        raise BLSSchedulerError(f"cannot read scheduler artifact: {path.name}") from exc
    if not isinstance(value, dict):
        raise BLSSchedulerError("scheduler artifact must be an object")
    return value


def _claim_payload(value: dict[str, Any]) -> dict[str, Any]:
    return {key: value[key] for key in _CLAIM_KEYS - {"claim_sha256"}}


def _result_payload(value: dict[str, Any]) -> dict[str, Any]:
    return {key: value[key] for key in _RESULT_KEYS - {"result_sha256"}}


def _validate_claim(value: dict[str, Any], path: Path) -> dict[str, Any]:
    if set(value) != _CLAIM_KEYS or value.get("schema_version") != CLAIM_SCHEMA:
        raise BLSSchedulerError("scheduler claim schema is invalid")
    if value.get("claim_sha256") != _sha(_claim_payload(value)):
        raise BLSSchedulerError("scheduler claim hash mismatch")
    capture_id = value.get("capture_id")
    match = _ID.fullmatch(capture_id) if isinstance(capture_id, str) else None
    if match is None or path.stem != capture_id:
        raise BLSSchedulerError("scheduler claim filename or capture ID is invalid")
    if value.get("year") != int(match.group(1)) or value.get("month") != int(match.group(2)) or value.get("bucket") != int(match.group(3)):
        raise BLSSchedulerError("scheduler claim ID does not bind its calendar fields")
    if not isinstance(value.get("policy_sha256"), str) or not value["policy_sha256"].startswith("sha256:"):
        raise BLSSchedulerError("scheduler claim policy hash is invalid")
    _utc(value.get("claimed_at_utc"))
    return value


def _validate_collector(value: Any, capture_id: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise BLSSchedulerError("collector result must be an object")
    try:
        copied = _copy(value)
    except BLSSchedulerError:
        raise
    if copied.get("capture_id") != capture_id or copied.get("execution_authority") is not False:
        raise BLSSchedulerError("collector result does not bind capture ID or non-execution authority")
    required = {"schema_version", "capture_id", "execution_authority", "outcome", "status_code",
                "completed_at_utc", "observation_sha256", "coverage_status", "processing"}
    success = copied.get("outcome") == "SUCCESS"
    if set(copied) != required | ({"journal_sha256", "parser_quarantined"} if success else set()):
        raise BLSSchedulerError("collector summary fields are invalid")
    if copied["schema_version"] != "forex.bls-collection-result.v1" or copied["coverage_status"] != "UNKNOWN":
        raise BLSSchedulerError("collector schema or coverage is invalid")
    for key in ["observation_sha256"] + (["journal_sha256"] if success else []):
        if not isinstance(copied[key], str) or re.fullmatch(r"sha256:[0-9a-f]{64}", copied[key]) is None:
            raise BLSSchedulerError("collector evidence hash is invalid")
    status = copied["status_code"]
    if copied["outcome"] not in {"SUCCESS", "HTTP_ERROR", "TRANSPORT_ERROR", "BODY_TOO_LARGE", "UNSUPPORTED_CONTENT_TYPE"} or status is not None and (type(status) is not int or not 100 <= status <= 599):
        raise BLSSchedulerError("collector result outcome or status_code is invalid")
    processing = copied["processing"]
    if success:
        quarantine = copied["parser_quarantined"]
        if (status != 200 or processing != "CAPTURE_RETAINED" or not isinstance(quarantine, list)
                or any(not isinstance(item, dict) or not isinstance(item.get("reason"), str)
                       or any(not isinstance(key, str) or not isinstance(value, str) for key, value in item.items())
                       for item in quarantine)):
            raise BLSSchedulerError("collector success is contradictory")
    elif processing not in {"RETRIEVAL_FAILURE_RETAINED", "TRANSPORT_FAILURE_RETAINED"}:
        raise BLSSchedulerError("collector failure processing is invalid")
    if processing == "TRANSPORT_FAILURE_RETAINED" and (copied["outcome"] != "TRANSPORT_ERROR" or status is not None or copied["completed_at_utc"] is not None):
        raise BLSSchedulerError("transport-only failure is contradictory")
    completed = copied.get("completed_at_utc")
    if completed is None and processing != "TRANSPORT_FAILURE_RETAINED":
        raise BLSSchedulerError("publisher response needs its completion timestamp")
    if completed is not None:
        _utc(completed)
    return copied


def _validate_result(value: dict[str, Any], path: Path, claims: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if set(value) != _RESULT_KEYS or value.get("schema_version") != RESULT_SCHEMA:
        raise BLSSchedulerError("scheduler result schema is invalid")
    if value.get("result_sha256") != _sha(_result_payload(value)):
        raise BLSSchedulerError("scheduler result hash mismatch")
    capture_id = value.get("capture_id")
    claim = claims.get(capture_id)
    if claim is None or path.stem != capture_id or value.get("claim_sha256") != claim["claim_sha256"]:
        raise BLSSchedulerError("scheduler result does not bind a claim")
    collector = _validate_collector(value.get("collector_result"), capture_id)
    if value.get("collector_result_sha256") != _sha(collector):
        raise BLSSchedulerError("scheduler result collector hash mismatch")
    if value.get("store_health") != "UNKNOWN":
        raise BLSSchedulerError("scheduler result store health must remain UNKNOWN")
    completed, _ = _utc(value.get("completed_at_utc"))
    claimed, _ = _utc(claim["claimed_at_utc"])
    if completed < claimed:
        raise BLSSchedulerError("scheduler result predates its claim")
    return value


def _state(layout: dict[str, Path]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    claims = {}
    for path in layout["claims"].glob("*.json"):
        claim = _validate_claim(_read(path), path)
        if claim["capture_id"] in claims:
            raise BLSSchedulerError("duplicate scheduler claim")
        claims[claim["capture_id"]] = claim
    results = {}
    for path in layout["results"].glob("*.json"):
        result = _validate_result(_read(path), path, claims)
        if result["capture_id"] in results:
            raise BLSSchedulerError("duplicate scheduler result")
        results[result["capture_id"]] = result
    ordered = sorted(results.values(), key=lambda item: item["capture_id"])
    if any(_utc(item["completed_at_utc"])[0] < _utc(claims[item["capture_id"]]["claimed_at_utc"])[0] for item in ordered):
        raise BLSSchedulerError("scheduler result chronology is invalid")
    return claims, results


def _run(now: str, policy: dict[str, Any], state: str, results: list[dict[str, Any]], detail: str | None = None) -> dict[str, Any]:
    value = {"schema_version": RUN_SCHEMA, "state": state, "now_utc": now,
             "policy_sha256": _sha(policy), "results": _copy(results),
             "execution_authority": False}
    if detail is not None:
        value["detail"] = detail
    return value


def _record(claim: dict[str, Any], collector: dict[str, Any], completed: str) -> dict[str, Any]:
    value = {"schema_version": RESULT_SCHEMA, "capture_id": claim["capture_id"],
             "claim_sha256": claim["claim_sha256"], "collector_result": collector,
             "collector_result_sha256": _sha(collector), "completed_at_utc": completed,
             "store_health": "UNKNOWN"}
    value["result_sha256"] = _sha(value)
    return value


def _denial_until(results: dict[str, dict[str, Any]], now: datetime, seconds: int) -> str | None:
    deadlines = []
    for result in results.values():
        collector = result["collector_result"]
        if collector["status_code"] in {403, 429}:
            completed, _ = _utc(result["completed_at_utc"])
            deadline = completed.timestamp() + seconds
            if now.timestamp() < deadline:
                deadlines.append(datetime.fromtimestamp(deadline, timezone.utc).isoformat().replace("+00:00", "Z"))
    return max(deadlines) if deadlines else None


def run_schedule_once(root: Path, *, now_utc: str, policy: dict[str, Any], collect: Callable[..., dict[str, Any]]) -> dict[str, Any]:
    """Claim/recover at most the current and following BLS calendar months.

    A pre-existing unfinished claim is always handled first and only through
    ``resume=True``.  New collection is never attempted until that recovery is
    resolved, preventing restarts from issuing a duplicate acquisition.
    """
    now_dt, now = _utc(now_utc)
    policy = _policy(policy)
    if not callable(collect):
        raise BLSSchedulerError("collect must be callable")
    layout = _layout(root)
    bucket = math.floor(now_dt.timestamp() / policy["interval_seconds"])
    policy_hash = _sha(policy)

    # This scheduler-only lock deliberately spans the callback.  It prevents a
    # second process from treating an actively executing new claim as a stale
    # recovery claim.  The collector remains free to take the *different*
    # event-capture-store lock, so there is no lock inversion with that store.
    with _lock(layout):
        claims, results = _state(layout)
        if any(now_dt < _utc(claim["claimed_at_utc"])[0] for claim in claims.values()):
            return _run(now, policy, "RECOVERY_REQUIRED", [], "scheduler clock predates immutable claim")
        denial = _denial_until(results, now_dt, policy["denial_backoff_seconds"])
        if denial is not None:
            return _run(now, policy, "BACKOFF", [], denial)
        pending = sorted((claim for capture_id, claim in claims.items() if capture_id not in results),
                         key=lambda item: (item["bucket"], item["capture_id"]))
        if pending:
            if pending[0]["policy_sha256"] != policy_hash:
                return _run(now, policy, "RECOVERY_REQUIRED", [],
                            "unfinished claim policy does not match current scheduler policy")
            work: list[tuple[dict[str, Any], bool]] = [(pending[0], True)]
        else:
            work = []
            for offset in policy["month_offsets"]:
                year, month = _add_months(now_dt, offset)
                # The monthly parser's official schedule URL grammar is
                # deliberately limited to 2000..2099.  Refuse before writing
                # a claim or asking a collector to contact anything.
                if not 2000 <= year <= 2099:
                    return _run(now, policy, "RECOVERY_REQUIRED", [],
                                "requested calendar month is outside 2000..2099")
                capture_id = _capture_id(year, month, bucket)
                # Bucket numbers use different units after an interval change.
                # Across policy versions, use elapsed wall time for this month
                # so a configuration edit cannot immediately duplicate a GET.
                prior = [claim for claim in claims.values()
                         if claim["year"] == year and claim["month"] == month
                         and claim["policy_sha256"] != policy_hash]
                if any(now_dt.timestamp() - _utc(results[claim["capture_id"]]["completed_at_utc"])[0].timestamp()
                       < policy["interval_seconds"] for claim in prior):
                    continue
                if capture_id not in results:
                    work.append(({"schema_version": CLAIM_SCHEMA, "capture_id": capture_id, "bucket": bucket,
                                  "year": year, "month": month, "claimed_at_utc": now,
                                  "policy_sha256": policy_hash}, False))
            if not work:
                return _run(now, policy, "NOT_DUE", [])

        completed: list[dict[str, Any]] = []
        for target, recovery in work:
            if not recovery:
                target["claim_sha256"] = _sha(target)
                _publish(layout["claims"] / f"{target['capture_id']}.json", target)

            try:
                collector = _validate_collector(collect(year=target["year"], month=target["month"],
                                                        capture_id=target["capture_id"], resume=recovery),
                                                target["capture_id"])
            except Exception:
                return _run(now, policy, "RECOVERY_REQUIRED", completed,
                            "collector did not provide a valid recoverable result")

            completed_at = now
            if collector.get("completed_at_utc") is not None:
                observed_completed, canonical_completed = _utc(collector["completed_at_utc"])
                if observed_completed > now_dt:
                    completed_at = canonical_completed
            record = _record(target, collector, completed_at)
            # Refuse contradictory chronology before immutable publication.
            _validate_result(record, layout["results"] / f"{target['capture_id']}.json",
                             {target["capture_id"]: target})
            current_claims, current_results = _state(layout)
            current = current_claims.get(target["capture_id"])
            if current is None or current != target:
                return _run(now, policy, "RECOVERY_REQUIRED", completed, "scheduler claim changed during collection")
            existing = current_results.get(target["capture_id"])
            if existing is None:
                _publish(layout["results"] / f"{target['capture_id']}.json", record)
                existing = record
            elif existing != record:
                return _run(now, policy, "RECOVERY_REQUIRED", completed, "conflicting immutable collector result")
            completed.append(existing)
            # A fresh denial applies immediately to the other requested month.
            if collector["status_code"] in {403, 429}:
                break
        return _run(now, policy, "RUN_COMPLETE", completed)
