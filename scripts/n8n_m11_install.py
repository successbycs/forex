#!/usr/bin/env python3
"""T480-local installer for the one fixed M11 n8n workflow.

This is deployment plumbing, not a scheduled collector.  It reads both the
n8n API key and PostgreSQL password only on the T480 and never prints them.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = {
    "Forex GDELT hourly download and stage": ROOT / "n8n" / "forex-gdelt-daily.json",
    "Forex GDELT hourly context import": ROOT / "n8n" / "forex-gdelt-hourly-import.json",
}
M13_SEED_NAME = "Forex M13 historical GDELT seed"
M13_SEED_WEBHOOK_ID = "31f35b0f-0b6e-4778-809f-14d13e8b0430"
LAB_ROOT = Path("/home/chris/projects/cs-ai-lab-infra")
KEY_FILE = Path("/home/chris/.config/cs-ai-lab/n8n-api-key")
NAME = "Forex GDELT hourly download and stage"
CREDENTIAL_NAME = "Forex M11 PostgreSQL"
LEGACY_WORKFLOW_NAME = "Forex GDELT daily H1 context ingestion"


def env_file() -> dict[str, str]:
    values: dict[str, str] = {}
    for line in (LAB_ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            values[key] = value
    return values


def api(method: str, path: str, payload: dict | None = None) -> dict:
    body = None if payload is None else json.dumps(payload, separators=(",", ":")).encode()
    request = Request(
        "http://127.0.0.1:5678/api/v1" + path, body, method=method,
        headers={"accept": "application/json", "content-type": "application/json", "X-N8N-API-KEY": KEY_FILE.read_text().strip()},
    )
    try:
        with urlopen(request, timeout=60) as response:
            value = json.loads(response.read())
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"n8n {method} {path} failed with HTTP {error.code}: {detail}") from error
    if not isinstance(value, dict):
        raise RuntimeError("n8n returned an invalid response")
    return value


def upsert_workflow(name: str, payload: dict) -> dict:
    workflows = api("GET", "/workflows?limit=250").get("data", [])
    existing = next((item for item in workflows if item.get("name") == name), None)
    if existing and existing.get("active"):
        api("POST", f"/workflows/{existing['id']}/deactivate")
    return api("PUT", f"/workflows/{existing['id']}", payload) if existing else api("POST", "/workflows", payload)


def deactivate_legacy_workflow() -> None:
    """Remove only the known obsolete webhook owner before activating M11-R1."""
    workflows = api("GET", "/workflows?limit=250").get("data", [])
    legacy = next((item for item in workflows if item.get("name") == LEGACY_WORKFLOW_NAME), None)
    if legacy and legacy.get("active"):
        api("POST", f"/workflows/{legacy['id']}/deactivate")


def activate_workflow(workflow_id: str) -> None:
    api("POST", f"/workflows/{workflow_id}/activate")


def payload_for(workflow: dict, credential_id: str) -> dict:
    """Bind the one fixed credential; no caller selects workflows or SQL."""
    for node in workflow["nodes"]:
        if node.get("id") in {"stage", "persist-hourly-context", "import-staged-hour"}:
            node["credentials"] = {"postgres": {"id": credential_id, "name": CREDENTIAL_NAME}}
    return {key: workflow.get(key, {} if key in {"connections", "settings"} else []) for key in ("name", "nodes", "connections", "settings")}


def m13_historical_seed(workflow: dict) -> dict:
    """Derive one non-scheduled, fixed M13 seed from the proven M11 stage flow."""
    seed = json.loads(json.dumps(workflow))
    seed["name"] = M13_SEED_NAME
    seed["nodes"] = [node for node in seed["nodes"] if node.get("id") != "schedule"]
    for node in seed["nodes"]:
        if node.get("id") == "webhook":
            node["name"] = "Run fixed M13 historical seed (T480-local only)"
            node["webhookId"] = M13_SEED_WEBHOOK_ID
            node["parameters"]["path"] = "forex-m13-historical-context-seed"
        elif node.get("id") == "build":
            node["name"] = "Build four fixed historical GKG URLs"
            node["parameters"]["jsCode"] = node["parameters"]["jsCode"].replace(
                "const n=new Date(),h=new Date(Date.UTC(n.getUTCFullYear(),n.getUTCMonth(),n.getUTCDate(),n.getUTCHours()-1));",
                "const h=new Date('2026-08-28T00:00:00Z');",
            )
    seed["connections"].pop("Schedule after UTC hour closes", None)
    seed["connections"]["Run fixed M13 historical seed (T480-local only)"] = seed["connections"].pop(
        "Run M11 now (T480-local only)"
    )
    seed["connections"]["Run fixed M13 historical seed (T480-local only)"]["main"][0][0]["node"] = (
        "Build four fixed historical GKG URLs"
    )
    seed["connections"]["Build four fixed historical GKG URLs"] = seed["connections"].pop(
        "Build four closed-hour GKG URLs"
    )
    return seed


def main() -> None:
    workflows = {name: json.loads(path.read_text(encoding="utf-8")) for name, path in WORKFLOWS.items()}
    workflows[M13_SEED_NAME] = m13_historical_seed(workflows[NAME])
    if any(item.get("name") != name or item.get("active") is not False for name, item in workflows.items()):
        raise RuntimeError("fixed M11 workflow contract is invalid")
    lookup = subprocess.run(
        ["docker", "compose", "exec", "-T", "postgres", "psql", "-U", "cs_ai_lab", "-d", "cs_ai_lab", "-Atqc", "SELECT id FROM credentials_entity WHERE name = 'Forex M11 PostgreSQL' AND type = 'postgres' LIMIT 1"],
        cwd=LAB_ROOT, check=True, capture_output=True, text=True,
    )
    credential_id = lookup.stdout.strip()
    if not credential_id:
        values = env_file()
        credential = api("POST", "/credentials", {"name": CREDENTIAL_NAME, "type": "postgres", "data": {"host": "postgres", "port": 5432, "database": values["POSTGRES_DB"], "user": values["POSTGRES_USER"], "password": values["POSTGRES_PASSWORD"], "ssl": "disable", "sshTunnel": False}})
        credential_id = str(credential.get("id") or "")
    if not credential_id:
        raise RuntimeError("n8n PostgreSQL credential was not created")
    deactivate_legacy_workflow()
    ids = {}
    for name, workflow in workflows.items():
        response = upsert_workflow(name, payload_for(workflow, credential_id))
        if not (workflow_id := str(response.get("id") or "")):
            raise RuntimeError(f"n8n M11 workflow was not created: {name}")
        ids[name] = workflow_id
    for workflow_id in ids.values():
        activate_workflow(workflow_id)
    print(json.dumps({"workflow_id": ids[NAME], "workflow_name": NAME, "workflow_ids": ids, "credential_configured": True, "activated": True, "ok": True}))


if __name__ == "__main__":
    main()
