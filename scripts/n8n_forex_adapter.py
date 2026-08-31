#!/usr/bin/env python3
"""Fixed Forex M11 n8n workflow adapter using the shared T480 transport.

The shared lab owns transport and the T480-local n8n API key. Forex owns this
single workflow catalogue entry. No shell, host, URL, credential, order, or
caller-selected workflow surface is accepted.
"""

from __future__ import annotations

import argparse
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


def upsert(activate: bool) -> dict[str, Any]:
    adapter = shared_n8n()
    definition = workflow()
    existing, _ = adapter.list_workflows()
    item = next((entry for entry in existing if entry.get("name") == WORKFLOW_NAME), None)
    payload = adapter.workflow_api_payload(definition)
    if item is None:
        response, result = adapter.api_request("POST", "/workflows", payload)
    else:
        workflow_id = str(item.get("id") or "").strip()
        if not workflow_id:
            raise RuntimeError("The existing Forex M11 n8n workflow has no id.")
        response, result = adapter.api_request("PUT", f"/workflows/{workflow_id}", payload)
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
