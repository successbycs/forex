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
ASSETS = {
    "schema": "sql/migrations/001_m2_historical_data.sql",
    "sealed_provenance": "sql/migrations/002_m2_sealed_provenance.sql",
    "import": "scripts/build_m2_postgres_import.py",
}
M2_SNAPSHOT_ID = "m2-m1-eurusd-h1-720"
M2_SNAPSHOT_ARTIFACT_SHA256 = "sha256:dc5384732d71091aa2279aaf6d92e8e1780c8021eacde948432ad7bc68fdabaa"
READ_ONLY = {"preflight", "inspect", "vector-probe", "forex-m2-verify", "forex-m2-provenance-negative-control"}
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
    schema_relative, schema_digest = asset("schema")
    provenance_relative, provenance_digest = asset("sealed_provenance")
    combined_digest = hashlib.sha256(f"{schema_digest}:{provenance_digest}".encode()).hexdigest()
    body = f'''schema_file="{REMOTE_FOREX}/{schema_relative}"
provenance_file="{REMOTE_FOREX}/{provenance_relative}"
test -f "$schema_file" && test -f "$provenance_file"
[[ "$(sha256sum "$schema_file" | head -c 64)" == "{schema_digest}" ]]
[[ "$(sha256sum "$provenance_file" | head -c 64)" == "{provenance_digest}" ]]
applied=false
if [[ "$(docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT to_regclass('forex.source_registry') IS NOT NULL;" </dev/null)" != t ]]; then
  docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" < "$schema_file"
  applied=true
fi
docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" < "$provenance_file"
applied=true
if [[ "$applied" == true ]]; then
  printf 'FOREX_M2_SCHEMA_APPLIED sha256:{combined_digest}\\n'
else
  printf 'FOREX_M2_SCHEMA_ALREADY_APPLIED sha256:{combined_digest}\\n'
fi'''
    return wrap("forex_m2_apply_schema", remote(body), combined_digest)


def import_snapshot() -> dict:
    relative, digest = asset("import")
    body = f'''file="{REMOTE_FOREX}/{relative}"
test -f "$file"
[[ "$(sha256sum "$file" | head -c 64)" == "{digest}" ]]
existing="$(docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT artifact_sha256 FROM forex.dataset_snapshot WHERE snapshot_id = '{M2_SNAPSHOT_ID}';" </dev/null)"
if [[ -n "$existing" ]]; then
  [[ "$existing" == "{M2_SNAPSHOT_ARTIFACT_SHA256}" ]] || {{ printf 'Existing M2 snapshot hash differs.\\n' >&2; exit 5; }}
  printf 'FOREX_M2_IMPORT_ALREADY_PRESENT sha256:{digest}\\n'
  exit 0
fi
cd "{REMOTE_FOREX}"
python3 "$file" | docker compose -f "{REMOTE_LAB}/compose.yaml" exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"
printf 'FOREX_M2_IMPORT_EXECUTED sha256:{digest}\\n' '''
    return wrap("forex_m2_import_snapshot", remote(body), digest)


def verify_snapshot() -> dict:
    body = '''docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT 'FOREX_M2_POSTGRES_VERIFY_OK',
 (SELECT count(*) FROM forex.source_registry),
 (SELECT count(*) FROM forex.raw_observation),
 (SELECT count(*) FROM forex.dataset_snapshot),
 (SELECT count(*) FROM forex.price_bar),
 (SELECT artifact_sha256 FROM forex.dataset_snapshot WHERE snapshot_id='m2-m1-eurusd-h1-720'),
 (SELECT payload_sha256 FROM forex.raw_observation WHERE observation_id='m1-demo-eurusd-h1-720'),
 'source_status=' || (SELECT approval_status FROM forex.source_registry WHERE source_id='gomarketsmu-demo-m1'),
 'snapshot=' || (SELECT instrument || ':' || timeframe FROM forex.dataset_snapshot WHERE snapshot_id='m2-m1-eurusd-h1-720'),
 'lineage_ok=' || EXISTS (SELECT 1 FROM forex.dataset_snapshot_observation link JOIN forex.raw_observation observation ON observation.observation_id=link.observation_id JOIN forex.source_registry source ON source.source_id=observation.source_id WHERE link.snapshot_id='m2-m1-eurusd-h1-720' AND observation.observation_id='m1-demo-eurusd-h1-720' AND source.source_id='gomarketsmu-demo-m1'),
 'bar_availability_ok=' || NOT EXISTS (SELECT 1 FROM forex.price_bar bar JOIN forex.dataset_snapshot snapshot ON snapshot.snapshot_id=bar.snapshot_id WHERE bar.snapshot_id='m2-m1-eurusd-h1-720' AND bar.available_at_utc > snapshot.decision_cutoff_utc),
 'point_in_time_triggers=' || (SELECT count(*) FROM pg_trigger WHERE NOT tgisinternal AND tgname IN ('price_bar_point_in_time','snapshot_observation_point_in_time')),
 'sealed_provenance_triggers=' || (SELECT count(*) FROM pg_trigger WHERE NOT tgisinternal AND tgname = 'raw_observation_sealed_provenance_immutable');
 " </dev/null'''
    return wrap("forex_m2_verify_snapshot", remote(body))


def provenance_negative_control() -> dict:
    body = '''docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<'SQL'
DO $$
BEGIN
  BEGIN
    UPDATE forex.raw_observation SET source_revision = source_revision WHERE observation_id = 'm1-demo-eurusd-h1-720';
    RAISE EXCEPTION 'raw observation mutation unexpectedly allowed';
  EXCEPTION WHEN OTHERS THEN
    IF SQLERRM <> 'sealed snapshot provenance is immutable' THEN RAISE; END IF;
  END;
  RAISE NOTICE 'FOREX_M2_SEALED_RAW_OBSERVATION_NEGATIVE_CONTROL_OK';
END;
$$;
SQL'''
    return wrap("forex_m2_provenance_negative_control", remote(body))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fixed Forex M2 PostgreSQL adapter.")
    parser.add_argument("command", choices=sorted(READ_ONLY | MUTATING))
    parser.add_argument("--approve", action="store_true")
    args = parser.parse_args(argv)
    if args.command in MUTATING and not args.approve:
        parser.error("this mutating operation requires --approve")
    actions = {"preflight": preflight, "inspect": inspect, "vector-probe": vector_probe, "forex-m2-apply-schema": apply_schema, "forex-m2-import": import_snapshot, "forex-m2-verify": verify_snapshot, "forex-m2-provenance-negative-control": provenance_negative_control}
    payload = actions[args.command]()
    print(json.dumps(payload, indent=2))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
