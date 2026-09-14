"""Deterministic, read-only JSON execution-work to Markdown projection checks."""
from __future__ import annotations

from hashlib import sha256
import re
from typing import Any

from forex.execution_continuation import validate_work_plan

SCHEMA = "forex.execution-work-projection.v1"
_START = re.compile(r"^<!-- forex-work-projection:start task=([A-Z][A-Z0-9_-]{0,63}) schema=forex\.execution-work-projection\.v1 -->$")
_ITEM = re.compile(r"^<!-- forex-work-item id=([a-z][a-z0-9-]{0,127}) state=(PENDING|IN_PROGRESS|IN_REVIEW|BLOCKED|DONE) -->$")
_END = "<!-- forex-work-projection:end -->"

class ProjectionError(ValueError): pass

def render(plan: object) -> str:
    items = validate_work_plan(plan)
    assert isinstance(plan, dict)
    lines = [f"<!-- forex-work-projection:start task={plan['task_id']} schema={SCHEMA} -->"]
    for item in items:
        state = item["state"]; mark = "x" if state == "DONE" else " "
        lines += [f"<!-- forex-work-item id={item['id']} state={state} -->", f"- [{mark}] {item['id']} — {item['title']} ({state})"]
    return "\n".join(lines + [_END])

def validate(plan: object, markdown: str, *, work_plan_bytes: bytes | None = None) -> dict[str, str]:
    expected = render(plan)
    blocks = re.findall(r"<!-- forex-work-projection:start[\s\S]*?<!-- forex-work-projection:end -->", markdown)
    if len(blocks) != 1: raise ProjectionError("PROJECTION_BLOCK_COUNT")
    actual = blocks[0]
    if actual != expected: raise ProjectionError("PROJECTION_MISMATCH")
    assert isinstance(plan, dict)
    source = work_plan_bytes if work_plan_bytes is not None else json_bytes(plan)
    return {"status":"CONSISTENT","task_id":plan["task_id"],"work_plan_sha256":"sha256:"+sha256(source).hexdigest(),"markdown_sha256":"sha256:"+sha256(markdown.encode()).hexdigest()}

def json_bytes(plan: object) -> bytes:
    import json
    return json.dumps(plan, sort_keys=True, separators=(",", ":")).encode()
