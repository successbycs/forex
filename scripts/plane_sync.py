#!/usr/bin/env python3
"""Validate the offline Plane integration contract; never contacts Plane."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from forex.plane_sync import PlaneSyncError, load_contract, load_task_ids, offline_report  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    try:
        contract = load_contract(ROOT / "config/plane_sync.json")
        task_source = (ROOT / contract["task_source"]).resolve()
        if not task_source.is_relative_to(ROOT.resolve()):
            raise PlaneSyncError("contract task source escapes repository")
        print(json.dumps(offline_report(contract, load_task_ids(task_source)), sort_keys=True))
    except PlaneSyncError as exc:
        print(f"FOREX_PLANE_SYNC_REFUSED: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
