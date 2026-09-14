"""Validated selection of the one active repository execution-work record."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


class ExecutionSelectionError(ValueError):
    """The active execution selector cannot safely identify one work record."""


@dataclass(frozen=True)
class ActiveExecutionWork:
    task_id: str
    work_plan: Path


def _pairs(items: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in items:
        if key in result:
            raise ExecutionSelectionError("active execution selector has duplicate fields")
        result[key] = value
    return result


def load_active_execution_work(root: Path) -> ActiveExecutionWork:
    """Resolve the tracked selector to one JSON work record below docs/plans."""
    root = root.resolve()
    selector_path = root / "config" / "execution-continuation.json"
    try:
        raw = json.loads(selector_path.read_bytes(), object_pairs_hook=_pairs,
                         parse_constant=lambda _value: (_ for _ in ()).throw(ExecutionSelectionError("nonfinite selector value")))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExecutionSelectionError("active execution selector is unavailable") from exc
    if not isinstance(raw, dict) or set(raw) != {"schema_version", "task_id", "work_plan"}:
        raise ExecutionSelectionError("active execution selector is invalid")
    task_id, relative = raw.get("task_id"), raw.get("work_plan")
    if raw.get("schema_version") != "forex.active-execution-work.v1" or not isinstance(task_id, str) or not task_id:
        raise ExecutionSelectionError("active execution selector is invalid")
    if not isinstance(relative, str) or Path(relative).is_absolute():
        raise ExecutionSelectionError("active execution work plan is unsafe")
    unresolved_work_plan = root / relative
    if unresolved_work_plan.is_symlink():
        raise ExecutionSelectionError("active execution work plan is unsafe")
    work_plan = unresolved_work_plan.resolve()
    plan_root = (root / "docs" / "plans").resolve()
    if work_plan.suffix != ".json" or not work_plan.is_relative_to(plan_root):
        raise ExecutionSelectionError("active execution work plan is unsafe")
    try:
        from forex.execution_work_projection import ProjectionError, validate
        plan = json.loads(work_plan.read_bytes(), object_pairs_hook=_pairs)
        if not isinstance(plan, dict) or plan.get("task_id") != task_id:
            raise ExecutionSelectionError("active execution task binding is invalid")
        markdown_relative = plan.get("markdown_plan") if isinstance(plan, dict) else None
        if not isinstance(markdown_relative, str) or Path(markdown_relative).is_absolute():
            raise ExecutionSelectionError("active execution projection is invalid")
        unresolved_markdown = root / markdown_relative
        if unresolved_markdown.is_symlink():
            raise ExecutionSelectionError("active execution projection is unsafe")
        markdown = unresolved_markdown.resolve()
        if not markdown.is_relative_to(plan_root) or markdown.is_symlink() or not markdown.is_file():
            raise ExecutionSelectionError("active execution projection is unsafe")
        validate(plan, markdown.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ProjectionError, ValueError) as exc:
        raise ExecutionSelectionError("active execution projection is invalid") from exc
    return ActiveExecutionWork(task_id=task_id, work_plan=work_plan)
