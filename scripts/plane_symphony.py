#!/usr/bin/env python3
"""Read local H5 controller status/preflight; Plane and Codex adapters are deployment-owned."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from forex.plane_symphony import (  # noqa: E402
    PlaneSymphonyError, load_config, load_json, status_report, validate_task_catalog,
)


def _loaded() -> tuple[object, object]:
    config = load_config(ROOT / "config" / "plane_symphony.json")
    tasks = validate_task_catalog(load_json(ROOT / "docs/milestones/active-delivery-tasks.json"))
    return config, tasks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("preflight", "sync-once", "run-once", "status"))
    args = parser.parse_args(argv)
    try:
        config, tasks = _loaded()
        if args.operation == "status":
            print(json.dumps(status_report(config, tasks), sort_keys=True))
            return 0
        if args.operation == "preflight":
            print(json.dumps({"status": "LOCAL_POLICY_VALID", "execution_authority": False}, sort_keys=True))
            return 0
        raise PlaneSymphonyError("Plane/Codex transport is deployment-owned; this local CLI refuses side effects")
    except PlaneSymphonyError as exc:
        print(f"FOREX_PLANE_SYMPHONY_REFUSED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
