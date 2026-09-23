#!/usr/bin/env python3
"""Retain an additive M31 refusal-window evaluation; never amend raw evidence."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from forex.m31_supplement import evaluate_no_trade_supplement, verify_original_hashes
from forex.m31_scorecard import render_terminal


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original-bundle", required=True, type=Path)
    parser.add_argument("--enriched-completeness", required=True, type=Path)
    parser.add_argument("--historical-reference", required=True, type=Path)
    parser.add_argument("--output-directory", required=True, type=Path)
    args = parser.parse_args()
    sources = {"protocol_raw": args.original_bundle / "protocol.json",
               "receipt_raw": args.original_bundle / "protocol-receipt.json",
               "original_raw": args.original_bundle / "completeness.json",
               "enriched_raw": args.enriched_completeness,
               "lifecycle_raw": args.original_bundle / "lifecycle.json",
               "broker_raw": args.original_bundle / "broker-history.json",
               "historical_raw": args.historical_reference}
    try:
        if args.output_directory.exists():
            raise ValueError("output directory exists; refusing overwrite")
        original = verify_original_hashes(args.original_bundle)
        for path in sources.values():
            if path.is_symlink() or not path.is_file():
                raise ValueError("all inputs must be retained regular files")
        raw = {name: path.read_bytes() for name, path in sources.items()}
        report = evaluate_no_trade_supplement(**raw)
        report["original_manifest_sha256"] = "sha256:" + hashlib.sha256(original["manifest.json"]).hexdigest()
        report["evaluation_provenance"] = {
            "evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
            "git_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "worktree_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True)),
            "source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in (
                "scripts/m31_supplement.py", "src/forex/m31_supplement.py",
                "src/forex/m31_scorecard.py", "src/forex/m31_evidence.py", "src/forex/m20_history_report.py")},
        }
        report["source_paths"] = {name: str(path.resolve()) for name, path in sources.items()}
        summary = render_terminal(report["scorecard"]) + (
            "\nBroker cross-check: zero EURUSD deals in this interval."
            f"\nHistorical NO_CHANGE: {report['historical_reference']['sessions']} sessions; no exposure. H1 trading results are not an M1 benchmark."
            "\nExisting account positions and account-wide P&L are excluded, not assumed zero."
            "\nLimitation: proposal/session records do not retain an account hash for a direct broker-account join."
            "\nSupplement only: historical artifact bound after observation; formal review remains required.\n")
        args.output_directory.mkdir(parents=True)
        (args.output_directory / "evaluation.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        (args.output_directory / "summary.txt").write_text(summary)
        print(summary)
        print(f"Retained supplement: {args.output_directory}")
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"M31 supplement refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
