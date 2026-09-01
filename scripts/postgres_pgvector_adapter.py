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
    "gdelt_schema": "sql/migrations/003_m11_gdelt_h1_aggregate.sql",
    "gdelt_stage_schema": "sql/migrations/004_m11_gdelt_hourly_stage.sql",
    "m12_probe": "scripts/m12_quality_probe.py",
    "m13_probe": "scripts/m13_replay_probe.py",
    "import": "scripts/build_m2_postgres_import.py",
}
M2_SNAPSHOT_ID = "m2-m1-eurusd-h1-720"
M2_SNAPSHOT_ARTIFACT_SHA256 = "sha256:dc5384732d71091aa2279aaf6d92e8e1780c8021eacde948432ad7bc68fdabaa"
READ_ONLY = {"preflight", "inspect", "vector-probe", "forex-m2-verify", "forex-m2-provenance-negative-control", "forex-m11-verify-schema", "forex-m11-verify-data", "forex-m11-r1-verify-hour", "forex-m12-quality-probe", "forex-m13-replay-probe"}
MUTATING = {"forex-m2-apply-schema", "forex-m2-import", "forex-m11-apply-schema", "forex-m11-r1-apply-stage-schema"}


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


def apply_m11_schema() -> dict:
    relative, digest = asset("gdelt_schema")
    body = f'''schema_file="{REMOTE_FOREX}/{relative}"
test -f "$schema_file"
[[ "$(sha256sum "$schema_file" | head -c 64)" == "{digest}" ]]
docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" < "$schema_file"
printf 'FOREX_M11_GDELT_SCHEMA_APPLIED sha256:{digest}\\n' '''
    return wrap("forex_m11_apply_schema", remote(body), digest)


def apply_m11_r1_stage_schema() -> dict:
    relative, digest = asset("gdelt_stage_schema")
    body = f'''schema_file="{REMOTE_FOREX}/{relative}"
test -f "$schema_file"
[[ "$(sha256sum "$schema_file" | head -c 64)" == "{digest}" ]]
docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" < "$schema_file"
printf 'FOREX_M11_R1_STAGE_SCHEMA_APPLIED sha256:{digest}\\n' '''
    return wrap("forex_m11_r1_apply_stage_schema", remote(body), digest)


def verify_m11_schema() -> dict:
    body = '''docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT 'FOREX_M11_GDELT_SCHEMA_VERIFY_OK',
  to_regclass('forex.gdelt_h1_aggregate') IS NOT NULL,
  (SELECT count(*) FROM information_schema.columns WHERE table_schema='forex' AND table_name='gdelt_h1_aggregate'),
  (SELECT count(*) FROM pg_indexes WHERE schemaname='forex' AND indexname='gdelt_h1_aggregate_alignment_idx');" </dev/null'''
    return wrap("forex_m11_verify_schema", remote(body))


def verify_m11_data() -> dict:
    body = '''docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT 'FOREX_M11_GDELT_DATA_VERIFY_OK',
  (SELECT count(*) FROM forex.source_registry WHERE source_id='gdelt-sentiment-prototype'),
  (SELECT count(*) FROM forex.raw_observation WHERE source_id='gdelt-sentiment-prototype'),
  (SELECT count(*) FROM forex.gdelt_h1_aggregate),
  (SELECT count(DISTINCT observation_id) FROM forex.gdelt_h1_aggregate),
  'complete_interval_coverage=' || ((SELECT count(*) FROM forex.raw_observation WHERE source_id='gdelt-sentiment-prototype') = 96),
  'observed_range=' || coalesce((SELECT min(observed_at_utc)::text || ',' || max(observed_at_utc)::text FROM forex.raw_observation WHERE source_id='gdelt-sentiment-prototype'), 'none'),
  'aggregate_range=' || coalesce((SELECT min(bucket_time_utc)::text || ',' || max(bucket_time_utc)::text FROM forex.gdelt_h1_aggregate), 'none'),
  'no_article_columns=' || NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='forex' AND table_name='gdelt_h1_aggregate' AND column_name IN ('article_text','headline','url','content')),
  'provenance_linkage_ok=' || NOT EXISTS (SELECT 1 FROM forex.gdelt_h1_aggregate aggregate LEFT JOIN forex.raw_observation observation ON observation.observation_id=aggregate.observation_id WHERE observation.observation_id IS NULL),
  'context_only=' || NOT EXISTS (SELECT 1 FROM forex.gdelt_h1_aggregate WHERE uncertainty_label <> 'EXPERIMENTAL_CONTEXT_ONLY');" </dev/null'''
    return wrap("forex_m11_verify_data", remote(body))


def verify_m11_r1_hour() -> dict:
    """Inspect the most recently imported H1 context unit; no caller input."""
    body = '''docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "WITH latest AS (SELECT max(bucket_time_utc) AS bucket FROM forex.gdelt_h1_aggregate), sources AS (SELECT observation_id, source_revision, payload_sha256, available_at_utc FROM forex.raw_observation, latest WHERE source_id='gdelt-sentiment-prototype' AND observation_id LIKE 'gdelt-gkg-%' AND observed_at_utc >= latest.bucket AND observed_at_utc < latest.bucket + interval '1 hour'), aggregate AS (SELECT aggregate.observation_id, aggregate.bucket_time_utc FROM forex.gdelt_h1_aggregate aggregate, latest WHERE aggregate.bucket_time_utc=latest.bucket) SELECT 'FOREX_M11_R1_HOUR_VERIFY_OK', 'bucket=' || COALESCE((SELECT bucket::text FROM latest), 'none'), 'source_count=' || (SELECT count(*) FROM sources), 'quarters_complete=' || ((SELECT array_agg(extract(minute FROM available_at_utc - interval '15 minutes')::integer ORDER BY available_at_utc) FROM sources) = ARRAY[0,15,30,45]), 'hashes_present=' || (SELECT bool_and(payload_sha256 LIKE 'sha256:%') FROM sources), 'availability_present=' || (SELECT bool_and(available_at_utc IS NOT NULL) FROM sources), 'one_aggregate=' || ((SELECT count(*) FROM aggregate)=1), 'lineage_ok=' || EXISTS (SELECT 1 FROM aggregate JOIN forex.raw_observation observation ON observation.observation_id=aggregate.observation_id WHERE observation.observation_id LIKE 'gdelt-h1-%'), 'no_article_columns=' || NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='forex' AND table_name='gdelt_h1_aggregate' AND column_name IN ('article_text','headline','url','content')), 'context_only=' || NOT EXISTS (SELECT 1 FROM forex.gdelt_h1_aggregate WHERE uncertainty_label <> 'EXPERIMENTAL_CONTEXT_ONLY');" </dev/null'''
    return wrap("forex_m11_r1_verify_hour", remote(body))


def m12_quality_probe() -> dict:
    relative, digest = asset("m12_probe")
    body = f'''file="{REMOTE_FOREX}/{relative}"
test -f "$file"
[[ "$(sha256sum "$file" | head -c 64)" == "{digest}" ]]
cd "{REMOTE_FOREX}"
PYTHONPATH=src python3 "$file"
'''
    return wrap("forex_m12_quality_probe", remote(body), digest)


def m13_replay_probe() -> dict:
    relative, digest = asset("m13_probe")
    body = f'''file="{REMOTE_FOREX}/{relative}"
test -f "$file" && [[ "$(sha256sum "$file" | head -c 64)" == "{digest}" ]]
cd "{REMOTE_FOREX}"; PYTHONPATH=src python3 "$file"'''
    return wrap("forex_m13_replay_probe", remote(body), digest)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fixed Forex M2 PostgreSQL adapter.")
    parser.add_argument("command", choices=sorted(READ_ONLY | MUTATING))
    parser.add_argument("--approve", action="store_true")
    args = parser.parse_args(argv)
    if args.command in MUTATING and not args.approve:
        parser.error("this mutating operation requires --approve")
    actions = {"preflight": preflight, "inspect": inspect, "vector-probe": vector_probe, "forex-m2-apply-schema": apply_schema, "forex-m2-import": import_snapshot, "forex-m2-verify": verify_snapshot, "forex-m2-provenance-negative-control": provenance_negative_control, "forex-m11-apply-schema": apply_m11_schema, "forex-m11-r1-apply-stage-schema": apply_m11_r1_stage_schema, "forex-m11-verify-schema": verify_m11_schema, "forex-m11-verify-data": verify_m11_data, "forex-m11-r1-verify-hour": verify_m11_r1_hour, "forex-m12-quality-probe": m12_quality_probe, "forex-m13-replay-probe": m13_replay_probe}
    payload = actions[args.command]()
    print(json.dumps(payload, indent=2))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
