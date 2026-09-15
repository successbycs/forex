import json
import subprocess
import base64
from pathlib import Path

import pytest
from forex.gdelt_publisher_egress import fetch_candidate


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / "n8n" / "forex-gdelt-daily.json"
FIXTURE = ROOT / "tests" / "fixtures" / "gdelt_v2_context_rows.tsv"


def _node_source(node_id: str) -> str:
    workflow = json.loads(WORKFLOW.read_text(encoding="utf-8"))
    return next(node for node in workflow["nodes"] if node["id"] == node_id)["parameters"]["jsCode"]


def run_exact_aggregate(files, *, hours=None, hashes=None, revisions=None):
    """Evaluate the literal n8n Code-node source with its binary helper surface."""
    hour = "2026-09-14T21:00:00.000Z"
    payload = {
        "source": _node_source("aggregate"),
        "items": [
            {
                "json": {
                    "id": f"gdelt-gkg-v2-2026091421{(0, 15, 30, 45)[index]:02d}00",
                    "rev": (revisions or [f"2026091421{minute:02d}00.gkg.csv.zip" for minute in (0, 15, 30, 45)])[index],
                    "hour": (hours or [hour] * len(files))[index],
                    "observed": f"2026-09-14T21:{index}0:00.000Z",
                    "available": f"2026-09-14T21:{index + 1}0:00.000Z",
                    "archive_sha256": (hashes or [f"sha256:{index + 1:064x}" for index in range(len(files))])[index],
                },
                "binary": {"file_0": content},
            }
            for index, content in enumerate(files)
        ],
    }
    runner = r'''
const vm=require('vm'); let input=''; process.stdin.on('data',c=>input+=c); process.stdin.on('end',async()=>{
  const payload=JSON.parse(input);
  const items=payload.items.map(item=>({json:item.json,binary:{file_0:Buffer.from(item.binary.file_0,'base64')}}));
  const context={$input:{all:()=>items},URL,require,helpers:{getBinaryDataBuffer:async(index,key)=>items[index].binary[key]}};
  try { const value=await vm.runInNewContext('(async function(){'+payload.source+'}).call(this)',context); process.stdout.write(JSON.stringify({ok:true,value})); }
  catch(error) { process.stdout.write(JSON.stringify({ok:false,error:error.message})); }
});
'''
    encoded = {
        **payload,
        "items": [
            {**item, "binary": {"file_0": base64.b64encode(item["binary"]["file_0"]).decode()}}
            for item in payload["items"]
        ],
    }
    result = subprocess.run(["node", "-e", runner], input=json.dumps(encoded), text=True, capture_output=True, check=True)
    response = json.loads(result.stdout)
    if not response["ok"]:
        raise RuntimeError(response["error"])
    return response["value"]


def run_exact_zip_hash(content: bytes):
    """Evaluate the literal n8n ZIP-hash Code-node source."""
    payload = {
        "source": _node_source("hash-zip"),
        "items": [{"json": {"id": "gdelt-gkg-v2-fixture"}, "binary": {"data": base64.b64encode(content).decode()}}],
    }
    runner = r'''
const vm=require('vm'); let input=''; process.stdin.on('data',c=>input+=c); process.stdin.on('end',async()=>{
  const payload=JSON.parse(input);
  const items=payload.items.map(item=>({json:item.json,binary:{data:Buffer.from(item.binary.data,'base64')}}));
  const context={$input:{all:()=>items},require,helpers:{getBinaryDataBuffer:async(index,key)=>items[index].binary[key]}};
  try { const value=await vm.runInNewContext('(async function(){'+payload.source+'}).call(this)',context); process.stdout.write(JSON.stringify({ok:true,value})); }
  catch(error) { process.stdout.write(JSON.stringify({ok:false,error:error.message})); }
});
'''
    response = json.loads(subprocess.run(["node", "-e", runner], input=json.dumps(payload), text=True, capture_output=True, check=True).stdout)
    if not response["ok"]:
        raise RuntimeError(response["error"])
    return response["value"]


def _fixture_files():
    data = FIXTURE.read_bytes()
    return [data] * 4


def test_exact_n8n_zip_hash_node_hashes_original_binary_bytes_and_preserves_binary():
    result = run_exact_zip_hash(b"fixture zip bytes")
    assert result[0]["json"] == {
        "id": "gdelt-gkg-v2-fixture",
        "archive_sha256": "sha256:2a0b19afdfe6ba2d01a822bf194bf3a6e59fb0cf1dd907141a6f081a735bfd88",
    }
    assert result[0]["binary"]["data"] == {"type": "Buffer", "data": list(b"fixture zip bytes")}


def test_exact_n8n_code_node_derives_unique_relevant_document_metrics():
    result = run_exact_aggregate(_fixture_files())[0]["json"]

    assert result["query_definition_version"] == "eurusd-context-terms.v2"
    assert result["source_row_count"] == 20
    assert result["article_count"] == 3
    assert result["tone_sample_count"] == 2
    assert result["mean_tone"] == pytest.approx(0.625)
    assert len(result["source_records"]) == 4
    assert set(result) == {"stage_id", "bucket_time_utc", "source_records", "aggregate_sha256", "article_count", "source_row_count", "tone_sample_count", "mean_tone", "query_definition_version", "uncertainty_label", "retrieved_at_utc", "article_candidates"}
    assert result["article_candidates"] == []  # fixture identifiers are not public HTTPS URLs


def test_exact_n8n_code_node_emits_at_most_one_candidate_per_canonical_url():
    data = FIXTURE.read_text(encoding="utf-8").replace("fixture-doc-positive", "https://publisher.example/a#fragment").replace("fixture-doc-negative", "https://publisher.example/b").replace("fixture-doc-blank-tone", "https://publisher.example/c")
    result = run_exact_aggregate([data.encode()] * 4)[0]["json"]
    assert [candidate["canonical_url"] for candidate in result["article_candidates"]] == ["https://publisher.example/a", "https://publisher.example/b", "https://publisher.example/c"]
    assert all(candidate["sources"] for candidate in result["article_candidates"])
    assert "fixture-doc-" not in json.dumps(result)


def test_exact_n8n_candidate_envelope_is_accepted_by_the_egress_hmac_contract():
    source = _node_source("expand-article-candidates")
    aggregate = {
        "aggregate_sha256": "sha256:" + "c" * 64,
        "bucket_time_utc": "2026-09-14T21:00:00.000Z",
        "article_candidates": [{
            "canonical_url": "https://publisher.example/story",
            "sources": [{"source_observation_id": "gdelt-gkg-v2-fixture", "gdelt_document_id": "doc-1",
                         "bucket_time_utc": "2026-09-14T21:00:00.000Z", "source_tone": 1.0}],
        }],
    }
    runner = r'''
const vm=require('vm');let input='';process.stdin.on('data',c=>input+=c);process.stdin.on('end',()=>{
 const p=JSON.parse(input),context={$:(name)=>({all:()=>p.aggregates}),$env:{FOREX_GDELT_CANDIDATE_SIGNING_KEY:p.key},require};
 try {process.stdout.write(JSON.stringify({ok:true,value:vm.runInNewContext('(function(){'+p.source+'})()',context)}));}
 catch(error) {process.stdout.write(JSON.stringify({ok:false,error:error.message}));}
});
'''
    key = "s" * 32
    output = json.loads(subprocess.run(
        ["node", "-e", runner], input=json.dumps({"source": source, "aggregates": [{"json": aggregate}], "key": key}),
        text=True, capture_output=True, check=True,
    ).stdout)
    assert output["ok"], output
    envelope = output["value"][0]["json"]
    assert set(envelope) == {"aggregate_sha256", "bucket_time_utc", "candidate", "signature"}

    resolver = lambda *_args, **_kwargs: [(2, 1, 6, "", ("127.0.0.1", 443))]
    assert fetch_candidate(json.dumps(envelope).encode(), candidate_signing_key=key, resolver=resolver)["reason"] == "REFUSED_NON_GLOBAL_DESTINATION"


@pytest.mark.parametrize(
    ("files", "message"),
    [([FIXTURE.read_bytes()] * 3, "Expected four GDELT archives"), ([b"x" * (32 * 1024 * 1024 + 1)] * 4, "GKG CSV exceeds 32 MiB limit")],
)
def test_exact_n8n_code_node_rejects_invalid_file_sets(files, message):
    with pytest.raises(RuntimeError, match=message):
        run_exact_aggregate(files)


def test_exact_n8n_code_node_rejects_missing_hash_and_mismatched_hour():
    with pytest.raises(RuntimeError, match="Missing archive SHA-256"):
        run_exact_aggregate(_fixture_files(), hashes=[None] * 4)
    with pytest.raises(RuntimeError, match="Input archive hour mismatch"):
        run_exact_aggregate(_fixture_files(), hours=["2026-09-14T21:00:00.000Z", "2026-09-14T22:00:00.000Z"] + ["2026-09-14T21:00:00.000Z"] * 2)


def test_exact_n8n_code_node_rejects_duplicate_or_wrong_quarter_revision():
    duplicate = ["20260914210000.gkg.csv.zip"] * 2 + ["20260914213000.gkg.csv.zip", "20260914214500.gkg.csv.zip"]
    with pytest.raises(RuntimeError, match="Expected one archive for each closed-hour quarter"):
        run_exact_aggregate(_fixture_files(), revisions=duplicate)
    wrong = ["20260914210000.gkg.csv.zip", "20260914211500.gkg.csv.zip", "20260914213000.gkg.csv.zip", "20260914220000.gkg.csv.zip"]
    with pytest.raises(RuntimeError, match="Expected one archive for each closed-hour quarter"):
        run_exact_aggregate(_fixture_files(), revisions=wrong)


def test_exact_n8n_code_node_treats_non_numeric_tone_as_no_sample():
    malformed = FIXTURE.read_text(encoding="utf-8").replace("2.5,10", "not-a-tone,10").encode()
    result = run_exact_aggregate([malformed] * 4)[0]["json"]
    assert result["article_count"] == 3
    assert result["tone_sample_count"] == 1
    assert result["mean_tone"] == pytest.approx(-1.25)


@pytest.mark.parametrize(
    ("content", "message"),
    [(b"\xff", "GKG CSV is not valid UTF-8"), (b"one\ttwo\n", "Malformed GKG required columns")],
)
def test_exact_n8n_code_node_rejects_bad_csv(content, message):
    with pytest.raises(RuntimeError, match=message):
        run_exact_aggregate([content] * 4)
