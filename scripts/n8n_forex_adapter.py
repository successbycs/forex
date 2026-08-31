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
WORKFLOW_NAME = "Forex GDELT daily H1 context ingestion"
REMOTE_WORKFLOW_FILE = "/home/chris/projects/forex/n8n/forex-gdelt-daily.json"


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
    if not required <= node_types or "n8n-nodes-base.executeCommand" in node_types:
        raise RuntimeError("The fixed Forex M11 workflow violates its n8n-native node contract.")
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
            "[[ -r \"$key_file\" && -r \"$workflow_file\" ]] || { printf 'n8n API key or fixed Forex workflow file is unavailable.\\n' >&2; exit 3; }",
            "[[ \"$(sha256sum \"$workflow_file\" | awk '{print $1}')\" == \"$expected_sha256\" ]] || { printf 'Deployed Forex workflow differs from the bound revision.\\n' >&2; exit 4; }",
            f"curl --fail-with-body --silent --show-error --max-time 60 -X {adapter.shell_quote(method.upper())} -H 'accept: application/json' -H 'content-type: application/json' -H \"X-N8N-API-KEY: $(<\"$key_file\")\" --data-binary @\"$workflow_file\" \"$base_url/api/v1{path}\"",
        ]
    )
    result = adapter.execute_remote(script)
    return adapter.result_json(result), result


def upsert(activate: bool) -> dict[str, Any]:
    adapter = shared_n8n()
    definition = workflow()
    existing, _ = adapter.list_workflows()
    item = next((entry for entry in existing if entry.get("name") == WORKFLOW_NAME), None)
    if item is None:
        response, result = remote_workflow_request(adapter, "POST", "/workflows")
    else:
        workflow_id = str(item.get("id") or "").strip()
        if not workflow_id:
            raise RuntimeError("The existing Forex M11 n8n workflow has no id.")
        response, result = remote_workflow_request(adapter, "PUT", f"/workflows/{workflow_id}")
    workflow_id = str(response.get("id") or "").strip()
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fixed Forex M11 n8n adapter.")
    parser.add_argument("command", choices=("preflight", "upsert", "activate"))
    parser.add_argument("--approve", action="store_true")
    args = parser.parse_args(argv)
    if args.command in {"upsert", "activate"} and not args.approve:
        parser.error("upsert and activate require --approve")
    try:
        result = preflight() if args.command == "preflight" else upsert(activate=args.command == "activate")
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok") else 1
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"tool_id": "forex_m11_n8n_t480", "ok": False, "error": str(error)}, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
