from __future__ import annotations

import copy

import pytest

from forex.execution_work_projection import ProjectionError, render, validate


def plan():
    return {"schema_version":"forex.execution-work.v1","task_id":"H5","authorization":"test","markdown_plan":"docs/plans/test.md","items":[
        {"id":"one","title":"First item","state":"DONE","requires":[],"evidence":["ok"],"blocker":None},
        {"id":"two","title":"Second item","state":"PENDING","requires":["one"],"evidence":[],"blocker":None},
    ]}


def test_renderer_is_deterministic_and_validates_exact_projection():
    value = plan(); block = render(value)
    assert render(copy.deepcopy(value)) == block
    assert validate(value, "before\n" + block + "\nafter", work_plan_bytes=b"{}") ["status"] == "CONSISTENT"


@pytest.mark.parametrize("mutator", [
    lambda block: block.replace("state=DONE", "state=PENDING", 1),
    lambda block: block.replace("First item", "Altered title"),
    lambda block: block.replace("<!-- forex-work-item id=two", "<!-- forex-work-item id=three"),
    lambda block: block.replace("<!-- forex-work-item id=one", "<!-- forex-work-item id=two", 1),
    lambda block: block.replace("<!-- forex-work-projection:end -->", ""),
])
def test_projection_rejects_state_title_id_order_and_marker_drift(mutator):
    with pytest.raises(ProjectionError): validate(plan(), mutator(render(plan())))


def test_projection_rejects_missing_or_duplicate_blocks():
    with pytest.raises(ProjectionError): validate(plan(), "- [x] plausible checklist")
    block = render(plan())
    with pytest.raises(ProjectionError): validate(plan(), block + "\n" + block)
