#!/usr/bin/env python3
"""Emit canonical facts from one receipt-verified n8n BLS retained store."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from forex.bls_n8n_projection import BLSN8nProjectionError, project_verified_n8n_bls_store  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, required=True, help="explicit retained BLS store root")
    parser.add_argument("--workflow-id", required=True, help="fixed local workflow identity expected in receipts")
    parser.add_argument("--workflow-sha256", required=True, help="fixed local workflow artifact digest expected in receipts")
    parser.add_argument("--persist", action="store_true", help="use the existing fixed T480 PostgreSQL writer after verification")
    args = parser.parse_args(argv)
    try:
        projector = lambda root: project_verified_n8n_bls_store(
            root, expected_workflow_id=args.workflow_id, expected_workflow_sha256=args.workflow_sha256)
        projection = projector(args.store)
        if args.persist:
            sys.path.insert(0, str(ROOT / "scripts"))
            from persist_bls_retained_calendar_facts import persist_store
            result = persist_store(args.store, projector=projector)
        else:
            result = projection
        print(json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False))
    except (BLSN8nProjectionError, OSError, ValueError) as exc:
        print(f"n8n BLS retained projection refused: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
