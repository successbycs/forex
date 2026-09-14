#!/usr/bin/env python3
"""Report repository task/evidence/blocker status without changing any state."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from forex.delivery_harness import DeliveryHarnessError, harness_status  # noqa: E402


def _json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must be a JSON object")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="repository root to inspect")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        report = harness_status(
            task_plan=_json(root / "docs/milestones/active-delivery-tasks.json"),
            state=_json(root / "project_state.json"),
            registry=_json(root / "milestone_registry.json"),
            history=_json(root / "runs/run_history.json"),
        )
    except (OSError, ValueError, json.JSONDecodeError, DeliveryHarnessError) as exc:
        print(f"FOREX_DELIVERY_HARNESS_REFUSED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
