from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_only_harness_task_source_instructs_current_selection():
    status = (ROOT / "docs/milestones/autonomous-delivery-status.md").read_text(encoding="utf-8")
    prompt = (ROOT / "docs/prompts/autonomous-delivery.md").read_text(encoding="utf-8")
    assert "python3 scripts/delivery_harness_status.py" in status
    assert "python3 scripts/autonomous_delivery_queue.py" not in status
    assert "Historical W1–W3 scheduling rule — superseded" in status
    assert "active-delivery-tasks.json" in prompt
    assert "Historical W1–W3 critical strategy delivery amendment — superseded" in prompt
