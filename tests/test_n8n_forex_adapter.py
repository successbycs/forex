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


def test_upsert_uses_the_shared_adapter_api_without_a_remote_workflow_file(monkeypatch):
    class Shared:
        def list_workflows(self):
            return [], {}

        def workflow_api_payload(self, payload):
            return {"name": payload["name"], "nodes": payload["nodes"], "connections": payload["connections"], "settings": payload["settings"]}

        def api_request(self, method, path, payload):
            assert method == "POST"
            assert path == "/workflows"
            assert payload["name"] == n8n_forex_adapter.WORKFLOW_NAME
            return {"id": "m11-workflow"}, {"ok": True}

    monkeypatch.setattr(n8n_forex_adapter, "shared_n8n", Shared)
    result = n8n_forex_adapter.upsert(activate=False)
    assert result["workflow_id"] == "m11-workflow"
    assert result["ok"] is True
