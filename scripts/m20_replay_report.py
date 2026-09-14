#!/usr/bin/env python3
"""Emit a read-only retained-M20 replay report as JSON on standard output."""
from __future__ import annotations

import argparse
import json
import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from forex.m20_replay_report import ReplayReportInputError, load_and_build_replay_report, build_replay_report
from forex.m20_retained_export import RetainedExportInputError, load_and_adapt_retained_m20_export


def event_sidecar_status(assessment, *, source_sha256, store, sidecars, start, end):
    """Read-only join; missing/invalid annotations never change replay decisions."""
    from m1_event_sidecar import _full_decision, _local_event_context, _output_directory, _strict_json
    from forex.m1_event_sidecar import build_m1_event_context_sidecar
    try:
        directory = _output_directory(Path(sidecars))
        decision = _full_decision(assessment, source_sha256)
        context = _local_event_context(Path(store), decision_at_utc=decision,
                                       window_start_utc=start, window_end_utc=end)
        expected = build_m1_event_context_sidecar(assessment, source_raw_sha256=source_sha256,
            event_context=context, window_start_utc=start, window_end_utc=end)
        path = directory / (expected["sidecar_sha256"].removeprefix("sha256:") + ".json")
        base = {"expected_sidecar_sha256": expected["sidecar_sha256"], "execution_authority": False,
                "scope": "EXACT_SOURCE_CURRENT_VERIFIED_JOURNAL_AND_EXPLICIT_WINDOW"}
        if not path.exists() and not path.is_symlink():
            return {**base, "status": "MISSING", "reason": "no sidecar for this exact source, journal and window"}
        if path.is_symlink() or not path.is_file() or _strict_json(path.read_bytes()) != expected:
            return {**base, "status": "INVALID", "reason": "stored sidecar differs from independently rebuilt context"}
        return {**base, "status": "ATTACHED", "annotation": expected["event_annotation"]}
    except (OSError, ValueError, TypeError, OverflowError, RuntimeError, subprocess.TimeoutExpired) as exc:
        return {"status": "UNAVAILABLE", "reason": type(exc).__name__, "execution_authority": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="local JSON document containing retained snapshot/proposal records")
    parser.add_argument("--retained-export", action="store_true", help="adapt a fixed M20 operation, lifecycle or lineage export")
    parser.add_argument("--event-store", type=Path)
    parser.add_argument("--event-sidecars", type=Path)
    parser.add_argument("--event-window-start")
    parser.add_argument("--event-window-end")
    arguments = parser.parse_args(argv)
    options = [arguments.event_store, arguments.event_sidecars, arguments.event_window_start, arguments.event_window_end]
    if any(item is not None for item in options) and (not all(item is not None for item in options) or not arguments.retained_export):
        parser.error("event joins require --retained-export and all four --event-* options")
    try:
        if arguments.retained_export:
            from forex.m20_retained_export import _strict_json, adapt_retained_m20_export
            path = Path(arguments.input).resolve(strict=True)
            raw = path.read_bytes()
            assessment = _strict_json(raw)
            source_sha = "sha256:" + hashlib.sha256(raw).hexdigest()
            document = adapt_retained_m20_export(assessment, source_sha256=source_sha, source_path=str(path))
            provenance = document["provenance"]
            report = build_replay_report(document, source_sha256=provenance["source_sha256"],
                                         source_path=provenance["source_path"])
            report["retained_export_coverage"] = document["retained_export_coverage"]
            report["coverage_only_records"] = document["coverage_only_records"]
            if arguments.event_store is not None:
                report["event_context_sidecar"] = event_sidecar_status(assessment, source_sha256=source_sha,
                    store=arguments.event_store, sidecars=arguments.event_sidecars,
                    start=arguments.event_window_start, end=arguments.event_window_end)
        else:
            report = load_and_build_replay_report(arguments.input)
    except (ReplayReportInputError, RetainedExportInputError, OSError) as exc:
        print(f"m20 replay report: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
