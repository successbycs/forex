#!/usr/bin/env python3
"""Fixed Forex M11 n8n workflow adapter using the shared T480 transport.

The shared lab owns transport and the T480-local n8n API key. Forex owns this
single workflow catalogue entry. No shell, host, URL, credential, order, or
caller-selected workflow surface is accepted.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_FILE = ROOT / "n8n" / "forex-gdelt-daily.json"
SHARED_ROOT = Path("/home/chris/projects/cs-ai-lab-infra")
SHARED_ADAPTER = SHARED_ROOT / "scripts" / "n8n_adapter.py"
WORKFLOW_NAME = "Forex GDELT hourly download and stage"
REMOTE_WORKFLOW_FILE = "/home/chris/projects/forex/n8n/forex-gdelt-daily.json"
CREDENTIAL_NAME = "Forex M11 PostgreSQL"
REMOTE_LAB_ENV = "/home/chris/projects/cs-ai-lab-infra/.env"
REMOTE_INSTALLER = "/home/chris/projects/forex/scripts/n8n_m11_install.py"
RUN_NOW_PATH = "/webhook/forex-m11-run-now"


def shared_n8n() -> Any:
    """Load the shared adapter without copying transport or credential logic."""
    if not SHARED_ADAPTER.is_file():
        raise RuntimeError("The shared T480 n8n adapter is unavailable.")
    sys.path.insert(0, str(SHARED_ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("forex_shared_n8n_adapter", SHARED_ADAPTER)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load the shared T480 n8n adapter.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def workflow() -> dict[str, Any]:
    payload = json.loads(WORKFLOW_FILE.read_text(encoding="utf-8"))
    if payload.get("name") != WORKFLOW_NAME or payload.get("active") is not False:
        raise RuntimeError("The fixed Forex M11 workflow name or inactive default is invalid.")
    nodes = payload.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise RuntimeError("The fixed Forex M11 workflow has no nodes.")
    node_types = {str(node.get("type", "")) for node in nodes if isinstance(node, dict)}
    required = {
        "n8n-nodes-base.scheduleTrigger",
        "n8n-nodes-base.httpRequest",
        "n8n-nodes-base.compression",
        "n8n-nodes-base.code",
        "n8n-nodes-base.postgres",
    }
    if not required <= node_types or "n8n-nodes-base.executeCommand" in node_types or "n8n-nodes-base.executeWorkflow" in node_types:
        raise RuntimeError("The fixed Forex M11 workflow violates its n8n-native node contract.")
    webhook = next((node for node in payload["nodes"] if node.get("name") == "Run M11 now (T480-local only)"), None)
    if not isinstance(webhook, dict) or webhook.get("type") != "n8n-nodes-base.webhook" or webhook.get("webhookId") != "2e9a7b9a-7a20-4ff3-8f5a-35d2a6890996":
        raise RuntimeError("The fixed Forex M11 run-now webhook is missing.")
    parameters = webhook.get("parameters")
    if not isinstance(parameters, dict) or parameters.get("httpMethod") != "POST" or parameters.get("path") != "forex-m11-run-now" or parameters.get("responseMode") != "lastNode":
        raise RuntimeError("The fixed Forex M11 run-now webhook contract is invalid.")
    return payload


def preflight() -> dict[str, Any]:
    adapter = shared_n8n()
    return adapter.preflight()


def remote_workflow_request(adapter: Any, method: str, path: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Submit the one deployed workflow file without putting it on an SSH argv."""
    expected_sha256 = hashlib.sha256(WORKFLOW_FILE.read_bytes()).hexdigest()
    settings = adapter.config()
    script = "\n".join(
        [
            "set -euo pipefail",
            f"key_file={adapter.shell_quote(settings['key_file'])}",
            f"base_url={adapter.shell_quote(settings['base_url'])}",
            f"workflow_file={adapter.shell_quote(REMOTE_WORKFLOW_FILE)}",
            f"expected_sha256={adapter.shell_quote(expected_sha256)}",
            f"credential_name={adapter.shell_quote(CREDENTIAL_NAME)}",
            f"lab_env={adapter.shell_quote(REMOTE_LAB_ENV)}",
            "[[ -r \"$key_file\" && -r \"$workflow_file\" ]] || { printf 'n8n API key or fixed Forex workflow file is unavailable.\\n' >&2; exit 3; }",
            "[[ -r \"$lab_env\" ]] || { printf 'T480 lab environment file is unavailable.\\n' >&2; exit 3; }",
            "[[ \"$(sha256sum \"$workflow_file\" | awk '{print $1}')\" == \"$expected_sha256\" ]] || { printf 'Deployed Forex workflow differs from the bound revision.\\n' >&2; exit 4; }",
            "payload_file=\"$(mktemp)\"; trap 'rm -f \"$payload_file\"' EXIT",
            "credential_list=\"$(curl --fail-with-body --silent --show-error --max-time 30 -H 'accept: application/json' -H \"X-N8N-API-KEY: $(<\"$key_file\")\" \"$base_url/api/v1/credentials?limit=100\")\"",
            "credential_id=\"$(printf '%s' \"$credential_list\" | python3 -c 'import json,sys; data=json.load(sys.stdin).get(\"data\", []); print(next((str(x.get(\"id\")) for x in data if x.get(\"name\")==sys.argv[1] and x.get(\"type\")==\"postgres\"), \"\"))' \"$credential_name\")\"",
            "if [[ -z \"$credential_id\" ]]; then set -a; . \"$lab_env\"; set +a; credential_file=\"$(mktemp)\"; trap 'rm -f \"$payload_file\" \"$credential_file\"' EXIT; CREDENTIAL_NAME=\"$credential_name\" python3 - > \"$credential_file\" <<'PY'\nimport json, os\nprint(json.dumps({\"name\": os.environ[\"CREDENTIAL_NAME\"], \"type\": \"postgres\", \"data\": {\"host\": \"postgres\", \"port\": 5432, \"database\": os.environ[\"POSTGRES_DB\"], \"user\": os.environ[\"POSTGRES_USER\"], \"password\": os.environ[\"POSTGRES_PASSWORD\"], \"ssl\": \"disable\"}}, separators=(\",\", \":\")))\nPY\ncredential_response=\"$(curl --fail-with-body --silent --show-error --max-time 30 -X POST -H 'accept: application/json' -H 'content-type: application/json' -H \"X-N8N-API-KEY: $(<\"$key_file\")\" --data-binary @\"$credential_file\" \"$base_url/api/v1/credentials\")\"; credential_id=\"$(printf '%s' \"$credential_response\" | python3 -c 'import json,sys; print(json.load(sys.stdin).get(\"id\", \"\"))')\"; fi",
            "[[ -n \"$credential_id\" ]] || { printf 'n8n PostgreSQL credential was not created or found.\\n' >&2; exit 5; }",
            "FOREX_CREDENTIAL_ID=\"$credential_id\" python3 - \"$workflow_file\" > \"$payload_file\" <<'PY'\nimport json, os, sys\nworkflow = json.load(open(sys.argv[1], encoding='utf-8'))\nfor node in workflow[\"nodes\"]:\n    if node.get(\"id\") == \"persist-gdelt-h1-context\":\n        node[\"credentials\"] = {\"postgres\": {\"id\": os.environ[\"FOREX_CREDENTIAL_ID\"], \"name\": \"Forex M11 PostgreSQL\"}}\nprint(json.dumps({key: workflow.get(key, {} if key in {\"connections\", \"settings\"} else []) for key in (\"name\", \"nodes\", \"connections\", \"settings\")}, separators=(\",\", \":\")))\nPY",
            f"curl --fail-with-body --silent --show-error --max-time 60 -X {adapter.shell_quote(method.upper())} -H 'accept: application/json' -H 'content-type: application/json' -H \"X-N8N-API-KEY: $(<\"$key_file\")\" --data-binary @\"$payload_file\" \"$base_url/api/v1{path}\"",
        ]
    )
    result = adapter.execute_remote(script)
    return adapter.result_json(result), result


def upsert(activate: bool) -> dict[str, Any]:
    adapter = shared_n8n()
    workflow()
    result = adapter.execute_remote(f"python3 {adapter.shell_quote(REMOTE_INSTALLER)}")
    response = adapter.result_json(result)
    workflow_id = str(response.get("workflow_id") or response.get("id") or "").strip()
    if activate:
        if not workflow_id:
            raise RuntimeError("n8n did not return the Forex M11 workflow id.")
        response, result = adapter.api_request("POST", f"/workflows/{workflow_id}/activate")
    return {
        "tool_id": "forex_m11_n8n_t480",
        "operation": "upsert_and_activate" if activate else "upsert",
        "workflow_name": WORKFLOW_NAME,
        "workflow_id": workflow_id,
        "workflow": response,
        "result": result,
        "ok": True,
    }


def recent_execution() -> dict[str, Any]:
    """Return the latest bounded M11 execution summary, without raw payloads."""
    adapter = shared_n8n()
    response, result = adapter.api_request("GET", "/executions?workflowId=rfIIE2BiPtppBbT2&limit=1")
    executions = response.get("data", [])
    latest = executions[0] if isinstance(executions, list) and executions else {}
    summary = {key: latest.get(key) for key in ("id", "status", "mode", "startedAt", "stoppedAt", "workflowId")}
    return {
        "tool_id": "forex_m11_n8n_t480",
        "operation": "recent_execution",
        "workflow_id": "rfIIE2BiPtppBbT2",
        "execution": summary,
        "result": result,
        "ok": result.get("ok", False),
    }


def trigger_now() -> dict[str, Any]:
    """Start the one fixed workflow through T480-local n8n service mode."""
    adapter = shared_n8n()
    workflow()
    settings = adapter.config()
    script = "\n".join(
        [
            "set -euo pipefail",
            f"base_url={adapter.shell_quote(settings['base_url'])}",
            f"curl --fail-with-body --silent --show-error --max-time 30 -X POST \"$base_url{RUN_NOW_PATH}\"",
        ]
    )
    result = adapter.execute_remote(script)
    return {
        "tool_id": "forex_m11_n8n_t480",
        "operation": "trigger_now",
        "workflow_id": "rfIIE2BiPtppBbT2",
        "result": result,
        "ok": result.get("ok", False),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fixed Forex M11 n8n adapter.")
    parser.add_argument("command", choices=("preflight", "upsert", "activate", "trigger-now", "recent-execution"))
    parser.add_argument("--approve", action="store_true")
    args = parser.parse_args(argv)
    if args.command in {"upsert", "activate", "trigger-now"} and not args.approve:
        parser.error("upsert, activate and trigger-now require --approve")
    try:
        if args.command == "preflight":
            result = preflight()
        elif args.command == "recent-execution":
            result = recent_execution()
        elif args.command == "trigger-now":
            result = trigger_now()
        else:
            result = upsert(activate=args.command == "activate")
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok") else 1
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"tool_id": "forex_m11_n8n_t480", "ok": False, "error": str(error)}, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
