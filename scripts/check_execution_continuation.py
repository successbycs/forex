#!/usr/bin/env python3
"""Report a read-only advisory continuation decision for an execution-work plan."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def _reject_nonfinite(value: str) -> None:
    raise ValueError("nonfinite JSON constant")


def _read_plan(path: Path) -> tuple[object, bytes]:
    raw = path.read_bytes()
    return json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_reject_nonfinite), raw


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-plan", type=Path, default=ROOT / "docs/plans/a1-execution-work.json")
    args = parser.parse_args(argv)
    try:
        from forex.execution_continuation import ExecutionWorkError, evaluate_work_plan
        from forex.execution_work_projection import validate

        plan, raw = _read_plan(args.work_plan)
        if not isinstance(plan, dict):
            raise ValueError("work plan is invalid")
        markdown = (ROOT / plan.get("markdown_plan", "")).resolve()
        validate(plan, markdown.read_text(encoding="utf-8"))
        report = evaluate_work_plan(plan, work_plan_sha256="sha256:" + hashlib.sha256(raw).hexdigest())
    except (ExecutionWorkError, OSError, OverflowError, RecursionError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"execution continuation refused: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return 1 if report["outcome"] == "CONTINUE" else 0


if __name__ == "__main__":
    raise SystemExit(main())
