#!/usr/bin/env python3
"""Qualify retained event metadata and emit decision-time context as JSON.

Input is a JSON array in forex.event_quality's metadata format. This command
does not fetch publishers or certify source authenticity or calendar coverage.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from forex.event_annotations import event_annotation
from forex.event_quality import qualify_events


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError(f"nonfinite JSON constant: {value}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path)
    source.add_argument("--store", type=Path, help="Verified local BLS capture store")
    parser.add_argument("--decision-at", required=True)
    parser.add_argument("--window-start", required=True)
    parser.add_argument("--window-end", required=True)
    args = parser.parse_args()
    try:
        if args.store is not None:
            from forex.event_capture_store import read_capture_store
            retained_store = read_capture_store(args.store)
            journal = retained_store["journal"]
            records = journal["records"]
            cutoff = datetime.fromisoformat(args.decision_at.replace("Z", "+00:00"))
            if cutoff.tzinfo is None:
                raise ValueError("decision cutoff must include a timezone")
            provenance = {
                "schema_version": "forex.event-store-context-report.v1",
                "journal_sha256": journal["journal_sha256"],
                "capture_provenance": "CALLER_SUPPLIED_NOT_AUTHENTICATED",
                "store_health_scope": "CURRENT_RETAINED_STATE_NOT_DECISION_TIME",
                "store_isolated_captures": retained_store["isolated_captures"],
                "capture_quarantine": [{"capture_id": item["capture_id"],
                    "quarantined": item["content"]["quarantined"]}
                    for item in journal["captures"]
                    if datetime.fromisoformat(item["capture_completed_at_utc"].replace("Z", "+00:00")) <= cutoff
                    and item["content"]["quarantined"]],
            }
        else:
            raw = args.input.read_bytes()
            records = json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
            if not isinstance(records, list) or not all(isinstance(row, dict) for row in records):
                raise ValueError("input must be a JSON array of event metadata objects")
            provenance = {"schema_version": "forex.event-context-report.v1",
                          "input_sha256": "sha256:" + hashlib.sha256(raw).hexdigest()}
        qualified = qualify_events(records, args.decision_at)
        annotation = event_annotation(
            qualified, decision_at_utc=args.decision_at,
            window_start_utc=args.window_start, window_end_utc=args.window_end,
        )
        result = {
            **provenance,
            "input_record_count": len(records),
            "qualification": qualified,
            "annotation": annotation,
            "execution_authority": False,
        }
        print(json.dumps(result, sort_keys=True, allow_nan=False))
    except (OSError, ValueError, TypeError, OverflowError, RuntimeError) as exc:
        print(f"Event context refused: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
