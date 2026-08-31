import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_m11_n8n_workflow_is_daily_native_and_has_no_python_or_host_command_surface():
    workflows = [json.loads(path.read_text(encoding="utf-8")) for path in (
        ROOT / "n8n/forex-gdelt-daily.json",
        ROOT / "n8n/forex-gdelt-hourly-download.json",
        ROOT / "n8n/forex-gdelt-hourly-import.json",
    )]
    workflow = workflows[0]
    rendered = json.dumps(workflows).lower()
    nodes = {node["name"]: node for candidate in workflows for node in candidate["nodes"]}

    assert workflow["active"] is False
    assert "n8n-nodes-base.scheduletrigger" in rendered
    assert "n8n-nodes-base.httprequest" in rendered
    assert "n8n-nodes-base.compression" in rendered
    assert "n8n-nodes-base.postgres" in rendered
    assert "n8n-nodes-base.executecommand" not in rendered
    assert "https://data.gdeltproject.org/gdeltv2/lastupdate.txt" not in rendered
    assert "Build 24 closed UTC hours" in nodes
    assert "Persist hourly GDELT context" in nodes
    assert nodes["One hourly job at a time"]["parameters"]["batchSize"] == 1
    loop_outputs = workflow["connections"]["One hourly job at a time"]["main"]
    assert loop_outputs[0][0]["node"] == "Summarise daily ingestion"
    assert loop_outputs[1][0]["node"] == "Run hourly download and aggregate"
    assert nodes["M11 fixed manual execution trigger"]["type"] == "n8n-nodes-base.executeWorkflowTrigger"
    assert nodes["Download GKG ZIP"]["parameters"]["options"]["response"]["response"] == {
        "neverError": False,
        "responseFormat": "file",
        "outputPropertyName": "data",
    }
    assert "gdelt_h1_aggregate" in rendered
    assert "article text" in rendered
    assert "order" in rendered


def test_m11_workflow_builds_all_96_prior_day_intervals_and_retains_no_article_fields():
    coordinator = json.loads((ROOT / "n8n/forex-gdelt-daily.json").read_text(encoding="utf-8"))
    hourly = json.loads((ROOT / "n8n/forex-gdelt-hourly-download.json").read_text(encoding="utf-8"))
    code = next(node["parameters"]["jsCode"] for node in coordinator["nodes"] if node["name"] == "Build 24 closed UTC hours")
    aggregate_code = next(node["parameters"]["jsCode"] for node in hourly["nodes"] if node["name"] == "Aggregate one hour of context")

    assert "length: 24" in code
    assert "hour * 3600000" in code
    assert "[0, 15, 30, 45]" in json.dumps(hourly)
    assert "payload_sha256" in aggregate_code
    assert "crypto.subtle.digest" in aggregate_code
    assert "require('crypto')" not in aggregate_code
    assert "article_text" not in aggregate_code
    assert "headline" not in aggregate_code
