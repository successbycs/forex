"""V3 workflow contract: publisher bytes can enter only via local egress."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_workflow_routes_candidates_to_fixed_loopback_egress_service():
    workflow = json.loads((ROOT / "n8n/forex-gdelt-daily.json").read_text())
    nodes = {node["id"]: node for node in workflow["nodes"]}
    fetch = nodes["fetch-article"]
    assert fetch["name"] == "Fetch publisher page through bounded loopback egress"
    assert fetch["parameters"]["method"] == "POST"
    assert fetch["parameters"]["url"] == "http://gdelt-egress:8092/forex/gdelt/fetch"
    assert fetch["parameters"]["body"] == "={{ JSON.stringify($json) }}"
    assert "FOREX_GDELT_CANDIDATE_SIGNING_KEY" in nodes["expand-article-candidates"]["parameters"]["jsCode"]
    assert "createHmac" in nodes["expand-article-candidates"]["parameters"]["jsCode"]
    assert "Bearer " in fetch["parameters"]["headerParameters"]["parameters"][0]["value"]
    assert "ForexResearchContext" not in json.dumps(fetch["parameters"])
    extractor = nodes["extract-article"]["parameters"]["jsCode"]
    assert "content_base64" in extractor and "EGRESS_CONTRACT_REJECTED" in extractor
    assert "getBinaryDataBuffer" not in extractor
    connections = workflow["connections"]
    assert connections["Expand bounded publisher candidates"]["main"][0][0]["node"] == fetch["name"]
    assert fetch["name"] in connections
    settings = workflow["settings"]
    assert settings["saveExecutionProgress"] is False
    assert settings["saveManualExecutions"] is False
    assert settings["saveExecutionSuccess"] == settings["saveExecutionError"] == "none"


def test_workflow_routes_fixed_gdelt_archives_through_the_private_egress_boundary():
    workflow = json.loads((ROOT / "n8n/forex-gdelt-daily.json").read_text())
    nodes = {node["id"]: node for node in workflow["nodes"]}
    node = nodes["download"]
    assert node["parameters"]["url"] == "http://gdelt-egress:8092/forex/gdelt/archive"
    assert node["parameters"]["method"] == "POST"
    assert "FOREX_GDELT_EGRESS_BEARER" in node["parameters"]["headerParameters"]["parameters"][0]["value"]

def test_article_migration_deduplicates_only_by_content_and_never_retains_failure_body():
    migration = (ROOT / "sql/migrations/025_m11_gdelt_article_retention.sql").read_text()
    article = migration.split("CREATE TABLE IF NOT EXISTS forex.gdelt_article_url", 1)[0]
    assert "canonical_url TEXT NOT NULL UNIQUE" not in article
    assert "content_sha256 TEXT PRIMARY KEY" in article
    attempt = migration.split("CREATE TABLE IF NOT EXISTS forex.gdelt_article_retrieval_attempt", 1)[1]
    assert "title" not in attempt and "body" not in attempt
    assert "result_status IN ('RETAINED', 'FAILED')" in attempt


def test_article_receipt_targets_the_exact_inserted_attempt_not_a_latest_url_lookup():
    workflow = json.loads((ROOT / "n8n/forex-gdelt-daily.json").read_text())
    nodes = {node["id"]: node for node in workflow["nodes"]}
    persist = nodes["persist-article"]["parameters"]["query"]
    receipt = nodes["persist-egress-receipt"]["parameters"]["query"]
    assert "SELECT attempt_id FROM attempts" in persist
    assert "WHERE attempt_id={{ $json.attempt_id }}::bigint" in receipt
    assert "max(attempt_id)" not in receipt.lower()


def test_stage_conflict_is_idempotent_only_for_the_same_immutable_aggregate():
    workflow = json.loads((ROOT / "n8n/forex-gdelt-daily.json").read_text())
    stage = next(node for node in workflow["nodes"] if node["id"] == "stage")["parameters"]["query"]
    assert "conflict_guard" in stage
    assert "existing.aggregate_sha256=input.aggregate_sha256" in stage
    assert "1/0" in stage
    assert "ON CONFLICT (stage_id) DO NOTHING" in stage
