#!/usr/bin/env python3
"""Forex-owned extraction of the fixed T480 PostgreSQL M2 adapter.

Transport, Docker, database credentials and backups stay in cs-ai-lab-infra.
This adapter owns only Forex's fixed schema, import and verification actions.
It deliberately has no SQL, URL, host, shell, MT5 or order argument.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from forex.t480_dependency import require_dependency  # noqa: E402

CONFIG = json.loads((ROOT / "config" / "t480.json").read_text())
require_dependency(CONFIG)
SHARED_ROOT = Path(CONFIG["shared_core"]["repository_root"])
sys.path.insert(0, str(SHARED_ROOT))
from t480_core import build_ssh_command, build_wsl_powershell_command, load_transport_settings, resolve_ssh_target  # noqa: E402

SETTINGS = load_transport_settings(SHARED_ROOT / "t480" / "transport-config.json")
TARGET = resolve_ssh_target(SETTINGS, [ROOT / ".env.t480.local", SHARED_ROOT / ".env.t480.local"])
REMOTE_LAB = "/home/chris/projects/cs-ai-lab-infra"
REMOTE_FOREX = "/home/chris/projects/forex"
ASSETS = {"schema": "sql/migrations/001_m2_historical_data.sql", "import": "scripts/build_m2_postgres_import.py"}
READ_ONLY = {"preflight", "inspect", "vector-probe", "forex-m2-verify"}
MUTATING = {"forex-m2-apply-schema", "forex-m2-import"}


def remote(body: str) -> dict:
    script = f"set -euo pipefail\ncd {REMOTE_LAB}\ntest -f .env\nset -a\nsource .env\nset +a\n{body}\n"
    command = build_ssh_command(TARGET, build_wsl_powershell_command(script, SETTINGS), SETTINGS)
    result = subprocess.run(command, text=True, capture_output=True, timeout=SETTINGS.long_command_timeout_seconds, check=False)
    return {"exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr, "ok": result.returncode == 0}


def asset(name: str) -> tuple[str, str]:
    relative = ASSETS[name]
    path = ROOT / relative
    if not path.is_file():
        raise RuntimeError(f"Required Forex asset is absent: {relative}")
    return relative, hashlib.sha256(path.read_bytes()).hexdigest()


def wrap(operation: str, result: dict, digest: str | None = None) -> dict:
    payload = {"tool_id": "forex_postgres_pgvector_t480", "operation": operation, "result": result, "ok": result["ok"]}
    if digest:
        payload["asset_sha256"] = f"sha256:{digest}"
    return payload


def preflight() -> dict:
    return wrap("preflight", remote('docker compose ps postgres\ndocker compose exec -T postgres pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" </dev/null'))


def inspect() -> dict:
    return wrap("inspect", remote('docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT current_database(), current_user, extname FROM pg_extension WHERE extname=\'vector\';" </dev/null'))


def vector_probe() -> dict:
    return wrap("vector_probe", remote('docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT \'[1,0,0]\'::vector <-> \'[0,1,0]\'::vector;" </dev/null'))


def apply_schema() -> dict:
    relative, digest = asset("schema")
    body = f'''file="{REMOTE_FOREX}/{relative}"
test -f "$file"
[[ "$(sha256sum "$file" | head -c 64)" == "{digest}" ]]
if [[ "$(docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT to_regclass('forex.source_registry') IS NOT NULL;" </dev/null)" == t ]]; then
  printf 'FOREX_M2_SCHEMA_ALREADY_APPLIED sha256:{digest}\\n'
else
  docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" < "$file"
  printf 'FOREX_M2_SCHEMA_APPLIED sha256:{digest}\\n'
fi'''
    return wrap("forex_m2_apply_schema", remote(body), digest)


def import_snapshot() -> dict:
    relative, digest = asset("import")
    body = f'''file="{REMOTE_FOREX}/{relative}"
test -f "$file"
[[ "$(sha256sum "$file" | head -c 64)" == "{digest}" ]]
cd "{REMOTE_FOREX}"
python3 "$file" | docker compose -f "{REMOTE_LAB}/compose.yaml" exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"
printf 'FOREX_M2_IMPORT_EXECUTED sha256:{digest}\\n' '''
    return wrap("forex_m2_import_snapshot", remote(body), digest)


def verify_snapshot() -> dict:
    body = '''docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT 'FOREX_M2_POSTGRES_VERIFY_OK', (SELECT count(*) FROM forex.source_registry), (SELECT count(*) FROM forex.raw_observation), (SELECT count(*) FROM forex.dataset_snapshot), (SELECT count(*) FROM forex.price_bar), (SELECT artifact_sha256 FROM forex.dataset_snapshot WHERE snapshot_id='m2-m1-eurusd-h1-720'), (SELECT payload_sha256 FROM forex.raw_observation WHERE observation_id='m1-demo-eurusd-h1-720');" </dev/null'''
    return wrap("forex_m2_verify_snapshot", remote(body))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fixed Forex M2 PostgreSQL adapter.")
    parser.add_argument("command", choices=sorted(READ_ONLY | MUTATING))
    parser.add_argument("--approve", action="store_true")
    args = parser.parse_args(argv)
    if args.command in MUTATING and not args.approve:
        parser.error("this mutating operation requires --approve")
    actions = {"preflight": preflight, "inspect": inspect, "vector-probe": vector_probe, "forex-m2-apply-schema": apply_schema, "forex-m2-import": import_snapshot, "forex-m2-verify": verify_snapshot}
    payload = actions[args.command]()
    print(json.dumps(payload, indent=2))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
