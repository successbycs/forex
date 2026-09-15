#!/usr/bin/env python3
"""Read-only Codex Stop hook; requests at most one corrective pass per turn."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from check_execution_continuation import _read_plan, _unique_object, _reject_nonfinite
from forex.execution_continuation import evaluate_work_plan
from forex.execution_selection import load_active_execution_work


def response(event: dict, root: Path = ROOT) -> dict:
    if event.get("hook_event_name") not in {"Stop", "SubagentStop"}:
        return {}
    if event.get("permission_mode") == "plan":
        return {}
    cwd = event.get("cwd", str(root))
    if not isinstance(cwd, str) or not Path(cwd).resolve().is_relative_to(root.resolve()):
        return {}
    if type(event.get("stop_hook_active", False)) is not bool:
        raise ValueError("invalid stop_hook_active")
    selection = load_active_execution_work(root)
    task_id, work_plan = selection.task_id, selection.work_plan
    plan, raw = _read_plan(work_plan)
    if not isinstance(plan, dict) or plan.get("task_id") != task_id:
        raise ValueError("active execution task binding is invalid")
    report = evaluate_work_plan(plan, work_plan_sha256="sha256:" + hashlib.sha256(raw).hexdigest())
    if report["outcome"] != "CONTINUE":
        return {}
    if event.get("stop_hook_active", False):
        return {"decision": "block", "reason": "The active Forex ExecPlan still reports actionable authorised work. Continue the recorded next item or record a concrete terminal blocker; do not emit a progress-only final answer."}
    return {"decision": "block", "reason": (
        "Before ending, reconcile the latest user instruction with PLANS.md. "
        "If the user paused, cancelled, or requested only an answer/review, honour that and finish that request; do not expand scope. "
        "For the authorised A1 execution, the recorded next item is "
        + report["next_item"]["id"] + ": " + report["next_item"]["title"] + ". "
        "Continue actionable in-scope work through checks, repair and review. "
        "A blocked deployment alone does not justify stopping independent preparation. "
        "Reconcile stale records against actual evidence; never mark work done just to bypass this check. "
        "This hook grants no authority and does not clear platform constraints."
    )}


def main() -> int:
    try:
        raw = sys.stdin.buffer.read(65537)
        if len(raw) > 65536:
            raise ValueError("hook input too large")
        event = json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_reject_nonfinite)
        if not isinstance(event, dict):
            raise ValueError("hook input must be an object")
        result = response(event)
    except (OSError, ValueError, TypeError, RecursionError) as exc:
        # Invalid records never silently claim completion; avoid infinite loops
        # when the very guard needs repair. No transcript or secret is logged.
        result = {"decision": "block", "reason": "Forex continuation projection is invalid; repair the work record and run the checker before ending this execution turn."}
    print(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
