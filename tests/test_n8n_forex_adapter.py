import json
from unittest import mock

from scripts import n8n_forex_adapter


def test_fixed_m11_workflow_contract_rejects_host_command_surface(tmp_path, monkeypatch):
    path = tmp_path / "workflow.json"
    path.write_text(json.dumps({"name": n8n_forex_adapter.WORKFLOW_NAME, "active": False, "nodes": [{"type": "n8n-nodes-base.executeCommand"}]}), encoding="utf-8")
    monkeypatch.setattr(n8n_forex_adapter, "WORKFLOW_FILE", path)
    try:
        n8n_forex_adapter.workflow()
    except RuntimeError as error:
        assert "n8n-native node contract" in str(error)
    else:
        raise AssertionError("host command node was accepted")


def test_upsert_uses_the_deployed_fixed_forex_workflow_file(monkeypatch):
    class Shared:
        def shell_quote(self, value):
            return repr(value)

        def execute_remote(self, script):
            assert "n8n_m11_install.py" in script
            return {"ok": True}

        def result_json(self, result):
            return {"id": "m11-workflow"}

    monkeypatch.setattr(n8n_forex_adapter, "shared_n8n", Shared)
    result = n8n_forex_adapter.upsert(activate=False)
    assert result["workflow_id"] == "m11-workflow"
    assert result["ok"] is True


def test_recent_execution_returns_only_fixed_workflow_summary(monkeypatch):
    class Shared:
        def api_request(self, method, path):
            assert (method, path) == ("GET", "/executions?workflowId=rfIIE2BiPtppBbT2&limit=1")
            return ({"data": [{"id": "42", "status": "success", "mode": "trigger", "startedAt": "start", "stoppedAt": "stop", "workflowId": "rfIIE2BiPtppBbT2", "data": "not returned"}]}, {"ok": True})

    monkeypatch.setattr(n8n_forex_adapter, "shared_n8n", Shared)
    result = n8n_forex_adapter.recent_execution()
    assert result["execution"] == {"id": "42", "status": "success", "mode": "trigger", "startedAt": "start", "stoppedAt": "stop", "workflowId": "rfIIE2BiPtppBbT2"}
