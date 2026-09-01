import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_m11_r1_is_one_flat_hourly_native_workflow_without_host_or_subworkflow_surface():
    workflow = json.loads((ROOT / "n8n/forex-gdelt-daily.json").read_text(encoding="utf-8"))
    rendered = json.dumps(workflow).lower()
    nodes = {node["name"]: node for node in workflow["nodes"]}

    assert workflow["active"] is False
    assert "n8n-nodes-base.scheduletrigger" in rendered
    assert "n8n-nodes-base.httprequest" in rendered
    assert "n8n-nodes-base.compression" in rendered
    assert "n8n-nodes-base.postgres" in rendered
    assert "n8n-nodes-base.executecommand" not in rendered
    assert "n8n-nodes-base.executeworkflow\"" not in rendered
    assert "https://data.gdeltproject.org/gdeltv2/lastupdate.txt" not in rendered
    assert nodes["Schedule after UTC hour closes"]["parameters"]["rule"]["interval"][0]["expression"] == "5 * * * *"
    assert nodes["Download GKG ZIP"]["parameters"]["options"]["response"]["response"] == {
        "neverError": False, "responseFormat": "file", "outputPropertyName": "data"
    }


def test_m11_r1_uses_last_closed_hour_and_exactly_four_sources_with_no_article_fields():
    workflow = json.loads((ROOT / "n8n/forex-gdelt-daily.json").read_text(encoding="utf-8"))
    nodes = {node["name"]: node for node in workflow["nodes"]}
    build = nodes["Build four closed-hour GKG URLs"]["parameters"]["jsCode"]
    aggregate = nodes["Aggregate one closed hour of context"]["parameters"]["jsCode"]

    assert "getUTCHours()-1" in build
    assert "[0,15,30,45]" in build
    assert "payload_sha256" in aggregate
    assert "require('crypto').createHash" in aggregate
    assert "getBinaryDataBuffer(i,'file_0')" in aggregate
    assert "article_text" not in aggregate
    assert "headline" not in aggregate


def test_m11_r1_persists_four_source_records_before_the_stage_handoff():
    download = json.loads((ROOT / "n8n/forex-gdelt-daily.json").read_text(encoding="utf-8"))
    importer = json.loads((ROOT / "n8n/forex-gdelt-hourly-import.json").read_text(encoding="utf-8"))
    stage_query = next(node for node in download["nodes"] if node["id"] == "stage")["parameters"]["query"]
    import_query = next(node for node in importer["nodes"] if node["id"] == "import-staged-hour")["parameters"]["query"]

    assert "persisted_sources AS (INSERT INTO forex.raw_observation" in stage_query
    assert "INSERT INTO forex.gdelt_hourly_stage" in stage_query
    assert "inserted_sources" not in import_query
    assert "INSERT INTO forex.gdelt_h1_aggregate" in import_query


def test_m11_r1_import_workflow_is_independent_and_has_no_subworkflow_or_host_surface():
    workflow = json.loads((ROOT / "n8n/forex-gdelt-hourly-import.json").read_text(encoding="utf-8"))
    rendered = json.dumps(workflow).lower()

    assert workflow["active"] is False
    assert "n8n-nodes-base.postgres" in rendered
    assert "n8n-nodes-base.executeworkflow" not in rendered
    assert "n8n-nodes-base.executecommand" not in rendered
    assert "gdelt_hourly_stage" in rendered
