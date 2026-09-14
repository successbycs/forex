#!/usr/bin/env python3
"""Build context-only sidecars for one-level retained M1 assessment batches."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import subprocess
from datetime import datetime, timezone, timedelta
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import m1_event_sidecar as sidecar_cli  # noqa: E402


REPORT_SCHEMA = "forex.m1-event-batch-report.v1"


def _trusted_directory(path: Path, *, label: str) -> Path:
    if not path.exists() or path.is_symlink() or not path.is_dir():
        raise ValueError(f"{label} must name an existing trusted non-symlink directory")
    from forex.event_capture_store import _no_symlink_ancestors
    _no_symlink_ancestors(path)
    return path


def _candidates(root: Path) -> list[Path]:
    """Discover only ``child/demo-trading-operation.json`` without recursion."""
    paths: list[Path] = []
    for child in sorted(root.iterdir(), key=lambda item: item.name):
        if child.is_symlink() or not child.is_dir():
            continue
        candidate = child / "demo-trading-operation.json"
        if candidate.exists() or candidate.is_symlink():
            paths.append(candidate)
    return paths


def _refused(path: Path, *, digest: str | None, code: str) -> dict[str, Any]:
    return {"source_path": str(path), "source_raw_sha256": digest,
            "status": "INPUT_REFUSED", "reason_code": code}


def _reason(error: BaseException) -> str:
    """Classify local failures without copying exception text into a report."""
    if isinstance(error, subprocess.TimeoutExpired):
        return "EVENT_CONTEXT_TIMEOUT"
    if isinstance(error, json.JSONDecodeError) or str(error) in {"invalid JSON", "duplicate JSON field", "nonfinite JSON value"}:
        return "INVALID_ASSESSMENT_JSON"
    if isinstance(error, OSError):
        return "ASSESSMENT_READ_FAILED"
    message = str(error)
    if "timestamps are not chronological" in message:
        return "ASSESSMENT_CLOCK_ORDER_INVALID"
    if "snapshot body is not a deployed" in message:
        return "UNSUPPORTED_SNAPSHOT_SCHEMA"
    if "payload_sha256 does not match retained body" in message:
        return "SNAPSHOT_DIGEST_MISMATCH"
    if "stdout is not JSON" in message:
        return "ASSESSMENT_OPERATION_OUTPUT_NOT_JSON"
    if "coverage-only" in message or "retained full" in message or "unsupported" in message:
        return "UNSUPPORTED_RETAINED_ASSESSMENT"
    if "event-context" in message or "event context" in message:
        return "EVENT_CONTEXT_UNAVAILABLE"
    if "sidecar" in message or "digest path" in message:
        return "SIDECAR_PUBLICATION_REFUSED"
    return "INPUT_VALIDATION_REFUSED"


def _process(path: Path, *, store: Path, output: Path,
             window_start: str | None, window_end: str | None, window_mode: str | None = None) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        return _refused(path, digest=None, code="UNSAFE_ASSESSMENT_PATH")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return _refused(path, digest=None, code=_reason(exc))
    digest = "sha256:" + hashlib.sha256(raw).hexdigest()
    try:
        assessment = sidecar_cli._strict_json(raw)
        decision = sidecar_cli._full_decision(assessment, digest)
        if window_mode == "DECISION_UTC_DAY":
            instant = datetime.fromisoformat(decision.replace("Z", "+00:00"))
            if instant.tzinfo is None:
                raise ValueError("decision timestamp must include its timezone")
            start = instant.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            window_start = start.isoformat().replace("+00:00", "Z")
            # Annotation windows are inclusive: exclude the following midnight.
            window_end = (start + timedelta(days=1, microseconds=-1)).isoformat().replace("+00:00", "Z")
        context = sidecar_cli._local_event_context(
            store, decision_at_utc=decision, window_start_utc=window_start,
            window_end_utc=window_end,
        )
        from forex.m1_event_sidecar import build_m1_event_context_sidecar
        sidecar = build_m1_event_context_sidecar(
            assessment, source_raw_sha256=digest, event_context=context,
            window_start_utc=window_start, window_end_utc=window_end,
        )
        target, created = sidecar_cli._publish_sidecar(output, sidecar)
    except (OSError, ValueError, TypeError, OverflowError, RuntimeError, subprocess.TimeoutExpired) as exc:
        return _refused(path, digest=digest, code=_reason(exc))
    return {"source_path": str(path), "source_raw_sha256": digest,
            "status": "ATTACHED", "sidecar_path": str(target),
            "sidecar_sha256": sidecar["sidecar_sha256"],
            "publication": "CREATED" if created else "EXISTING"}


def run_batch(*, assessment_root: Path, store: Path, output: Path,
              window_start: str | None, window_end: str | None, window_mode: str | None = None) -> dict[str, Any]:
    if window_mode not in {None, "DECISION_UTC_DAY"}:
        raise ValueError("unsupported observational window mode")
    if window_mode is not None and (window_start is not None or window_end is not None):
        raise ValueError("automatic and explicit windows cannot be combined")
    if window_mode is None and (not isinstance(window_start, str) or not isinstance(window_end, str)):
        raise ValueError("explicit window bounds are required")
    root = _trusted_directory(assessment_root, label="assessment_root")
    trusted_output = sidecar_cli._output_directory(output)
    records = [_process(path, store=store, output=trusted_output,
                        window_start=window_start, window_end=window_end, window_mode=window_mode)
               for path in _candidates(root)]
    attached = sum(record["status"] == "ATTACHED" for record in records)
    refused = sum(record["status"] == "INPUT_REFUSED" for record in records)
    return {"schema_version": REPORT_SCHEMA,
            "state": "NO_INPUTS" if not records else "COMPLETE",
            "assessment_root": str(root), "total_count": len(records),
            "attached_count": attached, "refused_count": refused,
            "records": records, "execution_authority": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assessment-root", type=Path, required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--window-start", required=True)
    parser.add_argument("--window-end", required=True)
    args = parser.parse_args(argv)
    try:
        report = run_batch(assessment_root=args.assessment_root, store=args.store,
                           output=args.output, window_start=args.window_start,
                           window_end=args.window_end)
        print(json.dumps(report, sort_keys=True, allow_nan=False))
        return 0
    except (OSError, ValueError, TypeError, OverflowError, RuntimeError) as exc:
        print("M1 event batch refused; inspect local retained assessment and sidecar state", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
