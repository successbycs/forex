#!/usr/bin/env python3
"""Report the next safe independent delivery package; makes no state changes."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from forex.autonomous_delivery import DeliveryQueueError, select_next  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit machine-readable selection")
    args = parser.parse_args()
    try:
        queue = json.loads((ROOT / "docs/milestones/autonomous-delivery-queue.json").read_text(encoding="utf-8"))
        state = json.loads((ROOT / "project_state.json").read_text(encoding="utf-8"))
        selection = select_next(queue, state)
    except (OSError, json.JSONDecodeError, DeliveryQueueError) as exc:
        raise SystemExit(f"FOREX_AUTONOMOUS_DELIVERY_QUEUE_REFUSED: {exc}") from exc
    if args.json:
        print(json.dumps(selection, sort_keys=True))
    elif selection["next_package"] is None:
        print("FOREX_AUTONOMOUS_DELIVERY_QUEUE_NO_SAFE_PACKAGE")
    else:
        package = selection["next_package"]
        print(f"FOREX_AUTONOMOUS_DELIVERY_NEXT_PACKAGE: {package['id']} — {package['title']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
