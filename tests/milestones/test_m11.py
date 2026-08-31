import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_m11_n8n_workflow_is_daily_native_and_has_no_python_or_host_command_surface():
    workflow = json.loads((ROOT / "n8n/forex-gdelt-daily.json").read_text(encoding="utf-8"))
    rendered = json.dumps(workflow).lower()
    nodes = {node["name"]: node for node in workflow["nodes"]}

    assert workflow["active"] is False
    assert "n8n-nodes-base.scheduletrigger" in rendered
    assert "n8n-nodes-base.httprequest" in rendered
    assert "n8n-nodes-base.compression" in rendered
    assert "n8n-nodes-base.postgres" in rendered
    assert "n8n-nodes-base.executecommand" not in rendered
    assert "https://data.gdeltproject.org/gdeltv2/lastupdate.txt" not in rendered
    assert "Build prior-day GKG URLs" in nodes
    assert "Persist GDELT H1 context" in nodes
    assert workflow["nodes"][0]["type"] == "n8n-nodes-base.executeWorkflowTrigger"
    assert nodes["Download GKG ZIP"]["parameters"]["options"]["response"]["response"] == {
        "neverError": False,
        "responseFormat": "file",
        "outputPropertyName": "data",
    }
    assert "gdelt_h1_aggregate" in rendered
    assert "article text" in rendered
    assert "order" in rendered


def test_m11_workflow_builds_all_96_prior_day_intervals_and_retains_no_article_fields():
    workflow = json.loads((ROOT / "n8n/forex-gdelt-daily.json").read_text(encoding="utf-8"))
    code = next(node["parameters"]["jsCode"] for node in workflow["nodes"] if node["name"] == "Build prior-day GKG URLs")
    aggregate_code = next(node["parameters"]["jsCode"] for node in workflow["nodes"] if node["name"] == "Aggregate permitted GKG context")

    assert "minuteOfDay < 24 * 60" in code
    assert "minuteOfDay += 15" in code
    assert " + '00'" not in code
    assert "payload_sha256" in aggregate_code
    assert "crypto.subtle.digest" in aggregate_code
    assert "require('crypto')" not in aggregate_code
    assert "article_text" not in aggregate_code
    assert "headline" not in aggregate_code
