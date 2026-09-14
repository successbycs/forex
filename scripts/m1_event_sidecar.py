#!/usr/bin/env python3
"""Create one immutable, context-only M1 sidecar from retained local inputs."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON field")
        value[key] = item
    return value


def _constant(value):
    raise ValueError("nonfinite JSON value")


def _strict_json(raw: bytes | str) -> Any:
    try:
        return json.loads(raw, object_pairs_hook=_pairs, parse_constant=_constant)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid JSON") from exc


def _full_decision(assessment: Any, source_raw_sha256: str) -> str:
    """Extract a decision time only from the existing full-pair adapter."""
    from forex.m20_retained_export import adapt_retained_m20_export

    adapted = adapt_retained_m20_export(assessment, source_sha256=source_raw_sha256)
    coverage, records = adapted["retained_export_coverage"], adapted["records"]
    if (coverage.get("replayable_pair_count") != 1 or coverage.get("coverage_only_row_count") != 0
            or len(records) != 1 or not isinstance(records[0].get("proposal"), dict)):
        raise ValueError("assessment is coverage-only or lacks one retained full proposal/snapshot pair")
    decision = records[0]["proposal"].get("decision_at_utc")
    if not isinstance(decision, str):
        raise ValueError("retained proposal has no decision_at_utc")
    return decision


def _local_event_context(store: Path, *, decision_at_utc: str,
                         window_start_utc: str, window_end_utc: str) -> dict[str, Any]:
    """Run only the local read-only event-context command with fixed arguments."""
    command = [sys.executable, str(ROOT / "scripts" / "event_context.py"), "--store", str(store),
               "--decision-at", decision_at_utc, "--window-start", window_start_utc,
               "--window-end", window_end_utc]
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                               timeout=30, check=False)
    if completed.returncode != 0:
        raise ValueError("local event-context report was unavailable or invalid")
    result = _strict_json(completed.stdout)
    if not isinstance(result, dict):
        raise ValueError("local event-context output must be an object")
    return result


def _output_directory(path: Path) -> Path:
    from forex.event_capture_store import _no_symlink_ancestors
    _no_symlink_ancestors(path)
    if not path.exists() or path.is_symlink() or not path.is_dir():
        raise ValueError("output must name an existing trusted non-symlink directory")
    return path


def _publish_sidecar(directory: Path, sidecar: dict[str, Any]) -> tuple[Path, bool]:
    """Publish a digest-addressed sidecar only once, accepting exact repeats."""
    from forex.event_capture_store import CaptureConflictError, _publish_exclusive

    digest = sidecar.get("sidecar_sha256")
    if not isinstance(digest, str) or not digest.startswith("sha256:"):
        raise ValueError("sidecar has no content digest")
    payload = json.dumps(sidecar, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    target = directory / f"{digest.removeprefix('sha256:')}.json"
    if target.exists() or target.is_symlink():
        if target.is_symlink() or not target.is_file() or target.read_bytes() != payload:
            raise ValueError("existing sidecar digest path conflicts or is unsafe")
        return target, False
    try:
        _publish_exclusive(target, payload)
        return target, True
    except CaptureConflictError as exc:
        # A concurrent same-content publisher is idempotent; a different byte
        # sequence under the same digest is never overwritten or accepted.
        if target.exists() and not target.is_symlink() and target.is_file() and target.read_bytes() == payload:
            return target, False
        raise ValueError("sidecar publication conflict") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assessment", type=Path, required=True, help="Retained full assessment JSON")
    parser.add_argument("--store", type=Path, required=True, help="Verified local BLS capture store")
    parser.add_argument("--window-start", required=True)
    parser.add_argument("--window-end", required=True)
    parser.add_argument("--output", type=Path, required=True, help="Existing trusted sidecar directory")
    args = parser.parse_args(argv)
    try:
        from forex.event_capture_store import _no_symlink_ancestors
        _no_symlink_ancestors(args.assessment)
        if args.assessment.is_symlink() or not args.assessment.is_file():
            raise ValueError("assessment must be a regular retained file")
        output = _output_directory(args.output)
        raw = args.assessment.read_bytes()
        assessment = _strict_json(raw)
        source_raw_sha256 = "sha256:" + hashlib.sha256(raw).hexdigest()
        decision = _full_decision(assessment, source_raw_sha256)
        context = _local_event_context(args.store, decision_at_utc=decision,
                                       window_start_utc=args.window_start, window_end_utc=args.window_end)
        from forex.m1_event_sidecar import build_m1_event_context_sidecar
        sidecar = build_m1_event_context_sidecar(
            assessment, source_raw_sha256=source_raw_sha256, event_context=context,
            window_start_utc=args.window_start, window_end_utc=args.window_end,
        )
        target, created = _publish_sidecar(output, sidecar)
        print(json.dumps({"schema_version": "forex.m1-event-sidecar-command.v1",
                          "sidecar_path": str(target), "sidecar_sha256": sidecar["sidecar_sha256"],
                          "publication": "CREATED" if created else "EXISTING",
                          "execution_authority": False}, sort_keys=True, allow_nan=False))
        return 0
    except (OSError, ValueError, TypeError, OverflowError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f"M1 event sidecar refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
