#!/usr/bin/env python3
"""Parse a retained BLS HTML capture into annotated event context.

Capture time is supplied explicitly; a file modification time is not source
availability. Original response bytes are hashed separately from parsed text.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from forex.bls_events import FAMILIES, parse_bls_schedule_html
from forex.event_quality import qualify_events
from forex.event_annotations import event_annotation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--family", choices=sorted(FAMILIES), required=True)
    parser.add_argument("--capture-completed-at", required=True)
    parser.add_argument("--decision-at", required=True)
    parser.add_argument("--window-start", required=True)
    parser.add_argument("--window-end", required=True)
    args = parser.parse_args()
    try:
        raw = args.input.read_bytes()
        parsed = parse_bls_schedule_html(raw.decode("utf-8-sig"),
            capture_completed_at_utc=args.capture_completed_at,
            source_url="https://www.bls.gov" + FAMILIES[args.family]["path"],
            source_family=args.family)
        qualified = qualify_events(parsed["records"], args.decision_at)
        annotation = event_annotation(qualified, decision_at_utc=args.decision_at,
            window_start_utc=args.window_start, window_end_utc=args.window_end)
        print(json.dumps({"schema_version": "forex.bls-retained-context.v1",
            "raw_capture_sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
            "capture_provenance": "CALLER_SUPPLIED_NOT_AUTHENTICATED",
            "parser_result": parsed, "qualification": qualified, "annotation": annotation,
            "execution_authority": False}, sort_keys=True, allow_nan=False))
    except (OSError, ValueError, TypeError) as exc:
        print(f"BLS retained context refused: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
