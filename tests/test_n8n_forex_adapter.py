import json
from unittest import mock

from scripts import n8n_forex_adapter, n8n_m11_install


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


def test_evidence_run_uses_only_the_fixed_runner_id(monkeypatch):
    class Shared:
        def shell_quote(self, value):
            return repr(value)

        def execute_remote(self, script):
            assert "n8n execute --id='runner-fixed' --rawOutput" in script
            return {"ok": True}

    monkeypatch.setattr(n8n_forex_adapter, "shared_n8n", Shared)
    monkeypatch.setattr(n8n_forex_adapter, "upsert", lambda activate: {"workflow_id": "m11-fixed", "evidence_runner_workflow_id": "runner-fixed"})
    assert n8n_forex_adapter.evidence_run()["ok"] is True


def test_evidence_runner_uses_a_fixed_resource_reference():
    runner = n8n_m11_install.evidence_runner_payload("child-fixed")
    child = runner["nodes"][1]["parameters"]["workflowId"]
    assert child == {"__rl": True, "value": "child-fixed", "mode": "list", "cachedResultName": n8n_m11_install.NAME}
