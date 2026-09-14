#!/usr/bin/env python3
"""Run one local M1 event-sidecar batch and retain its immutable service report."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any, Iterator


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config" / "m1_event_annotations.json"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import m1_event_batch as batch  # noqa: E402


POLICY_SCHEMA = "forex.m1-event-automation-policy.v1"
REPORT_SCHEMA = "forex.m1-event-service-report.v1"
START_SCHEMA = "forex.m1-event-service-start.v1"
_POLICY_KEYS = {"schema_version", "window_mode", "execution_authority"}


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON field")
        value[key] = item
    return value


def _constant(value):
    raise ValueError("nonfinite JSON value")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _trusted(path: Path, *, label: str) -> Path:
    if not path.exists() or path.is_symlink() or not path.is_dir():
        raise ValueError(f"{label} must name an existing trusted non-symlink directory")
    from forex.event_capture_store import _no_symlink_ancestors
    _no_symlink_ancestors(path)
    return path


def _policy() -> tuple[dict[str, Any], str]:
    raw = POLICY_PATH.read_bytes()
    value = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_constant)
    if (not isinstance(value, dict) or set(value) != _POLICY_KEYS
            or value.get("schema_version") != POLICY_SCHEMA
            or value.get("window_mode") != "DECISION_UTC_DAY"
            or value.get("execution_authority") is not False):
        raise ValueError("M1 event automation policy is invalid")
    return value, "sha256:" + hashlib.sha256(raw).hexdigest()


@contextmanager
def _lock(reports: Path) -> Iterator[None]:
    path = reports / ".m1-event-service.lock"
    if path.is_symlink():
        raise ValueError("service lock path is unsafe")
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _validate_batch(result: Any) -> dict[str, Any]:
    if not isinstance(result, dict) or result.get("execution_authority") is not False:
        raise ValueError("batch did not return a non-executing report")
    for field in ("total_count", "attached_count", "refused_count"):
        value = result.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError("batch counts are invalid")
    if result["attached_count"] + result["refused_count"] != result["total_count"]:
        raise ValueError("batch counts do not account for every input")
    if not isinstance(result.get("records"), list):
        raise ValueError("batch records are invalid")
    records = result["records"]
    if (result.get("schema_version") != batch.REPORT_SCHEMA or len(records) != result["total_count"]
            or result.get("state") != ("COMPLETE" if records else "NO_INPUTS")
            or any(not isinstance(row, dict) or row.get("status") not in {"ATTACHED", "INPUT_REFUSED"} for row in records)
            or sum(row["status"] == "ATTACHED" for row in records) != result["attached_count"]):
        raise ValueError("batch rows do not match declared counts or schema")
    return json.loads(_canonical(result))


def _combine_batches(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Join independently bounded roots without hiding a refused input."""
    if not results:
        raise ValueError("at least one assessment root is required")
    verified = [_validate_batch(result) for result in results]
    records = [record for result in verified for record in result["records"]]
    total = sum(result["total_count"] for result in verified)
    attached = sum(result["attached_count"] for result in verified)
    refused = sum(result["refused_count"] for result in verified)
    return {
        "schema_version": batch.REPORT_SCHEMA,
        "state": "NO_INPUTS" if not records else "COMPLETE",
        "assessment_roots": [result["assessment_root"] for result in verified],
        "total_count": total,
        "attached_count": attached,
        "refused_count": refused,
        "records": records,
        "execution_authority": False,
    }


def _filename(kind: str, started: str, digest: str) -> str:
    stamp = started.replace("-", "").replace(":", "").replace(".", "")
    return f"m1-event-service-{kind}-{stamp}-{digest.removeprefix('sha256:')}.json"


def _publish(reports: Path, artifact: dict[str, Any], *, kind: str,
             digest_field: str) -> tuple[Path, bool]:
    from forex.event_capture_store import CaptureConflictError, _publish_exclusive

    digest = artifact[digest_field]
    payload = _canonical(artifact)
    target = reports / _filename(kind, artifact["started_at_utc"], digest)
    if target.exists() or target.is_symlink():
        if target.is_symlink() or not target.is_file() or target.read_bytes() != payload:
            raise ValueError("existing service artifact conflicts or is unsafe")
        return target, False
    try:
        _publish_exclusive(target, payload)
        return target, True
    except CaptureConflictError as exc:
        if target.exists() and not target.is_symlink() and target.is_file() and target.read_bytes() == payload:
            return target, False
        raise ValueError("service artifact publication conflict") from exc


def run_once(*, assessment_root: Path, store: Path, sidecars: Path,
             reports: Path, additional_assessment_roots: tuple[Path, ...] = ()) -> tuple[dict[str, Any], Path, bool]:
    root = _trusted(assessment_root, label="assessment_root")
    additional = tuple(_trusted(item, label="additional_assessment_root") for item in additional_assessment_roots)
    roots = (root, *additional)
    if len({str(item) for item in roots}) != len(roots):
        raise ValueError("assessment roots must be unique")
    trusted_store = _trusted(store, label="store")
    trusted_sidecars = _trusted(sidecars, label="sidecars")
    trusted_reports = _trusted(reports, label="reports")
    policy, policy_sha = _policy()
    with _lock(trusted_reports):
        started = _now()
        start_content = {"schema_version": START_SCHEMA, "started_at_utc": started,
                         "policy_sha256": policy_sha, "assessment_roots": [str(item) for item in roots],
                         "store": str(trusted_store), "sidecars": str(trusted_sidecars),
                         "execution_authority": False}
        start_record = {**start_content, "start_record_sha256": _sha(start_content)}
        # Publish before invoking the potentially watchdog-bounded batch.  If
        # the process dies or the batch refuses, this immutable record remains
        # an explicit unfinished run, not a successful service claim.
        _publish(trusted_reports, start_record, kind="start", digest_field="start_record_sha256")
        result = _combine_batches([batch.run_batch(
            assessment_root=item, store=trusted_store, output=trusted_sidecars,
            window_start=None, window_end=None, window_mode=policy["window_mode"],
        ) for item in roots])
        completed = _now()
        if datetime.fromisoformat(completed.replace("Z", "+00:00")) < datetime.fromisoformat(started.replace("Z", "+00:00")):
            raise ValueError("service clock moved backwards during batch")
        content = {"schema_version": REPORT_SCHEMA, "started_at_utc": started,
                   "completed_at_utc": completed, "policy_sha256": policy_sha,
                   "start_record_sha256": start_record["start_record_sha256"],
                   "result": result, "execution_authority": False}
        report = {**content, "report_sha256": _sha(content)}
        path, created = _publish(trusted_reports, report, kind="report", digest_field="report_sha256")
        return report, path, created


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assessment-root", type=Path, required=True)
    parser.add_argument("--additional-assessment-root", type=Path, action="append", default=[])
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--sidecars", type=Path, required=True)
    parser.add_argument("--reports", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report, path, created = run_once(assessment_root=args.assessment_root, store=args.store,
                                         sidecars=args.sidecars, reports=args.reports,
                                         additional_assessment_roots=tuple(args.additional_assessment_root))
        result = report["result"]
        print(json.dumps({"schema_version": "forex.m1-event-service-command.v1",
                          "report_path": str(path), "report_sha256": report["report_sha256"],
                          "publication": "CREATED" if created else "EXISTING",
                          "state": result.get("state"), "total_count": result["total_count"],
                          "attached_count": result["attached_count"], "refused_count": result["refused_count"],
                          "execution_authority": False}, sort_keys=True, allow_nan=False))
        return 0
    except (OSError, ValueError, TypeError, OverflowError, RuntimeError) as exc:
        print("M1 event service refused; inspect local policy, batch, and retained report state", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
