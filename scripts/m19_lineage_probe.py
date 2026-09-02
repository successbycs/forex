#!/usr/bin/env python3
"""Fixed T480 M19 drill: persist one validated M18 research observation.

No arguments are accepted. The script uses only the retained Demo-only M2
snapshot, the M17 bounded context and the fixed local M18 model selector.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from forex.agent_context import build_context
from forex.ollama_sentiment import build_request, sha256, validate_response

MODEL = "qwen2.5:3b"
LAB_ROOT = "/home/chris/projects/cs-ai-lab-infra"
SNAPSHOT_ID = "m2-m1-eurusd-h1-720"


def quote(value: object) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def compose(service: str, *args: str, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", service, *args],
        input=input_text, text=True, capture_output=True, check=False, cwd=LAB_ROOT,
    )
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or "no command output"
        raise RuntimeError(f"fixed M19 {service} operation failed with exit {result.returncode}: {detail}")
    return result


def main() -> int:
    rows = compose(
        "postgres", "psql", "-At", "-F", "|", "-U", os.environ["POSTGRES_USER"], "-d", os.environ["POSTGRES_DB"], "-c",
        "SELECT time_utc::text, available_at_utc::text, open, high, low, close, volume "
        f"FROM forex.price_bar WHERE snapshot_id='{SNAPSHOT_ID}' ORDER BY time_utc LIMIT 12;",
    ).stdout.splitlines()
    bars = [dict(zip(("time_utc", "available_at_utc", "open", "high", "low", "close", "volume"), row.split("|"))) for row in rows if row]
    if not bars:
        raise RuntimeError("no retained historical bars are available for M19")
    context = build_context(
        bars=bars,
        cutoff_utc=bars[-1]["available_at_utc"],
        features={"source": "DEMO_ONLY_HISTORICAL", "licensing": "UNQUALIFIED_BROKER_TERMINAL_DATA"},
    )
    request = build_request(context)
    model_line = next((line.strip() for line in compose("ollama", "ollama", "list").stdout.splitlines() if line.startswith(f"{MODEL} ")), "")
    if not model_line:
        raise RuntimeError(f"approved local model is unavailable: {MODEL}")
    raw = compose("ollama", "ollama", "run", MODEL, "--format", json.dumps(request["response_schema"], separators=(",", ":")), input_text=request["prompt"]).stdout.strip()
    raw_output = json.loads(raw)
    response = validate_response(raw_output)
    input_payload = {"context": context, "prompt": request["prompt"], "response_schema": request["response_schema"]}
    output_payload = {"response": response}
    input_hash = sha256(input_payload)
    output_hash = sha256(output_payload)
    inference_id = "m19-inference-" + hashlib.sha256(f"{input_hash}:{output_hash}".encode()).hexdigest()[:20]
    decision_id = "m19-decision-" + hashlib.sha256(inference_id.encode()).hexdigest()[:20]
    application_revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=True).stdout.strip()
    configuration_fingerprint = json.loads(subprocess.run(["python3", "scripts/forex_milestones.py", "status", "--json"], cwd=ROOT, text=True, capture_output=True, check=True).stdout)["configuration_fingerprint"]
    sql = f"""BEGIN;
INSERT INTO forex.model_inference_lineage (inference_id,snapshot_id,source_label,model_id,model_definition_sha256,prompt_template_version,prompt_sha256,input_sha256,output_sha256,input_payload,output_payload,validation_result,research_only,order_capability,application_revision,configuration_fingerprint)
VALUES ({quote(inference_id)},{quote(SNAPSHOT_ID)},'DEMO_ONLY_HISTORICAL',{quote(MODEL)},{quote(sha256(model_line))},{quote(request['prompt_template_version'])},{quote(sha256(request['prompt']))},{quote(input_hash)},{quote(output_hash)},{quote(json.dumps(input_payload, sort_keys=True))}::jsonb,{quote(json.dumps(output_payload, sort_keys=True))}::jsonb,'PASS',true,false,{quote(application_revision)},{quote(configuration_fingerprint)})
ON CONFLICT (inference_id) DO NOTHING;
INSERT INTO forex.research_decision_lineage (decision_id,inference_id,hypothesis_id,hypothesis_text,decision_state,validation_result)
VALUES ({quote(decision_id)},{quote(inference_id)},'eurusd-h1-historical-sentiment-observation','A bounded historical EUR/USD H1 sentiment observation may be retained for later research evaluation.','RESEARCH_ONLY','PASS')
ON CONFLICT (decision_id) DO NOTHING;
COMMIT;
SELECT 'FOREX_M19_LINEAGE_PERSIST_OK', {quote(inference_id)}, {quote(decision_id)}, {quote(input_hash)}, {quote(output_hash)};
"""
    persisted = compose("postgres", "psql", "-v", "ON_ERROR_STOP=1", "-At", "-F", "|", "-U", os.environ["POSTGRES_USER"], "-d", os.environ["POSTGRES_DB"], input_text=sql).stdout.strip()
    if not persisted.startswith("FOREX_M19_LINEAGE_PERSIST_OK|"):
        raise RuntimeError("fixed M19 persistence marker is absent")
    print(json.dumps({
        "marker": "FOREX_M19_LINEAGE_PROBE_OK", "inference_id": inference_id, "decision_id": decision_id,
        "snapshot_id": SNAPSHOT_ID, "model": MODEL, "model_definition_sha256": sha256(model_line),
        "prompt_template_version": request["prompt_template_version"], "prompt_sha256": sha256(request["prompt"]),
        "input_sha256": input_hash, "output_sha256": output_hash, "validation_result": "PASS",
        "response": response, "research_only": True, "order_capability": False, "live_trading_capability": False,
    }, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
