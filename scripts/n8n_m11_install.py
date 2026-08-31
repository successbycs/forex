#!/usr/bin/env python3
"""T480-local installer for the one fixed M11 n8n workflow.

This is deployment plumbing, not a scheduled collector.  It reads both the
n8n API key and PostgreSQL password only on the T480 and never prints them.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / "n8n" / "forex-gdelt-daily.json"
LAB_ROOT = Path("/home/chris/projects/cs-ai-lab-infra")
KEY_FILE = Path("/home/chris/.config/cs-ai-lab/n8n-api-key")
NAME = "Forex GDELT daily H1 context ingestion"
CREDENTIAL_NAME = "Forex M11 PostgreSQL"


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
    with urlopen(request, timeout=60) as response:
        value = json.loads(response.read())
    if not isinstance(value, dict):
        raise RuntimeError("n8n returned an invalid response")
    return value


def main() -> None:
    workflow = json.loads(WORKFLOW.read_text(encoding="utf-8"))
    if workflow.get("name") != NAME or workflow.get("active") is not False:
        raise RuntimeError("fixed M11 workflow contract is invalid")
    credentials = api("GET", "/credentials?limit=100").get("data", [])
    credential_id = next((str(item.get("id")) for item in credentials if item.get("name") == CREDENTIAL_NAME and item.get("type") == "postgres"), "")
    if not credential_id:
        values = env_file()
        credential = api("POST", "/credentials", {"name": CREDENTIAL_NAME, "type": "postgres", "data": {"host": "postgres", "port": 5432, "database": values["POSTGRES_DB"], "user": values["POSTGRES_USER"], "password": values["POSTGRES_PASSWORD"], "ssl": "disable"}})
        credential_id = str(credential.get("id") or "")
    if not credential_id:
        raise RuntimeError("n8n PostgreSQL credential was not created")
    for node in workflow["nodes"]:
        if node.get("id") == "persist-gdelt-h1-context":
            node["credentials"] = {"postgres": {"id": credential_id, "name": CREDENTIAL_NAME}}
    payload = {key: workflow.get(key, {} if key in {"connections", "settings"} else []) for key in ("name", "nodes", "connections", "settings")}
    workflows = api("GET", "/workflows?limit=250").get("data", [])
    existing = next((item for item in workflows if item.get("name") == NAME), None)
    response = api("PUT", f"/workflows/{existing['id']}", payload) if existing else api("POST", "/workflows", payload)
    print(json.dumps({"workflow_id": response.get("id"), "workflow_name": NAME, "credential_configured": True, "ok": True}))


if __name__ == "__main__":
    main()
