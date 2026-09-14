#!/usr/bin/env python3
"""Retain supplied BLS response bytes and append locally observed revisions.

This command is the Forex storage boundary for a source collector, not a
network transport. It neither downloads data nor authenticates a caller's
capture timestamp. Existing raw captures are never replaced.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from forex.bls_events import FAMILIES
from forex.event_capture_store import EventCaptureStoreError, retain_bls_capture


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Retained original BLS HTML response")
    parser.add_argument("--store", type=Path, required=True, help="Machine-local capture directory")
    parser.add_argument("--capture-id", required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--family", choices=sorted(FAMILIES))
    source.add_argument("--monthly-url", help="Official BLS YYYY/MM_sched_list.htm source URL")
    parser.add_argument("--capture-completed-at", required=True)
    parser.add_argument("--resume", action="store_true",
                        help="Resume the exact existing request; never replace captured bytes")
    args = parser.parse_args()
    try:
        capture = retain_bls_capture
        if args.resume:
            from forex.event_capture_recovery import resume_bls_capture
            capture = resume_bls_capture
        retained = capture(args.store, capture_id=args.capture_id,
            raw=args.input.read_bytes(), source_family="BLS_MONTHLY" if args.monthly_url else args.family,
            capture_completed_at_utc=args.capture_completed_at, source_url=args.monthly_url)
        print(json.dumps({"schema_version": "forex.bls-capture-command.v1",
            "capture_id": retained["capture_id"],
            "raw_capture_sha256": retained["raw_capture_sha256"],
            "journal_sha256": retained["journal"]["journal_sha256"],
            "capture_count": len(retained["journal"]["captures"]),
            "revision_count": len(retained["journal"]["records"]),
            "parser_quarantined": retained["parser_result"]["quarantined"],
            "coverage_status": "UNKNOWN",
            "capture_provenance": "CALLER_SUPPLIED_NOT_AUTHENTICATED",
            "execution_authority": False}, sort_keys=True, allow_nan=False))
    except (OSError, ValueError, TypeError, OverflowError, EventCaptureStoreError) as exc:
        print(f"BLS capture refused: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
