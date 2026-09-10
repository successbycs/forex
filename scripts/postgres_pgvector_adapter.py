#!/usr/bin/env python3
"""Forex-owned extraction of the fixed T480 PostgreSQL M2 adapter.

Transport, Docker, database credentials and backups stay in cs-ai-lab-infra.
This adapter owns only Forex's fixed schema, import and verification actions.
It deliberately has no SQL, URL, host, shell, MT5 or order argument.
"""

from __future__ import annotations

import argparse
import base64
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
TARGET = resolve_ssh_target(
    SETTINGS,
    [
        ROOT / ".env.t480.local",
        SHARED_ROOT / ".env.t480.local",
        Path(CONFIG["shared_lab_root"]) / ".env.t480.local",
    ],
)
REMOTE_LAB = "/home/chris/projects/cs-ai-lab-infra"
REMOTE_FOREX = "/home/chris/projects/forex"
ASSETS = {"m20_wave1_gap_reconciliation": "sql/operations/w1_reconcile_attempt_65915347.sql",
    "schema": "sql/migrations/001_m2_historical_data.sql",
    "sealed_provenance": "sql/migrations/002_m2_sealed_provenance.sql",
    "gdelt_schema": "sql/migrations/003_m11_gdelt_h1_aggregate.sql",
    "gdelt_stage_schema": "sql/migrations/004_m11_gdelt_hourly_stage.sql",
    "m12_probe": "scripts/m12_quality_probe.py",
    "m13_probe": "scripts/m13_replay_probe.py",
    "m13_query": "sql/m13_postgres_replay.sql",
    "m14_query": "sql/m14_regime_probe.sql",
    "m15_probe": "scripts/m15_baseline_probe.py",
    "m16_probe": "scripts/m16_walk_forward_probe.py",
    "m17_probe": "scripts/m17_context_probe.py",
    "m18_probe": "scripts/m18_ollama_probe.py",
    "m19_schema": "sql/migrations/005_m19_decision_model_lineage.sql",
    "m19_probe": "scripts/m19_lineage_probe.py",
    "m20_schema": "sql/migrations/006_m20_demo_trading_audit.sql",
    "m20_ledger_schema": "sql/migrations/008_m20_account_currency_pnl.sql",
    "m20_cost_ledger_schema": "sql/migrations/009_m20_trade_cost_ledger.sql",
    "m20_open_position_schema": "sql/migrations/010_m20_open_position_state.sql",
    "m20_continuous_lease_schema": "sql/migrations/011_m20_continuous_demo_lease.sql",
    "m20_outcome_reconciliation_schema": "sql/migrations/012_m20_outcome_reconciliation_revision.sql",
    "m20_regime_strategy_schema": "sql/migrations/013_m20_market_regime_strategy_ownership.sql",
    "m20_projected_cost_schema": "sql/migrations/014_m20_projected_cost_components.sql",
    "m20_multi_timeframe_context_schema": "sql/migrations/015_m20_multi_timeframe_context.sql",
    "m20_remove_trade_count_cap_schema": "sql/migrations/016_m20_remove_legacy_trade_count_cap.sql",
    "m20_unresolved_execution_schema": "sql/migrations/017_m20_unresolved_execution_state.sql",
    "m20_broker_fee_ledger_schema": "sql/migrations/018_m20_broker_fee_ledger.sql",
    "m20_persistent_risk_policy_schema": "sql/migrations/019_m20_persistent_risk_policy.sql",
    "m20_risk_resume_audit_schema": "sql/migrations/020_m20_risk_resume_audit.sql",
    "m20_fee_complete_reconciliation_ledger_schema": "sql/migrations/021_m20_fee_complete_reconciliation_ledger.sql",
    "m20_independent_risk_pauses_schema": "sql/migrations/022_m20_independent_risk_pauses.sql",
    "m20_not_submitted_execution_schema": "sql/migrations/023_m20_not_submitted_execution_state.sql",
    "m20_strategy_trial_query": "sql/m20_strategy_trial_summary.sql",
    "import": "scripts/build_m2_postgres_import.py",
}
M2_SNAPSHOT_ID = "m2-m1-eurusd-h1-720"
M2_SNAPSHOT_ARTIFACT_SHA256 = "sha256:dc5384732d71091aa2279aaf6d92e8e1780c8021eacde948432ad7bc68fdabaa"
READ_ONLY = {"forex-m20-wave1-reconciliation-context","preflight", "inspect", "vector-probe", "forex-m2-verify", "forex-m2-provenance-negative-control", "forex-m11-verify-schema", "forex-m11-verify-data", "forex-m11-r1-verify-hour", "forex-m12-quality-probe", "forex-m13-replay-probe", "forex-m14-regime-probe", "forex-m15-baseline-probe", "forex-m16-walk-forward-probe", "forex-m17-context-probe", "forex-m18-ollama-probe", "forex-m19-lineage-verify", "forex-m20-audit-verify", "forex-m20-rejection-summary", "forex-m20-lifecycle-summary", "forex-m20-current-lineage-summary", "forex-m20-unresolved-attempt-summary", "forex-m20-strategy-trial-summary", "forex-m20-mtf-context-verify", "forex-m20-mtf-context-summary", "forex-m20-risk-policy-summary"}
MUTATING = {"forex-m20-stage-wave1-gap-reconciliation", "forex-m20-apply-wave1-gap-reconciliation","forex-m20-stage-listener-release","forex-m2-apply-schema", "forex-m2-import", "forex-m11-apply-schema", "forex-m11-r1-apply-stage-schema", "forex-m19-apply-schema", "forex-m19-lineage-probe", "forex-m20-stage-schema", "forex-m20-apply-schema", "forex-m20-stage-ledger-schema", "forex-m20-apply-ledger-schema", "forex-m20-stage-cost-ledger-schema", "forex-m20-apply-cost-ledger-schema", "forex-m20-stage-open-position-schema", "forex-m20-apply-open-position-schema", "forex-m20-stage-continuous-lease-schema", "forex-m20-apply-continuous-lease-schema", "forex-m20-stage-outcome-reconciliation-schema", "forex-m20-apply-outcome-reconciliation-schema", "forex-m20-stage-regime-strategy-schema", "forex-m20-apply-regime-strategy-schema", "forex-m20-stage-projected-cost-schema", "forex-m20-apply-projected-cost-schema", "forex-m20-stage-mtf-context-schema", "forex-m20-apply-mtf-context-schema", "forex-m20-stage-remove-trade-count-cap-schema", "forex-m20-apply-remove-trade-count-cap-schema", "forex-m20-stage-unresolved-execution-schema", "forex-m20-apply-unresolved-execution-schema", "forex-m20-stage-broker-fee-ledger-schema", "forex-m20-apply-broker-fee-ledger-schema", "forex-m20-stage-persistent-risk-policy-schema", "forex-m20-apply-persistent-risk-policy-schema", "forex-m20-stage-risk-resume-audit-schema", "forex-m20-apply-risk-resume-audit-schema", "forex-m20-stage-fee-complete-reconciliation-ledger-schema", "forex-m20-apply-fee-complete-reconciliation-ledger-schema", "forex-m20-stage-strategy-trial-query", "forex-m20-stage-independent-risk-pauses-schema", "forex-m20-apply-independent-risk-pauses-schema", "forex-m20-stage-not-submitted-execution-schema", "forex-m20-apply-not-submitted-execution-schema"}


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
    relative, digest = asset("m13_query")
    body = f'''file="{REMOTE_FOREX}/{relative}"
test -f "$file" && [[ "$(sha256sum "$file" | head -c 64)" == "{digest}" ]]
cd "{REMOTE_LAB}"
cat "$file" | docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At'''
    return wrap("forex_m13_replay_probe", remote(body), digest)


def m14_regime_probe() -> dict:
    relative, digest = asset("m14_query")
    body = f'''file="{REMOTE_FOREX}/{relative}"
test -f "$file" && [[ "$(sha256sum "$file" | head -c 64)" == "{digest}" ]]
cd "{REMOTE_LAB}"
cat "$file" | docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At'''
    return wrap("forex_m14_regime_probe", remote(body), digest)


def m15_baseline_probe() -> dict:
    relative, digest = asset("m15_probe")
    body = f'''file="{REMOTE_FOREX}/{relative}"
test -f "$file" && [[ "$(sha256sum "$file" | head -c 64)" == "{digest}" ]]
cd "{REMOTE_FOREX}"
PYTHONPATH=src python3 "$file"'''
    return wrap("forex_m15_baseline_probe", remote(body), digest)


def m16_walk_forward_probe() -> dict:
    relative, digest = asset("m16_probe")
    body = f'''file="{REMOTE_FOREX}/{relative}"
test -f "$file" && [[ "$(sha256sum "$file" | head -c 64)" == "{digest}" ]]
cd "{REMOTE_FOREX}"
PYTHONPATH=src python3 "$file"'''
    return wrap("forex_m16_walk_forward_probe", remote(body), digest)


def m17_context_probe() -> dict:
    relative, digest = asset("m17_probe")
    body = f'''file="{REMOTE_FOREX}/{relative}"
test -f "$file" && [[ "$(sha256sum "$file" | head -c 64)" == "{digest}" ]]
cd "{REMOTE_FOREX}"
PYTHONPATH=src python3 "$file"'''
    return wrap("forex_m17_context_probe", remote(body), digest)


def m18_ollama_probe() -> dict:
    """Run the one fixed local M18 Ollama validation drill on the T480."""
    relative, digest = asset("m18_probe")
    body = f'''file="{REMOTE_FOREX}/{relative}"
test -f "$file" && [[ "$(sha256sum "$file" | head -c 64)" == "{digest}" ]]
cd "{REMOTE_FOREX}"
PYTHONPATH=src python3 "$file"'''
    return wrap("forex_m18_ollama_probe", remote(body), digest)


def apply_m19_schema() -> dict:
    relative, digest = asset("m19_schema")
    body = f'''file="{REMOTE_FOREX}/{relative}"
test -f "$file" && [[ "$(sha256sum "$file" | head -c 64)" == "{digest}" ]]
docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" < "$file"
printf 'FOREX_M19_SCHEMA_APPLIED sha256:{digest}\\n' '''
    return wrap("forex_m19_apply_schema", remote(body), digest)


def m19_lineage_probe() -> dict:
    relative, digest = asset("m19_probe")
    body = f'''file="{REMOTE_FOREX}/{relative}"
test -f "$file" && [[ "$(sha256sum "$file" | head -c 64)" == "{digest}" ]]
cd "{REMOTE_FOREX}"
PYTHONPATH=src python3 "$file"'''
    return wrap("forex_m19_lineage_probe", remote(body), digest)


def m19_lineage_verify() -> dict:
    body = '''docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT 'FOREX_M19_LINEAGE_VERIFY_OK',
 (SELECT count(*) FROM forex.model_inference_lineage),
 (SELECT count(*) FROM forex.research_decision_lineage),
 'model=qwen2.5:3b=' || EXISTS (SELECT 1 FROM forex.model_inference_lineage WHERE model_id='qwen2.5:3b'),
 'demo_only=' || NOT EXISTS (SELECT 1 FROM forex.model_inference_lineage WHERE source_label <> 'DEMO_ONLY_HISTORICAL'),
 'validation_results_valid=' || NOT EXISTS (SELECT 1 FROM forex.model_inference_lineage WHERE validation_result NOT IN ('PASS','REJECTED_AND_ABSTAINED')),
 'research_only=' || NOT EXISTS (SELECT 1 FROM forex.model_inference_lineage WHERE research_only IS NOT TRUE OR order_capability IS NOT FALSE),
 'hashes_present=' || NOT EXISTS (SELECT 1 FROM forex.model_inference_lineage WHERE model_definition_sha256 !~ '^sha256:[0-9a-f]{64}$' OR prompt_sha256 !~ '^sha256:[0-9a-f]{64}$' OR input_sha256 !~ '^sha256:[0-9a-f]{64}$' OR output_sha256 !~ '^sha256:[0-9a-f]{64}$'),
 'decision_linkage=' || NOT EXISTS (SELECT 1 FROM forex.research_decision_lineage decision LEFT JOIN forex.model_inference_lineage inference ON inference.inference_id=decision.inference_id WHERE inference.inference_id IS NULL OR decision.decision_state <> 'RESEARCH_ONLY'),
 'no_order_fields=' || NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='forex' AND table_name IN ('model_inference_lineage','research_decision_lineage') AND column_name IN ('order','account','credential','broker_server','execution'));" </dev/null'''
    return wrap("forex_m19_lineage_verify", remote(body))


def apply_m20_schema() -> dict:
    """Install only the hash-bound append-only M20 Demo audit schema."""
    relative, digest = asset("m20_schema")
    body = f'''file="{REMOTE_FOREX}/{relative}"
test -f "$file" && [[ "$(sha256sum "$file" | head -c 64)" == "{digest}" ]]
docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" < "$file"
printf 'FOREX_M20_DEMO_AUDIT_SCHEMA_APPLIED sha256:{digest}\\n' '''
    return wrap("forex_m20_apply_schema", remote(body), digest)


def stage_m20_schema() -> dict:
    """Stage exactly the M20 audit migration in the fixed remote checkout."""
    relative, digest = asset("m20_schema")
    source = ROOT / relative
    source_windows = subprocess.run(["wslpath", "-w", str(source)], text=True, capture_output=True, check=True).stdout.strip()
    staging_windows = r"C:\Users\chris\Documents\Code\forex-m1-probe\006_m20_demo_trading_audit.sql"
    quote = lambda value: "'" + value.replace("'", "''") + "'"
    staging_directory = r"C:\Users\chris\Documents\Code\forex-m1-probe"
    mkdir = subprocess.run(
        build_ssh_command(TARGET, "$ErrorActionPreference='Stop'; New-Item -ItemType Directory -Force -Path " + quote(staging_directory) + " | Out-Null", SETTINGS),
        text=True,
        capture_output=True,
        check=False,
    )
    if mkdir.returncode:
        return wrap("forex_m20_stage_schema", {"exit_code": mkdir.returncode, "stdout": mkdir.stdout, "stderr": mkdir.stderr, "ok": False}, digest)
    command = (
        "$ErrorActionPreference='Stop'; "
        f"& scp.exe -B -o BatchMode=yes -o StrictHostKeyChecking=yes -- {quote(source_windows)} {quote(TARGET + ':' + staging_windows)}; "
        "if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }"
    )
    encoded = base64.b64encode(command.encode("utf-16-le")).decode("ascii")
    transfer = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded], text=True, capture_output=True, check=False)
    if transfer.returncode:
        return wrap("forex_m20_stage_schema", {"exit_code": transfer.returncode, "stdout": transfer.stdout, "stderr": transfer.stderr, "ok": False}, digest)
    body = f'''source="/mnt/c/Users/chris/Documents/Code/forex-m1-probe/006_m20_demo_trading_audit.sql"
file="{REMOTE_FOREX}/{relative}"
test -f "$source" && [[ "$(sha256sum "$source" | head -c 64)" == "{digest}" ]]
mkdir -p "$(dirname "$file")"
install -m 0644 "$source" "$file"
[[ "$(sha256sum "$file" | head -c 64)" == "{digest}" ]]
printf 'FOREX_M20_DEMO_AUDIT_SCHEMA_STAGED sha256:{digest}\\n' '''
    return wrap("forex_m20_stage_schema", remote(body), digest)


def stage_m20_ledger_schema() -> dict:
    """Stage exactly the account-currency ledger migration on T480."""
    relative, digest = asset("m20_ledger_schema")
    source_windows = subprocess.run(
        ["wslpath", "-w", str(ROOT / relative)], text=True, capture_output=True, check=True
    ).stdout.strip()
    staging_directory = r"C:\Users\chris\Documents\Code\forex-m1-probe"
    staging_windows = staging_directory + r"\008_m20_account_currency_pnl.sql"
    quote = lambda value: "'" + value.replace("'", "''") + "'"
    mkdir = subprocess.run(
        build_ssh_command(
            TARGET,
            "$ErrorActionPreference='Stop'; New-Item -ItemType Directory -Force -Path "
            + quote(staging_directory) + " | Out-Null",
            SETTINGS,
        ), text=True, capture_output=True, check=False,
    )
    if mkdir.returncode:
        return wrap("forex_m20_stage_ledger_schema", {"exit_code": mkdir.returncode, "stdout": mkdir.stdout, "stderr": mkdir.stderr, "ok": False}, digest)
    command = (
        "$ErrorActionPreference='Stop'; "
        f"& scp.exe -B -o BatchMode=yes -o StrictHostKeyChecking=yes -- {quote(source_windows)} {quote(TARGET + ':' + staging_windows)}; "
        "if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }"
    )
    encoded = base64.b64encode(command.encode("utf-16-le")).decode("ascii")
    transfer = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded], text=True, capture_output=True, check=False)
    if transfer.returncode:
        return wrap("forex_m20_stage_ledger_schema", {"exit_code": transfer.returncode, "stdout": transfer.stdout, "stderr": transfer.stderr, "ok": False}, digest)
    body = f'''source="/mnt/c/Users/chris/Documents/Code/forex-m1-probe/008_m20_account_currency_pnl.sql"
file="{REMOTE_FOREX}/{relative}"
test -f "$source" && [[ "$(sha256sum "$source" | head -c 64)" == "{digest}" ]]
mkdir -p "$(dirname "$file")"
install -m 0644 "$source" "$file"
[[ "$(sha256sum "$file" | head -c 64)" == "{digest}" ]]
printf 'FOREX_M20_ACCOUNT_CURRENCY_LEDGER_STAGED sha256:{digest}\\n' '''
    return wrap("forex_m20_stage_ledger_schema", remote(body), digest)


def apply_m20_ledger_schema() -> dict:
    """Apply only the hash-bound M20 account-currency ledger migration."""
    relative, digest = asset("m20_ledger_schema")
    body = f'''file="{REMOTE_FOREX}/{relative}"
test -f "$file" && [[ "$(sha256sum "$file" | head -c 64)" == "{digest}" ]]
docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" < "$file"
printf 'FOREX_M20_ACCOUNT_CURRENCY_LEDGER_APPLIED sha256:{digest}\\n' '''
    return wrap("forex_m20_apply_ledger_schema", remote(body), digest)


def stage_m20_cost_ledger_schema() -> dict:
    """Stage exactly the M20 trade-cost ledger migration on T480."""
    relative, digest = asset("m20_cost_ledger_schema")
    source_windows = subprocess.run(
        ["wslpath", "-w", str(ROOT / relative)], text=True, capture_output=True, check=True
    ).stdout.strip()
    staging_directory = r"C:\Users\chris\Documents\Code\forex-m1-probe"
    staging_windows = staging_directory + r"\009_m20_trade_cost_ledger.sql"
    quote = lambda value: "'" + value.replace("'", "''") + "'"
    mkdir = subprocess.run(
        build_ssh_command(
            TARGET,
            "$ErrorActionPreference='Stop'; New-Item -ItemType Directory -Force -Path "
            + quote(staging_directory) + " | Out-Null",
            SETTINGS,
        ), text=True, capture_output=True, check=False,
    )
    if mkdir.returncode:
        return wrap("forex_m20_stage_cost_ledger_schema", {"exit_code": mkdir.returncode, "stdout": mkdir.stdout, "stderr": mkdir.stderr, "ok": False}, digest)
    command = (
        "$ErrorActionPreference='Stop'; "
        f"& scp.exe -B -o BatchMode=yes -o StrictHostKeyChecking=yes -- {quote(source_windows)} {quote(TARGET + ':' + staging_windows)}; "
        "if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }"
    )
    encoded = base64.b64encode(command.encode("utf-16-le")).decode("ascii")
    transfer = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded], text=True, capture_output=True, check=False)
    if transfer.returncode:
        return wrap("forex_m20_stage_cost_ledger_schema", {"exit_code": transfer.returncode, "stdout": transfer.stdout, "stderr": transfer.stderr, "ok": False}, digest)
    body = f'''source="/mnt/c/Users/chris/Documents/Code/forex-m1-probe/009_m20_trade_cost_ledger.sql"
file="{REMOTE_FOREX}/{relative}"
test -f "$source" && [[ "$(sha256sum "$source" | head -c 64)" == "{digest}" ]]
mkdir -p "$(dirname "$file")"
install -m 0644 "$source" "$file"
[[ "$(sha256sum "$file" | head -c 64)" == "{digest}" ]]
printf 'FOREX_M20_TRADE_COST_LEDGER_STAGED sha256:{digest}\\n' '''
    return wrap("forex_m20_stage_cost_ledger_schema", remote(body), digest)


def apply_m20_cost_ledger_schema() -> dict:
    """Apply only the hash-bound M20 trade-cost ledger migration."""
    relative, digest = asset("m20_cost_ledger_schema")
    body = f'''file="{REMOTE_FOREX}/{relative}"
test -f "$file" && [[ "$(sha256sum "$file" | head -c 64)" == "{digest}" ]]
docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" < "$file"
printf 'FOREX_M20_TRADE_COST_LEDGER_APPLIED sha256:{digest}\\n' '''
    return wrap("forex_m20_apply_cost_ledger_schema", remote(body), digest)


def stage_m20_open_position_schema() -> dict:
    """Stage exactly the M20 durable open-position migration on T480."""
    relative, digest = asset("m20_open_position_schema")
    source_windows = subprocess.run(
        ["wslpath", "-w", str(ROOT / relative)], text=True, capture_output=True, check=True
    ).stdout.strip()
    staging_directory = r"C:\Users\chris\Documents\Code\forex-m1-probe"
    staging_windows = staging_directory + r"\010_m20_open_position_state.sql"
    quote = lambda value: "'" + value.replace("'", "''") + "'"
    mkdir = subprocess.run(
        build_ssh_command(
            TARGET,
            "$ErrorActionPreference='Stop'; New-Item -ItemType Directory -Force -Path "
            + quote(staging_directory) + " | Out-Null",
            SETTINGS,
        ), text=True, capture_output=True, check=False,
    )
    if mkdir.returncode:
        return wrap("forex_m20_stage_open_position_schema", {"exit_code": mkdir.returncode, "stdout": mkdir.stdout, "stderr": mkdir.stderr, "ok": False}, digest)
    command = (
        "$ErrorActionPreference='Stop'; "
        f"& scp.exe -B -o BatchMode=yes -o StrictHostKeyChecking=yes -- {quote(source_windows)} {quote(TARGET + ':' + staging_windows)}; "
        "if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }"
    )
    encoded = base64.b64encode(command.encode("utf-16-le")).decode("ascii")
    transfer = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded], text=True, capture_output=True, check=False)
    if transfer.returncode:
        return wrap("forex_m20_stage_open_position_schema", {"exit_code": transfer.returncode, "stdout": transfer.stdout, "stderr": transfer.stderr, "ok": False}, digest)
    body = f'''source="/mnt/c/Users/chris/Documents/Code/forex-m1-probe/010_m20_open_position_state.sql"
file="{REMOTE_FOREX}/{relative}"
test -f "$source" && [[ "$(sha256sum "$source" | head -c 64)" == "{digest}" ]]
mkdir -p "$(dirname "$file")"
install -m 0644 "$source" "$file"
[[ "$(sha256sum "$file" | head -c 64)" == "{digest}" ]]
printf 'FOREX_M20_OPEN_POSITION_STATE_STAGED sha256:{digest}\\n' '''
    return wrap("forex_m20_stage_open_position_schema", remote(body), digest)


def apply_m20_open_position_schema() -> dict:
    """Apply only the hash-bound M20 durable open-position migration."""
    relative, digest = asset("m20_open_position_schema")
    body = f'''file="{REMOTE_FOREX}/{relative}"
test -f "$file" && [[ "$(sha256sum "$file" | head -c 64)" == "{digest}" ]]
docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" < "$file"
printf 'FOREX_M20_OPEN_POSITION_STATE_APPLIED sha256:{digest}\\n' '''
    return wrap("forex_m20_apply_open_position_schema", remote(body), digest)


def stage_m20_continuous_lease_schema() -> dict:
    """Stage the fixed M20 continuous Demo-lease migration on T480."""
    relative, digest = asset("m20_continuous_lease_schema")
    source_windows = subprocess.run(
        ["wslpath", "-w", str(ROOT / relative)], text=True, capture_output=True, check=True
    ).stdout.strip()
    staging_directory = r"C:\Users\chris\Documents\Code\forex-m1-probe"
    staging_windows = staging_directory + r"\011_m20_continuous_demo_lease.sql"
    quote = lambda value: "'" + value.replace("'", "''") + "'"
    mkdir = subprocess.run(
        build_ssh_command(
            TARGET,
            "$ErrorActionPreference='Stop'; New-Item -ItemType Directory -Force -Path "
            + quote(staging_directory) + " | Out-Null",
            SETTINGS,
        ), text=True, capture_output=True, check=False,
    )
    if mkdir.returncode:
        return wrap("forex_m20_stage_continuous_lease_schema", {"exit_code": mkdir.returncode, "stdout": mkdir.stdout, "stderr": mkdir.stderr, "ok": False}, digest)
    command = (
        "$ErrorActionPreference='Stop'; "
        f"& scp.exe -B -o BatchMode=yes -o StrictHostKeyChecking=yes -- {quote(source_windows)} {quote(TARGET + ':' + staging_windows)}; "
        "if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }"
    )
    encoded = base64.b64encode(command.encode("utf-16-le")).decode("ascii")
    transfer = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded], text=True, capture_output=True, check=False)
    if transfer.returncode:
        return wrap("forex_m20_stage_continuous_lease_schema", {"exit_code": transfer.returncode, "stdout": transfer.stdout, "stderr": transfer.stderr, "ok": False}, digest)
    body = f'''source="/mnt/c/Users/chris/Documents/Code/forex-m1-probe/011_m20_continuous_demo_lease.sql"
file="{REMOTE_FOREX}/{relative}"
test -f "$source" && [[ "$(sha256sum "$source" | head -c 64)" == "{digest}" ]]
mkdir -p "$(dirname "$file")"
install -m 0644 "$source" "$file"
[[ "$(sha256sum "$file" | head -c 64)" == "{digest}" ]]
printf 'FOREX_M20_CONTINUOUS_LEASE_SCHEMA_STAGED sha256:{digest}\\n' '''
    return wrap("forex_m20_stage_continuous_lease_schema", remote(body), digest)


def apply_m20_continuous_lease_schema() -> dict:
    """Apply only the hash-bound continuous Demo-lease schema remediation."""
    relative, digest = asset("m20_continuous_lease_schema")
    body = f"file='{REMOTE_FOREX}/{relative}'; test -f \"$file\" && [[ \"$(sha256sum \"$file\" | head -c 64)\" == '{digest}' ]]; docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U \"$POSTGRES_USER\" -d \"$POSTGRES_DB\" < \"$file\"; printf 'FOREX_M20_CONTINUOUS_LEASE_SCHEMA_APPLIED sha256:{digest}\\n'"
    return wrap("forex_m20_apply_continuous_lease_schema", remote(body), digest)


def stage_m20_outcome_reconciliation_schema() -> dict:
    """Stage the fixed append-only M20 reconciliation-overlay migration."""
    relative, digest = asset("m20_outcome_reconciliation_schema")
    source_windows = subprocess.run(
        ["wslpath", "-w", str(ROOT / relative)], text=True, capture_output=True, check=True
    ).stdout.strip()
    staging_directory = r"C:\Users\chris\Documents\Code\forex-m1-probe"
    staging_windows = staging_directory + r"\012_m20_outcome_reconciliation_revision.sql"
    quote = lambda value: "'" + value.replace("'", "''") + "'"
    mkdir = subprocess.run(
        build_ssh_command(
            TARGET,
            "$ErrorActionPreference='Stop'; New-Item -ItemType Directory -Force -Path "
            + quote(staging_directory) + " | Out-Null",
            SETTINGS,
        ), text=True, capture_output=True, check=False,
    )
    if mkdir.returncode:
        return wrap("forex_m20_stage_outcome_reconciliation_schema", {"exit_code": mkdir.returncode, "stdout": mkdir.stdout, "stderr": mkdir.stderr, "ok": False}, digest)
    command = (
        "$ErrorActionPreference='Stop'; "
        f"& scp.exe -B -o BatchMode=yes -o StrictHostKeyChecking=yes -- {quote(source_windows)} {quote(TARGET + ':' + staging_windows)}; "
        "if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }"
    )
    encoded = base64.b64encode(command.encode("utf-16-le")).decode("ascii")
    transfer = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded], text=True, capture_output=True, check=False)
    if transfer.returncode:
        return wrap("forex_m20_stage_outcome_reconciliation_schema", {"exit_code": transfer.returncode, "stdout": transfer.stdout, "stderr": transfer.stderr, "ok": False}, digest)
    body = f'''source="/mnt/c/Users/chris/Documents/Code/forex-m1-probe/012_m20_outcome_reconciliation_revision.sql"
file="{REMOTE_FOREX}/{relative}"
test -f "$source" && [[ "$(sha256sum "$source" | head -c 64)" == "{digest}" ]]
mkdir -p "$(dirname "$file")"
install -m 0644 "$source" "$file"
[[ "$(sha256sum "$file" | head -c 64)" == "{digest}" ]]
printf 'FOREX_M20_OUTCOME_RECONCILIATION_SCHEMA_STAGED sha256:{digest}\\n' '''
    return wrap("forex_m20_stage_outcome_reconciliation_schema", remote(body), digest)


def apply_m20_outcome_reconciliation_schema() -> dict:
    """Apply only the hash-bound append-only M20 reconciliation overlay."""
    relative, digest = asset("m20_outcome_reconciliation_schema")
    body = f'''file="{REMOTE_FOREX}/{relative}"
test -f "$file" && [[ "$(sha256sum "$file" | head -c 64)" == "{digest}" ]]
docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" < "$file"
printf 'FOREX_M20_OUTCOME_RECONCILIATION_SCHEMA_APPLIED sha256:{digest}\\n' '''
    return wrap("forex_m20_apply_outcome_reconciliation_schema", remote(body), digest)


def stage_m20_regime_strategy_schema() -> dict:
    """Stage M20's hash-bound append-only market-regime migration on T480."""
    relative, digest = asset("m20_regime_strategy_schema")
    source_windows = subprocess.run(["wslpath", "-w", str(ROOT / relative)], text=True, capture_output=True, check=True).stdout.strip()
    staging_directory = r"C:\\Users\\chris\\Documents\\Code\\forex-m1-probe"
    staging_windows = staging_directory + r"\013_m20_market_regime_strategy_ownership.sql"
    quote = lambda value: "'" + value.replace("'", "''") + "'"
    mkdir = subprocess.run(build_ssh_command(TARGET, "$ErrorActionPreference='Stop'; New-Item -ItemType Directory -Force -Path " + quote(staging_directory) + " | Out-Null", SETTINGS), text=True, capture_output=True, check=False)
    if mkdir.returncode:
        return wrap("forex_m20_stage_regime_strategy_schema", {"exit_code": mkdir.returncode, "stdout": mkdir.stdout, "stderr": mkdir.stderr, "ok": False}, digest)
    command = "$ErrorActionPreference='Stop'; " + f"& scp.exe -B -o BatchMode=yes -o StrictHostKeyChecking=yes -- {quote(source_windows)} {quote(TARGET + ':' + staging_windows)}; " + "if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }"
    transfer = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", base64.b64encode(command.encode("utf-16-le")).decode("ascii")], text=True, capture_output=True, check=False)
    if transfer.returncode:
        return wrap("forex_m20_stage_regime_strategy_schema", {"exit_code": transfer.returncode, "stdout": transfer.stdout, "stderr": transfer.stderr, "ok": False}, digest)
    body = f'''source="/mnt/c/Users/chris/Documents/Code/forex-m1-probe/013_m20_market_regime_strategy_ownership.sql"
file="{REMOTE_FOREX}/{relative}"
test -f "$source" && [[ "$(sha256sum "$source" | head -c 64)" == "{digest}" ]]
mkdir -p "$(dirname "$file")"
install -m 0644 "$source" "$file"
[[ "$(sha256sum "$file" | head -c 64)" == "{digest}" ]]
printf 'FOREX_M20_REGIME_STRATEGY_SCHEMA_STAGED sha256:{digest}\\n' '''
    return wrap("forex_m20_stage_regime_strategy_schema", remote(body), digest)


def apply_m20_regime_strategy_schema() -> dict:
    """Apply only the staged hash-bound M20 regime/ownership schema."""
    relative, digest = asset("m20_regime_strategy_schema")
    body = f'''file="{REMOTE_FOREX}/{relative}"
test -f "$file" && [[ "$(sha256sum "$file" | head -c 64)" == "{digest}" ]]
docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" < "$file"
printf 'FOREX_M20_REGIME_STRATEGY_SCHEMA_APPLIED sha256:{digest}\\n' '''
    return wrap("forex_m20_apply_regime_strategy_schema", remote(body), digest)


def stage_m20_projected_cost_schema() -> dict:
    """Stage the hash-bound M20 projected-cost metadata migration on T480."""
    relative, digest = asset("m20_projected_cost_schema")
    source_windows = subprocess.run(["wslpath", "-w", str(ROOT / relative)], text=True, capture_output=True, check=True).stdout.strip()
    staging_directory = r"C:\\Users\\chris\\Documents\\Code\\forex-m1-probe"
    staging_windows = staging_directory + r"\014_m20_projected_cost_components.sql"
    quote = lambda value: "'" + value.replace("'", "''") + "'"
    mkdir = subprocess.run(build_ssh_command(TARGET, "$ErrorActionPreference='Stop'; New-Item -ItemType Directory -Force -Path " + quote(staging_directory) + " | Out-Null", SETTINGS), text=True, capture_output=True, check=False)
    if mkdir.returncode:
        return wrap("forex_m20_stage_projected_cost_schema", {"exit_code": mkdir.returncode, "stdout": mkdir.stdout, "stderr": mkdir.stderr, "ok": False}, digest)
    command = "$ErrorActionPreference='Stop'; " + f"& scp.exe -B -o BatchMode=yes -o StrictHostKeyChecking=yes -- {quote(source_windows)} {quote(TARGET + ':' + staging_windows)}; " + "if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }"
    transfer = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", base64.b64encode(command.encode("utf-16-le")).decode("ascii")], text=True, capture_output=True, check=False)
    if transfer.returncode:
        return wrap("forex_m20_stage_projected_cost_schema", {"exit_code": transfer.returncode, "stdout": transfer.stdout, "stderr": transfer.stderr, "ok": False}, digest)
    body = f'''source="/mnt/c/Users/chris/Documents/Code/forex-m1-probe/014_m20_projected_cost_components.sql"
file="{REMOTE_FOREX}/{relative}"
test -f "$source" && [[ "$(sha256sum "$source" | head -c 64)" == "{digest}" ]]
mkdir -p "$(dirname "$file")"
install -m 0644 "$source" "$file"
[[ "$(sha256sum "$file" | head -c 64)" == "{digest}" ]]
printf "FOREX_M20_PROJECTED_COST_SCHEMA_STAGED sha256:{digest}\\n" '''
    return wrap("forex_m20_stage_projected_cost_schema", remote(body), digest)


def apply_m20_projected_cost_schema() -> dict:
    """Apply only the staged hash-bound M20 projected-cost metadata schema."""
    relative, digest = asset("m20_projected_cost_schema")
    body = f'''file="{REMOTE_FOREX}/{relative}"
test -f "$file" && [[ "$(sha256sum "$file" | head -c 64)" == "{digest}" ]]
docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" < "$file"
printf "FOREX_M20_PROJECTED_COST_SCHEMA_APPLIED sha256:{digest}\\n" '''
    return wrap("forex_m20_apply_projected_cost_schema", remote(body), digest)


def stage_m20_multi_timeframe_context_schema() -> dict:
    """Stage, but do not apply, the M20.12 observational M5/H1 schema."""
    relative, digest = asset("m20_multi_timeframe_context_schema")
    source_windows = subprocess.run(["wslpath", "-w", str(ROOT / relative)], text=True, capture_output=True, check=True).stdout.strip()
    staging_directory = r"C:\\Users\\chris\\Documents\\Code\\forex-m1-probe"
    staging_windows = staging_directory + r"\015_m20_multi_timeframe_context.sql"
    quote = lambda value: "'" + value.replace("'", "''") + "'"
    mkdir = subprocess.run(build_ssh_command(TARGET, "$ErrorActionPreference='Stop'; New-Item -ItemType Directory -Force -Path " + quote(staging_directory) + " | Out-Null", SETTINGS), text=True, capture_output=True, check=False)
    if mkdir.returncode:
        return wrap("forex_m20_stage_mtf_context_schema", {"exit_code": mkdir.returncode, "stdout": mkdir.stdout, "stderr": mkdir.stderr, "ok": False}, digest)
    command = "$ErrorActionPreference='Stop'; " + f"& scp.exe -B -o BatchMode=yes -o StrictHostKeyChecking=yes -- {quote(source_windows)} {quote(TARGET + ':' + staging_windows)}; " + "if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }"
    transfer = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", base64.b64encode(command.encode("utf-16-le")).decode("ascii")], text=True, capture_output=True, check=False)
    if transfer.returncode:
        return wrap("forex_m20_stage_mtf_context_schema", {"exit_code": transfer.returncode, "stdout": transfer.stdout, "stderr": transfer.stderr, "ok": False}, digest)
    body = f'''source="/mnt/c/Users/chris/Documents/Code/forex-m1-probe/015_m20_multi_timeframe_context.sql"
file="{REMOTE_FOREX}/{relative}"
test -f "$source" && [[ "$(sha256sum "$source" | head -c 64)" == "{digest}" ]]
mkdir -p "$(dirname "$file")"
install -m 0644 "$source" "$file"
[[ "$(sha256sum "$file" | head -c 64)" == "{digest}" ]]
printf 'FOREX_M20_MTF_CONTEXT_SCHEMA_STAGED sha256:{digest}\\n' '''
    return wrap("forex_m20_stage_mtf_context_schema", remote(body), digest)


def apply_m20_multi_timeframe_context_schema() -> dict:
    """Apply only a previously staged, hash-bound M20.12 context schema."""
    relative, digest = asset("m20_multi_timeframe_context_schema")
    body = f'''file="{REMOTE_FOREX}/{relative}"
test -f "$file" && [[ "$(sha256sum "$file" | head -c 64)" == "{digest}" ]]
docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" < "$file"
printf 'FOREX_M20_MTF_CONTEXT_SCHEMA_APPLIED sha256:{digest}\\n' '''
    return wrap("forex_m20_apply_mtf_context_schema", remote(body), digest)


def stage_m20_remove_trade_count_cap_schema() -> dict:
    relative, digest = asset("m20_remove_trade_count_cap_schema")
    source = subprocess.run(["wslpath", "-w", str(ROOT / relative)], text=True, capture_output=True, check=True).stdout.strip()
    staged = r"C:\\Users\\chris\\Documents\\Code\\forex-m1-probe\\016_m20_remove_legacy_trade_count_cap.sql"
    quote = lambda value: "'" + value.replace("'", "''") + "'"
    command = "$ErrorActionPreference='Stop'; & scp.exe -B -o BatchMode=yes -o StrictHostKeyChecking=yes -- " + quote(source) + " " + quote(TARGET + ":" + staged) + "; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }"
    transfer = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", base64.b64encode(command.encode("utf-16-le")).decode("ascii")], text=True, capture_output=True, check=False)
    if transfer.returncode:
        return wrap("forex_m20_stage_remove_trade_count_cap_schema", {"exit_code": transfer.returncode, "stdout": transfer.stdout, "stderr": transfer.stderr, "ok": False}, digest)
    body = f'''file="{REMOTE_FOREX}/{relative}"
test -f /mnt/c/Users/chris/Documents/Code/forex-m1-probe/016_m20_remove_legacy_trade_count_cap.sql
install -m 0644 /mnt/c/Users/chris/Documents/Code/forex-m1-probe/016_m20_remove_legacy_trade_count_cap.sql "$file"
[[ "$(sha256sum "$file" | head -c 64)" == "{digest}" ]]'''
    return wrap("forex_m20_stage_remove_trade_count_cap_schema", remote(body), digest)


def apply_m20_remove_trade_count_cap_schema() -> dict:
    relative, digest = asset("m20_remove_trade_count_cap_schema")
    body = f'''file="{REMOTE_FOREX}/{relative}"
test -f "$file" && [[ "$(sha256sum "$file" | head -c 64)" == "{digest}" ]]
docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" < "$file"'''
    return wrap("forex_m20_apply_remove_trade_count_cap_schema", remote(body), digest)


def stage_m20_unresolved_execution_schema() -> dict:
    """Stage the hash-bound schema for unresolved broker execution only."""
    relative, digest = asset("m20_unresolved_execution_schema")
    source = subprocess.run(["wslpath", "-w", str(ROOT / relative)], text=True, capture_output=True, check=True).stdout.strip()
    staged = r"C:\\Users\\chris\\Documents\\Code\\forex-m1-probe\\017_m20_unresolved_execution_state.sql"
    quote = lambda value: "'" + value.replace("'", "''") + "'"
    command = "$ErrorActionPreference='Stop'; & scp.exe -B -o BatchMode=yes -o StrictHostKeyChecking=yes -- " + quote(source) + " " + quote(TARGET + ":" + staged) + "; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }"
    transfer = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", base64.b64encode(command.encode("utf-16-le")).decode("ascii")], text=True, capture_output=True, check=False)
    if transfer.returncode:
        return wrap("forex_m20_stage_unresolved_execution_schema", {"exit_code": transfer.returncode, "stdout": transfer.stdout, "stderr": transfer.stderr, "ok": False}, digest)
    body = f'''file="{REMOTE_FOREX}/{relative}"
test -f /mnt/c/Users/chris/Documents/Code/forex-m1-probe/017_m20_unresolved_execution_state.sql
install -m 0644 /mnt/c/Users/chris/Documents/Code/forex-m1-probe/017_m20_unresolved_execution_state.sql "$file"
[[ "$(sha256sum "$file" | head -c 64)" == "{digest}" ]]'''
    return wrap("forex_m20_stage_unresolved_execution_schema", remote(body), digest)


def apply_m20_unresolved_execution_schema() -> dict:
    relative, digest = asset("m20_unresolved_execution_schema")
    body = f'''file="{REMOTE_FOREX}/{relative}"
test -f "$file" && [[ "$(sha256sum "$file" | head -c 64)" == "{digest}" ]]
docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" < "$file"'''
    return wrap("forex_m20_apply_unresolved_execution_schema", remote(body), digest)


def stage_m20_broker_fee_ledger_schema() -> dict:
    """Stage the hash-bound broker-fee ledger migration only."""
    relative, digest = asset("m20_broker_fee_ledger_schema")
    source = subprocess.run(["wslpath", "-w", str(ROOT / relative)], text=True, capture_output=True, check=True).stdout.strip()
    staged = r"C:\\Users\\chris\\Documents\\Code\\forex-m1-probe\\018_m20_broker_fee_ledger.sql"
    quote = lambda value: "'" + value.replace("'", "''") + "'"
    command = "$ErrorActionPreference='Stop'; & scp.exe -B -o BatchMode=yes -o StrictHostKeyChecking=yes -- " + quote(source) + " " + quote(TARGET + ":" + staged) + "; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }"
    transfer = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", base64.b64encode(command.encode("utf-16-le")).decode("ascii")], text=True, capture_output=True, check=False)
    if transfer.returncode:
        return wrap("forex_m20_stage_broker_fee_ledger_schema", {"exit_code": transfer.returncode, "stdout": transfer.stdout, "stderr": transfer.stderr, "ok": False}, digest)
    body = f'''file="{REMOTE_FOREX}/{relative}"
test -f /mnt/c/Users/chris/Documents/Code/forex-m1-probe/018_m20_broker_fee_ledger.sql
install -m 0644 /mnt/c/Users/chris/Documents/Code/forex-m1-probe/018_m20_broker_fee_ledger.sql "$file"
[[ "$(sha256sum "$file" | head -c 64)" == "{digest}" ]]'''
    return wrap("forex_m20_stage_broker_fee_ledger_schema", remote(body), digest)


def apply_m20_broker_fee_ledger_schema() -> dict:
    relative, digest = asset("m20_broker_fee_ledger_schema")
    body = f'''file="{REMOTE_FOREX}/{relative}"
test -f "$file" && [[ "$(sha256sum "$file" | head -c 64)" == "{digest}" ]]
docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" < "$file"'''
    return wrap("forex_m20_apply_broker_fee_ledger_schema", remote(body), digest)


def stage_m20_persistent_risk_policy_schema() -> dict:
    """Stage the hash-bound persistent-risk policy migration only."""
    relative, digest = asset("m20_persistent_risk_policy_schema")
    source = subprocess.run(["wslpath", "-w", str(ROOT / relative)], text=True, capture_output=True, check=True).stdout.strip()
    staged = r"C:\\Users\\chris\\Documents\\Code\\forex-m1-probe\\019_m20_persistent_risk_policy.sql"
    quote = lambda value: "'" + value.replace("'", "''") + "'"
    command = "$ErrorActionPreference='Stop'; & scp.exe -B -o BatchMode=yes -o StrictHostKeyChecking=yes -- " + quote(source) + " " + quote(TARGET + ":" + staged) + "; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }"
    transfer = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", base64.b64encode(command.encode("utf-16-le")).decode("ascii")], text=True, capture_output=True, check=False)
    if transfer.returncode:
        return wrap("forex_m20_stage_persistent_risk_policy_schema", {"exit_code": transfer.returncode, "stdout": transfer.stdout, "stderr": transfer.stderr, "ok": False}, digest)
    body = f'''file="{REMOTE_FOREX}/{relative}"
test -f /mnt/c/Users/chris/Documents/Code/forex-m1-probe/019_m20_persistent_risk_policy.sql
install -m 0644 /mnt/c/Users/chris/Documents/Code/forex-m1-probe/019_m20_persistent_risk_policy.sql "$file"
[[ "$(sha256sum "$file" | head -c 64)" == "{digest}" ]]'''
    return wrap("forex_m20_stage_persistent_risk_policy_schema", remote(body), digest)


def apply_m20_persistent_risk_policy_schema() -> dict:
    relative, digest = asset("m20_persistent_risk_policy_schema")
    body = f'''file="{REMOTE_FOREX}/{relative}"
test -f "$file" && [[ "$(sha256sum "$file" | head -c 64)" == "{digest}" ]]
docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" < "$file"'''
    return wrap("forex_m20_apply_persistent_risk_policy_schema", remote(body), digest)


def stage_m20_risk_resume_audit_schema() -> dict:
    """Stage the hash-bound append-only risk-resume audit migration only."""
    relative, digest = asset("m20_risk_resume_audit_schema")
    source = subprocess.run(["wslpath", "-w", str(ROOT / relative)], text=True, capture_output=True, check=True).stdout.strip()
    staged = r"C:\\Users\\chris\\Documents\\Code\\forex-m1-probe\\020_m20_risk_resume_audit.sql"
    quote = lambda value: "'" + value.replace("'", "''") + "'"
    command = "$ErrorActionPreference='Stop'; & scp.exe -B -o BatchMode=yes -o StrictHostKeyChecking=yes -- " + quote(source) + " " + quote(TARGET + ":" + staged) + "; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }"
    transfer = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", base64.b64encode(command.encode("utf-16-le")).decode("ascii")], text=True, capture_output=True, check=False)
    if transfer.returncode:
        return wrap("forex_m20_stage_risk_resume_audit_schema", {"exit_code": transfer.returncode, "stdout": transfer.stdout, "stderr": transfer.stderr, "ok": False}, digest)
    body = f'''file="{REMOTE_FOREX}/{relative}"
test -f /mnt/c/Users/chris/Documents/Code/forex-m1-probe/020_m20_risk_resume_audit.sql
install -m 0644 /mnt/c/Users/chris/Documents/Code/forex-m1-probe/020_m20_risk_resume_audit.sql "$file"
[[ "$(sha256sum "$file" | head -c 64)" == "{digest}" ]]'''
    return wrap("forex_m20_stage_risk_resume_audit_schema", remote(body), digest)


def apply_m20_risk_resume_audit_schema() -> dict:
    relative, digest = asset("m20_risk_resume_audit_schema")
    body = f'''file="{REMOTE_FOREX}/{relative}"
test -f "$file" && [[ "$(sha256sum "$file" | head -c 64)" == "{digest}" ]]
docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" < "$file"'''
    return wrap("forex_m20_apply_risk_resume_audit_schema", remote(body), digest)


def stage_m20_listener_release() -> dict:
    """Copy only the four fixed payloads; prepare/install verify hashes separately.

    Reuse the Windows SCP staging path used for Forex migrations. Long inline
    Base64 payloads can be rejected before ssh.exe starts on the T16.
    """
    names = ("m20_demo_listener_service", "m20_demo_trading_session", "m20_postgres_audit_bridge", "m20_discord_trade_notification")
    sources = [ROOT / "t480" / (name + ".py") for name in names]
    release_id = hashlib.sha256(b"".join(path.read_bytes() for path in sources)).hexdigest()[:16]
    quote = lambda value: "'" + value.replace("'", "''") + "'"
    release_directory = "C:\\ProgramData\\ForexListener\\releases\\" + release_id
    mkdir = subprocess.run(
        build_ssh_command(TARGET, "$ErrorActionPreference='Stop'; New-Item -ItemType Directory -Force -Path " + quote(release_directory) + " | Out-Null", SETTINGS),
        text=True, capture_output=True, check=False,
    )
    if mkdir.returncode:
        return wrap("forex_m20_stage_listener_release", {"exit_code": mkdir.returncode, "stdout": "", "stderr": mkdir.stderr, "ok": False})
    transfers = []
    for name, path in zip(names, sources):
        source = subprocess.run(["wslpath", "-w", str(path)], text=True, capture_output=True, check=True).stdout.strip()
        destination = TARGET + ":C:/ProgramData/ForexListener/releases/" + release_id + "/" + name + ".payload"
        command = "$ErrorActionPreference='Stop'; & scp.exe -B -o BatchMode=yes -o StrictHostKeyChecking=yes -- " + quote(source) + " " + quote(destination) + "; exit $LASTEXITCODE"
        transfer = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", base64.b64encode(command.encode("utf-16-le")).decode("ascii")], text=True, capture_output=True, check=False)
        transfers.append({"payload": name, "exit_code": transfer.returncode})
        if transfer.returncode:
            return wrap("forex_m20_stage_listener_release", {"exit_code": transfer.returncode, "stdout": json.dumps(transfers), "stderr": transfer.stderr, "ok": False})
    return wrap("forex_m20_stage_listener_release", {"exit_code": 0, "stdout": json.dumps({"release_id": release_id, "transfers": transfers, "hash_verification": "REQUIRED_BEFORE_INSTALL"}), "stderr": "", "ok": True})


def stage_m20_independent_risk_pauses_schema() -> dict:
    """Stage the hash-bound independent-pause migration without applying it."""
    relative, digest = asset("m20_independent_risk_pauses_schema")
    source = subprocess.run(["wslpath", "-w", str(ROOT / relative)], text=True, capture_output=True, check=True).stdout.strip()
    staged = r"C:\\Users\\chris\\Documents\\Code\\forex-m1-probe\\022_m20_independent_risk_pauses.sql"
    quote = lambda value: "'" + value.replace("'", "''") + "'"
    command = "$ErrorActionPreference='Stop'; & scp.exe -B -o BatchMode=yes -o StrictHostKeyChecking=yes -- " + quote(source) + " " + quote(TARGET + ":" + staged) + "; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }"
    transfer = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", base64.b64encode(command.encode("utf-16-le")).decode("ascii")], text=True, capture_output=True, check=False)
    if transfer.returncode:
        return wrap("forex_m20_stage_independent_risk_pauses_schema", {"exit_code": transfer.returncode, "stdout": transfer.stdout, "stderr": transfer.stderr, "ok": False}, digest)
    body = f'''file="{REMOTE_FOREX}/{relative}"
test -f /mnt/c/Users/chris/Documents/Code/forex-m1-probe/022_m20_independent_risk_pauses.sql
install -m 0644 /mnt/c/Users/chris/Documents/Code/forex-m1-probe/022_m20_independent_risk_pauses.sql "$file"
[[ "$(sha256sum "$file" | head -c 64)" == "{digest}" ]]'''
    return wrap("forex_m20_stage_independent_risk_pauses_schema", remote(body), digest)


def apply_m20_independent_risk_pauses_schema() -> dict:
    relative, digest = asset("m20_independent_risk_pauses_schema")
    body = f'''file="{REMOTE_FOREX}/{relative}"
test -f "$file" && [[ "$(sha256sum "$file" | head -c 64)" == "{digest}" ]]
docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" < "$file"'''
    return wrap("forex_m20_apply_independent_risk_pauses_schema", remote(body), digest)


def stage_m20_not_submitted_execution_schema() -> dict:
    """Stage the fixed hash-bound terminal non-submission migration only."""
    relative, digest = asset("m20_not_submitted_execution_schema")
    source = subprocess.run(["wslpath", "-w", str(ROOT / relative)], text=True, capture_output=True, check=True).stdout.strip()
    staged = r"C:\\Users\\chris\\Documents\\Code\\forex-m1-probe\\023_m20_not_submitted_execution_state.sql"
    quote = lambda value: "'" + value.replace("'", "''") + "'"
    command = "$ErrorActionPreference='Stop'; & scp.exe -B -o BatchMode=yes -o StrictHostKeyChecking=yes -- " + quote(source) + " " + quote(TARGET + ":" + staged) + "; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }"
    transfer = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", base64.b64encode(command.encode("utf-16-le")).decode("ascii")], text=True, capture_output=True, check=False)
    if transfer.returncode:
        return wrap("forex_m20_stage_not_submitted_execution_schema", {"exit_code": transfer.returncode, "stdout": transfer.stdout, "stderr": transfer.stderr, "ok": False}, digest)
    body = f'file="{REMOTE_FOREX}/{relative}"\ntest -f /mnt/c/Users/chris/Documents/Code/forex-m1-probe/023_m20_not_submitted_execution_state.sql\ninstall -m 0644 /mnt/c/Users/chris/Documents/Code/forex-m1-probe/023_m20_not_submitted_execution_state.sql "$file"\n[[ "$(sha256sum "$file" | head -c 64)" == "{digest}" ]]'
    return wrap("forex_m20_stage_not_submitted_execution_schema", remote(body), digest)


def apply_m20_not_submitted_execution_schema() -> dict:
    relative, digest = asset("m20_not_submitted_execution_schema")
    body = f'file="{REMOTE_FOREX}/{relative}"\ntest -f "$file" && [[ "$(sha256sum "$file" | head -c 64)" == "{digest}" ]]\ndocker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" < "$file"'
    return wrap("forex_m20_apply_not_submitted_execution_schema", remote(body), digest)


def stage_m20_wave1_gap_reconciliation() -> dict:
    """Stage the hash-bound independent-pause migration without applying it."""
    relative, digest = asset("m20_wave1_gap_reconciliation")
    source = subprocess.run(["wslpath", "-w", str(ROOT / relative)], text=True, capture_output=True, check=True).stdout.strip()
    staged = r"C:\\Users\\chris\\Documents\\Code\\forex-m1-probe\\w1_reconcile_attempt_65915347.sql"
    quote = lambda value: "'" + value.replace("'", "''") + "'"
    command = "$ErrorActionPreference='Stop'; & scp.exe -B -o BatchMode=yes -o StrictHostKeyChecking=yes -- " + quote(source) + " " + quote(TARGET + ":" + staged) + "; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }"
    transfer = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", base64.b64encode(command.encode("utf-16-le")).decode("ascii")], text=True, capture_output=True, check=False)
    if transfer.returncode:
        return wrap("forex_m20_stage_wave1_gap_reconciliation", {"exit_code": transfer.returncode, "stdout": transfer.stdout, "stderr": transfer.stderr, "ok": False}, digest)
    body = f'''file="{REMOTE_FOREX}/{relative}"
mkdir -p "$(dirname "$file")"
test -f /mnt/c/Users/chris/Documents/Code/forex-m1-probe/w1_reconcile_attempt_65915347.sql
install -m 0644 /mnt/c/Users/chris/Documents/Code/forex-m1-probe/w1_reconcile_attempt_65915347.sql "$file"
[[ "$(sha256sum "$file" | head -c 64)" == "{digest}" ]]'''
    return wrap("forex_m20_stage_wave1_gap_reconciliation", remote(body), digest)


def apply_m20_wave1_gap_reconciliation() -> dict:
    relative, digest = asset("m20_wave1_gap_reconciliation")
    body = f'''file="{REMOTE_FOREX}/{relative}"
test -f "$file" && [[ "$(sha256sum "$file" | head -c 64)" == "{digest}" ]]
docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" < "$file"'''
    return wrap("forex_m20_apply_wave1_gap_reconciliation", remote(body), digest)


def stage_m20_fee_complete_reconciliation_ledger_schema() -> dict:
    """Stage the hash-bound append-only fee-complete reconciliation ledger migration only."""
    relative, digest = asset("m20_fee_complete_reconciliation_ledger_schema")
    source = subprocess.run(["wslpath", "-w", str(ROOT / relative)], text=True, capture_output=True, check=True).stdout.strip()
    staged = r"C:\\Users\\chris\\Documents\\Code\\forex-m1-probe\\021_m20_fee_complete_reconciliation_ledger.sql"
    quote = lambda value: "'" + value.replace("'", "''") + "'"
    command = "$ErrorActionPreference='Stop'; & scp.exe -B -o BatchMode=yes -o StrictHostKeyChecking=yes -- " + quote(source) + " " + quote(TARGET + ":" + staged) + "; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }"
    transfer = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", base64.b64encode(command.encode("utf-16-le")).decode("ascii")], text=True, capture_output=True, check=False)
    if transfer.returncode:
        return wrap("forex_m20_stage_fee_complete_reconciliation_ledger_schema", {"exit_code": transfer.returncode, "stdout": transfer.stdout, "stderr": transfer.stderr, "ok": False}, digest)
    body = f'''file="{REMOTE_FOREX}/{relative}"
test -f /mnt/c/Users/chris/Documents/Code/forex-m1-probe/021_m20_fee_complete_reconciliation_ledger.sql
install -m 0644 /mnt/c/Users/chris/Documents/Code/forex-m1-probe/021_m20_fee_complete_reconciliation_ledger.sql "$file"
[[ "$(sha256sum "$file" | head -c 64)" == "{digest}" ]]'''
    return wrap("forex_m20_stage_fee_complete_reconciliation_ledger_schema", remote(body), digest)


def apply_m20_fee_complete_reconciliation_ledger_schema() -> dict:
    relative, digest = asset("m20_fee_complete_reconciliation_ledger_schema")
    body = f'''file="{REMOTE_FOREX}/{relative}"
test -f "$file" && [[ "$(sha256sum "$file" | head -c 64)" == "{digest}" ]]
docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" < "$file"'''
    return wrap("forex_m20_apply_fee_complete_reconciliation_ledger_schema", remote(body), digest)


def m20_wave1_reconciliation_context() -> dict:
    body = """docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT json_build_object('attempt',(SELECT row_to_json(a) FROM forex.demo_execution_attempt a WHERE attempt_id='65915347-d4a1-53e2-94a2-dccfc41a164f'),'proposal',(SELECT row_to_json(p) FROM forex.demo_trade_proposal p WHERE proposal_id='a8eca0f8-7f7b-5198-8154-bcdfcb328147'),'selection',(SELECT row_to_json(s) FROM forex.demo_strategy_selection s WHERE proposal_id='a8eca0f8-7f7b-5198-8154-bcdfcb328147'),'risk',(SELECT row_to_json(r) FROM forex.demo_risk_policy_state r),'open_states',(SELECT COALESCE(json_agg(row_to_json(o)),'[]'::json) FROM forex.demo_open_position_state o),'outcomes',(SELECT COALESCE(json_agg(row_to_json(o)),'[]'::json) FROM forex.demo_trade_outcome o WHERE closed_at_utc >= '2026-09-07T00:00:00Z'));" </dev/null"""
    return wrap("forex_m20_wave1_reconciliation_context", remote(body))


def m20_risk_policy_summary() -> dict:
    """Read the persistent Option B state and append-only resume records only."""
    body = '''docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT json_build_object('pause_reasons',(SELECT to_jsonb(p)->'pause_reasons' FROM forex.demo_risk_policy_state p WHERE policy_version='forex.m20.conservative-risk.v1'),'state',(SELECT row_to_json(s) FROM (SELECT policy_version,account_currency,baseline_balance,expected_balance,peak_adjusted_equity,daily_anchor_equity,daily_anchor_date,weekly_anchor_equity,weekly_anchor_date,pause_reason,pause_until_date,cash_flow_review_approved,created_at_utc,updated_at_utc FROM forex.demo_risk_policy_state WHERE policy_version='forex.m20.conservative-risk.v1') s),'resume_requests',(SELECT COALESCE(json_agg(row_to_json(r) ORDER BY r.requested_at_utc),'[]'::json) FROM (SELECT resume_id,policy_version,previous_pause_reason,requested_at_utc,operator_action FROM forex.demo_risk_policy_resume) r));" </dev/null'''
    return wrap("forex_m20_risk_policy_summary", remote(body))


def m20_multi_timeframe_context_verify() -> dict:
    """Read-only M20.12 schema/audit verification; unavailable until explicitly applied."""
    body = '''docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT 'FOREX_M20_MTF_CONTEXT_VERIFY_OK','exact_m5_h1='||NOT EXISTS(SELECT 1 FROM forex.demo_multi_timeframe_context c WHERE (SELECT count(*) FROM forex.demo_multi_timeframe_context_bar b WHERE b.context_id=c.context_id)<>2),'m1_only='||NOT EXISTS(SELECT 1 FROM forex.demo_multi_timeframe_context c JOIN forex.demo_trade_proposal p ON p.proposal_id=c.proposal_id WHERE c.selected_m1_action<>p.action),'immutable='||(SELECT count(*)=2 FROM pg_trigger WHERE NOT tgisinternal AND tgname IN ('demo_multi_timeframe_context_immutable','demo_multi_timeframe_context_bar_immutable')),'contexts='||(SELECT count(*) FROM forex.demo_multi_timeframe_context);" </dev/null'''
    return wrap("forex_m20_mtf_context_verify", remote(body))


def m20_multi_timeframe_context_summary() -> dict:
    """Return read-only context and linked broker outcome fields for later comparison."""
    body = '''docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT COALESCE(json_agg(row_to_json(x) ORDER BY x.decision_at_utc)::text,'[]') FROM (SELECT p.proposal_id,p.decision_at_utc,p.action,c.rule_version,c.overall_alignment,c.context_disposition,c.reason AS context_reason,COALESCE(json_agg(json_build_object('timeframe',b.timeframe,'closed_at_utc',b.closed_at_utc,'data_age_seconds',b.data_age_seconds,'integrity_status',b.integrity_status,'market_state',b.market_state,'volatility_state',b.volatility_state,'liquidity_state',b.liquidity_state,'alignment',b.alignment,'reason',b.reason) ORDER BY b.timeframe) FILTER (WHERE b.timeframe IS NOT NULL),'[]'::json) AS contexts,l.realized_pnl_account,l.account_currency,o.gross_price_pnl_account,o.commission_account,o.fee_account,o.swap_account,o.estimated_total_cost_account,l.close_reason,l.reconciliation_status,CASE WHEN l.closed_at_utc IS NULL THEN NULL ELSE round(extract(epoch FROM l.closed_at_utc-p.decision_at_utc))::integer END AS holding_seconds,'NOT_RETAINED_IN_M20_12' AS mae_mfe_status FROM forex.demo_trade_proposal p JOIN forex.demo_multi_timeframe_context c ON c.proposal_id=p.proposal_id LEFT JOIN forex.demo_multi_timeframe_context_bar b ON b.context_id=c.context_id LEFT JOIN forex.demo_trade_ledger l ON l.proposal_id=p.proposal_id LEFT JOIN forex.demo_trade_outcome o ON o.proposal_id=p.proposal_id GROUP BY p.proposal_id,p.decision_at_utc,p.action,c.rule_version,c.overall_alignment,c.context_disposition,c.reason,l.realized_pnl_account,l.account_currency,o.gross_price_pnl_account,o.commission_account,o.fee_account,o.swap_account,o.estimated_total_cost_account,l.close_reason,l.reconciliation_status,l.closed_at_utc)x;" </dev/null'''
    return wrap("forex_m20_mtf_context_summary", remote(body))


def m20_audit_verify() -> dict:
    """Read back the fixed M20 audit boundary without exposing table input."""
    audit = remote('''docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT 'FOREX_M20_DEMO_AUDIT_VERIFY_OK','demo_only='||NOT EXISTS(SELECT FROM forex.demo_trade_session WHERE server<>'GOMarketsMU-Demo' OR instrument<>'EURUSD'),'caps_ok='||NOT EXISTS(SELECT FROM forex.demo_trade_session WHERE max_notional_usd>10000 OR max_cumulative_notional_usd>100000 OR max_open_positions<>1),'proposal_first='||NOT EXISTS(SELECT FROM forex.demo_execution_attempt a LEFT JOIN forex.demo_trade_proposal p ON p.proposal_id=a.proposal_id LEFT JOIN forex.demo_decision_snapshot s ON s.proposal_id=p.proposal_id WHERE p.proposal_id IS NULL OR s.proposal_id IS NULL OR p.decision_at_utc>a.submitted_at_utc),'idempotency_ok='||NOT EXISTS(SELECT FROM (SELECT idempotency_key FROM forex.demo_execution_attempt GROUP BY idempotency_key HAVING count(*)>1)x);" </dev/null''')
    immutability = remote('''docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT 'immutable_triggers='||(SELECT count(*)=8 FROM pg_trigger WHERE NOT tgisinternal AND tgname IN ('demo_trade_proposal_immutable','demo_decision_snapshot_immutable','demo_execution_attempt_immutable','demo_position_event_immutable','demo_trade_outcome_immutable','demo_outcome_reconciliation_revision_immutable','demo_strategy_selection_immutable','demo_strategy_signal_immutable')),'selection_rows='||(SELECT count(*) FROM forex.demo_strategy_selection),'signal_rows='||(SELECT count(*) FROM forex.demo_strategy_signal),'legacy_proposals_without_selection='||(SELECT count(*) FROM forex.demo_trade_proposal p LEFT JOIN forex.demo_strategy_selection x ON x.proposal_id=p.proposal_id WHERE x.proposal_id IS NULL),'false_pnl_excluded='||NOT EXISTS(SELECT FROM forex.demo_trade_ledger WHERE reconciliation_status='MATCHED' AND realized_pnl_account=100000.18);" </dev/null''')
    cost = remote('''docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT 'cost_schema=' || (SELECT count(*)=7 FROM information_schema.columns WHERE table_schema='forex' AND table_name='demo_trade_outcome' AND column_name IN ('gross_price_pnl_account','commission_account','fee_account','swap_account','estimated_spread_cost_account','slippage_cost_account','estimated_total_cost_account')) || '|fee_incomplete_excluded=' || NOT EXISTS (SELECT 1 FROM forex.demo_trade_ledger WHERE fee_account IS NULL AND realized_pnl_account IS NOT NULL);" </dev/null''')
    combined = {
        "exit_code": 0 if audit["ok"] and immutability["ok"] and cost["ok"] else 1,
        "stdout": "|".join(item["stdout"].strip() for item in (audit, immutability, cost) if item["stdout"].strip()) + "\n",
        "stderr": audit["stderr"] + immutability["stderr"] + cost["stderr"],
        "ok": audit["ok"] and immutability["ok"] and cost["ok"],
    }
    return wrap("forex_m20_audit_verify", combined)


def m20_rejection_summary() -> dict:
    """Read fixed redacted MT5 rejection retcodes from the M20 audit ledger."""
    body = '''docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT COALESCE(json_agg(row_to_json(x))::text, '[]') FROM (SELECT e.observed_at_utc,p.action,e.payload->>'retcode' AS mt5_retcode,e.payload->>'broker_comment' AS broker_comment,e.payload->>'volume' AS volume,e.payload->>'requested_price' AS requested_price,e.payload->>'stop_loss' AS stop_loss,e.payload->>'take_profit' AS take_profit,e.payload->>'observed_bid' AS observed_bid,e.payload->>'observed_ask' AS observed_ask,e.payload->>'spread_points' AS spread_points,e.payload->>'stops_level_points' AS stops_level_points,e.payload->>'visible_positions_count' AS visible_positions_count,e.payload->>'lease_max_trades' AS lease_max_trades,e.payload->>'reservation_slot_number' AS reservation_slot_number FROM forex.demo_position_event e JOIN forex.demo_execution_attempt a ON a.attempt_id=e.attempt_id JOIN forex.demo_trade_proposal p ON p.proposal_id=a.proposal_id WHERE e.event_type='REJECTED' ORDER BY e.observed_at_utc DESC) x;" </dev/null'''
    return wrap("forex_m20_rejection_summary", remote(body))


def m20_lifecycle_summary() -> dict:
    """Read every fixed M20 attempt's terminal/open lifecycle without secrets."""
    lifecycle = remote('''docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT COALESCE(json_agg(row_to_json(x) ORDER BY x.submitted_at_utc)::text,'[]') FROM (SELECT p.session_id,p.proposal_id,a.attempt_id,p.action,a.status,a.submitted_at_utc,p.proposed_entry,COALESCE((SELECT e.payload->>'actual_entry_price' FROM forex.demo_position_event e WHERE e.attempt_id=a.attempt_id AND e.event_type='OPENED' LIMIT 1),'') actual_entry_price,p.stop_loss,p.take_profit,COALESCE((SELECT e.payload->>'volume' FROM forex.demo_position_event e WHERE e.attempt_id=a.attempt_id AND e.event_type='OPENED' LIMIT 1),'') volume_lots,l.closed_at_utc,l.exit_price,l.realized_pnl_account,l.account_currency,l.close_reason,l.reconciliation_status,l.reconciliation_disposition,l.reconciliation_reason,p.strategy_version,o.commission_account,o.fee_account,o.swap_account,o.estimated_total_cost_account,COALESCE((SELECT json_agg(e.event_type ORDER BY e.observed_at_utc)::text FROM forex.demo_position_event e WHERE e.attempt_id=a.attempt_id),'[]') events,COALESCE((SELECT e.payload FROM forex.demo_position_event e WHERE e.attempt_id=a.attempt_id AND e.event_type='REJECTED' ORDER BY e.observed_at_utc DESC LIMIT 1),'{}'::jsonb) rejection_context,CASE WHEN l.reconciliation_status IN ('MATCHED','REPAIRED') THEN 'CLOSED_MATCHED' WHEN l.reconciliation_status='RECONCILIATION_ERROR' THEN 'CLOSED_RECONCILIATION_ERROR' WHEN s.attempt_id IS NOT NULL THEN 'OPEN_MONITORING' WHEN EXISTS(SELECT FROM forex.demo_position_event e WHERE e.attempt_id=a.attempt_id AND e.event_type='NOT_SUBMITTED') THEN 'TERMINAL_NOT_SUBMITTED' WHEN EXISTS(SELECT FROM forex.demo_position_event e WHERE e.attempt_id=a.attempt_id AND e.event_type='REJECTED') THEN 'TERMINAL_REJECTED' WHEN EXISTS(SELECT FROM forex.demo_position_event e WHERE e.attempt_id=a.attempt_id AND e.event_type='FAILED') THEN 'TERMINAL_FAILED' ELSE 'PENDING' END lifecycle FROM forex.demo_execution_attempt a JOIN forex.demo_trade_proposal p ON p.proposal_id=a.proposal_id LEFT JOIN forex.demo_trade_ledger l ON l.proposal_id=a.proposal_id LEFT JOIN forex.demo_trade_outcome o ON o.proposal_id=a.proposal_id LEFT JOIN forex.demo_open_position_state s ON s.attempt_id=a.attempt_id) x;" </dev/null''')
    selections = remote('''docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT COALESCE(json_agg(row_to_json(x))::text,'[]') FROM (SELECT proposal_id,market_regime,selected_strategy_id,strategy_rule_version,trade_owner_id,trade_owner_strategy_id,estimated_round_trip_cost_aud,minimum_net_profit_aud,expected_net_profit_at_take_profit_aud,cost_coverage_status FROM forex.demo_strategy_selection)x;" </dev/null''')
    costs = remote('''docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT COALESCE(json_agg(row_to_json(x))::text,'[]') FROM (SELECT proposal_id,gross_price_pnl_account,estimated_spread_cost_account,slippage_cost_account FROM forex.demo_trade_outcome)x;" </dev/null''')
    if not lifecycle["ok"] or not selections["ok"] or not costs["ok"]:
        return wrap("forex_m20_lifecycle_summary", {"exit_code": 1, "stdout": "", "stderr": lifecycle["stderr"] + selections["stderr"] + costs["stderr"], "ok": False})
    try:
        rows = json.loads(lifecycle["stdout"])
        selection_by_proposal = {item["proposal_id"]: item for item in json.loads(selections["stdout"])}
        costs_by_proposal = {item["proposal_id"]: item for item in json.loads(costs["stdout"])}
        for row in rows:
            row.update(selection_by_proposal.get(row["proposal_id"], {}))
            row.update(costs_by_proposal.get(row["proposal_id"], {}))
    except (KeyError, TypeError, json.JSONDecodeError):
        return wrap("forex_m20_lifecycle_summary", {"exit_code": 1, "stdout": "", "stderr": "M20 lifecycle summary returned invalid JSON", "ok": False})
    return wrap("forex_m20_lifecycle_summary", {"exit_code": 0, "stdout": json.dumps(rows, separators=(",", ":")), "stderr": lifecycle["stderr"] + selections["stderr"] + costs["stderr"], "ok": True})


def m20_current_lineage_summary() -> dict:
    """Read the fixed 10 September lineage and its database balance bridge.

    This bounded query stays below the Windows command-line limit after the
    governed PowerShell, SSH, and WSL encoding layers. Broker-deal attribution
    remains a separate MT5 evidence surface; this operation never infers it.
    """
    body = '''docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "WITH l AS (SELECT p.session_id,t.starts_at_utc,t.expires_at_utc,p.proposal_id,p.decision_at_utc,p.action,s.snapshot_id,a.attempt_id,a.submitted_at_utc,a.status,COALESCE((SELECT json_agg(json_build_object('event_type',e.event_type,'position_ticket',e.payload->>'position_ticket') ORDER BY e.observed_at_utc) FROM forex.demo_position_event e WHERE e.attempt_id=a.attempt_id),'[]'::json) events,row_to_json(o) outcome FROM forex.demo_trade_proposal p JOIN forex.demo_trade_session t ON t.session_id=p.session_id JOIN forex.demo_decision_snapshot s ON s.proposal_id=p.proposal_id LEFT JOIN forex.demo_execution_attempt a ON a.proposal_id=p.proposal_id LEFT JOIN forex.demo_trade_outcome o ON o.proposal_id=p.proposal_id WHERE p.decision_at_utc>='2026-09-10T06:00:00Z' AND p.decision_at_utc<'2026-09-11T00:00:00Z' AND (p.action<>'NO_TRADE' OR a.attempt_id IS NOT NULL)) SELECT json_build_object('window',json_build_object('from_utc','2026-09-10T06:00:00Z','to_utc','2026-09-11T00:00:00Z'),'lineage',COALESCE((SELECT json_agg(row_to_json(l) ORDER BY l.decision_at_utc) FROM l),'[]'::json),'balance_bridge',json_build_object('baseline_balance',(SELECT baseline_balance FROM forex.demo_risk_policy_state WHERE policy_version='forex.m20.conservative-risk.v1'),'expected_balance',(SELECT expected_balance FROM forex.demo_risk_policy_state WHERE policy_version='forex.m20.conservative-risk.v1'),'accounted_realized_pnl_since_window',COALESCE((SELECT sum(o.realized_pnl_account) FROM forex.demo_trade_outcome o JOIN forex.demo_trade_proposal p ON p.proposal_id=o.proposal_id WHERE p.decision_at_utc>='2026-09-10T06:00:00Z' AND p.decision_at_utc<'2026-09-11T00:00:00Z'),0)));" </dev/null'''
    return wrap("forex_m20_current_lineage_summary", remote(body))


def m20_unresolved_attempt_summary() -> dict:
    """Read only the exact attempts that keep the global entry gate closed."""
    body = '''docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT COALESCE(json_agg(row_to_json(x) ORDER BY x.submitted_at_utc)::text,'[]') FROM (SELECT a.attempt_id,p.proposal_id,p.session_id,p.action,a.status,a.submitted_at_utc,a.broker_order_reference,COALESCE((SELECT e.payload->>'position_ticket' FROM forex.demo_position_event e WHERE e.attempt_id=a.attempt_id AND e.event_type='OPENED' ORDER BY e.observed_at_utc LIMIT 1),'') position_ticket,COALESCE((SELECT e.payload->>'position_identifier' FROM forex.demo_position_event e WHERE e.attempt_id=a.attempt_id AND e.event_type='OPENED' ORDER BY e.observed_at_utc LIMIT 1),'') position_identifier,COALESCE((SELECT json_agg(e.event_type ORDER BY e.observed_at_utc)::text FROM forex.demo_position_event e WHERE e.attempt_id=a.attempt_id),'[]') events FROM forex.demo_execution_attempt a JOIN forex.demo_trade_proposal p ON p.proposal_id=a.proposal_id LEFT JOIN forex.demo_trade_outcome o ON o.proposal_id=a.proposal_id WHERE o.proposal_id IS NULL AND NOT EXISTS (SELECT FROM forex.demo_position_event e WHERE e.attempt_id=a.attempt_id AND e.event_type IN ('REJECTED','NOT_SUBMITTED'))) x;" </dev/null'''
    return wrap("forex_m20_unresolved_attempt_summary", remote(body))


def stage_m20_strategy_trial_query() -> dict:
    """Stage the fixed read-only scoreboard query on the T480 without touching data."""
    relative, digest = asset("m20_strategy_trial_query")
    source_windows = subprocess.run(["wslpath", "-w", str(ROOT / relative)], text=True, capture_output=True, check=True).stdout.strip()
    staging_directory = r"C:\Users\chris\Documents\Code\forex-m1-probe"
    staging_windows = staging_directory + r"\m20_strategy_trial_summary.sql"
    quote = lambda value: "'" + value.replace("'", "''") + "'"
    mkdir = subprocess.run(build_ssh_command(TARGET, "$ErrorActionPreference='Stop'; New-Item -ItemType Directory -Force -Path " + quote(staging_directory) + " | Out-Null", SETTINGS), text=True, capture_output=True, check=False)
    if mkdir.returncode:
        return wrap("forex_m20_stage_strategy_trial_query", {"exit_code": mkdir.returncode, "stdout": mkdir.stdout, "stderr": mkdir.stderr, "ok": False}, digest)
    command = "$ErrorActionPreference='Stop'; & scp.exe -B -o BatchMode=yes -o StrictHostKeyChecking=yes -- " + quote(source_windows) + " " + quote(TARGET + ':' + staging_windows) + "; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }"
    encoded = base64.b64encode(command.encode("utf-16-le")).decode("ascii")
    transfer = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded], text=True, capture_output=True, check=False)
    if transfer.returncode:
        return wrap("forex_m20_stage_strategy_trial_query", {"exit_code": transfer.returncode, "stdout": transfer.stdout, "stderr": transfer.stderr, "ok": False}, digest)
    body = f'''source="/mnt/c/Users/chris/Documents/Code/forex-m1-probe/m20_strategy_trial_summary.sql"
file="{REMOTE_FOREX}/{relative}"
test -f "$source" && [[ "$(sha256sum "$source" | head -c 64)" == "{digest}" ]]
mkdir -p "$(dirname "$file")"
install -m 0644 "$source" "$file"
[[ "$(sha256sum "$file" | head -c 64)" == "{digest}" ]]
printf 'FOREX_M20_STRATEGY_TRIAL_QUERY_STAGED sha256:{digest}\\n' '''
    return wrap("forex_m20_stage_strategy_trial_query", remote(body), digest)


def m20_strategy_trial_summary() -> dict:
    """Return a fixed, read-only M20.11 summary for every strategy owner."""
    relative, digest = asset("m20_strategy_trial_query")
    # Aggregate each append-only source once. The former five-way joined query
    # multiplied rows as assessments accumulated and could exceed the terminal
    # dashboard's bounded read timeout.
    query = """
    WITH trial_proposals AS (
      SELECT proposal_id FROM forex.demo_trade_proposal
      WHERE strategy_version='forex.m20.11.m1-five-strategy-trial.v2'
    ), signal_stats AS (
      SELECT g.strategy_id, count(*) FILTER (WHERE g.signal IN ('BUY','SELL')) AS signal_count
      FROM forex.demo_strategy_signal g JOIN trial_proposals p USING (proposal_id)
      GROUP BY g.strategy_id
    ), selection_stats AS (
      SELECT s.selected_strategy_id AS strategy_id,
             count(*) FILTER (WHERE s.selection_status='SELECTED_EXECUTABLE') AS selected_count
      FROM forex.demo_strategy_selection s JOIN trial_proposals p USING (proposal_id)
      WHERE s.selected_strategy_id IS NOT NULL GROUP BY s.selected_strategy_id
    ), attempt_events AS (
      SELECT e.attempt_id, bool_or(e.event_type='OPENED') AS opened, bool_or(e.event_type='REJECTED') AS rejected
      FROM forex.demo_position_event e GROUP BY e.attempt_id
    ), attempt_stats AS (
      SELECT s.selected_strategy_id AS strategy_id, count(DISTINCT a.attempt_id) AS attempt_count,
             count(DISTINCT a.attempt_id) FILTER (WHERE ev.opened) AS opened_count,
             count(DISTINCT a.attempt_id) FILTER (WHERE ev.rejected) AS rejected_count
      FROM forex.demo_strategy_selection s JOIN trial_proposals p USING (proposal_id)
      LEFT JOIN forex.demo_execution_attempt a USING (proposal_id)
      LEFT JOIN attempt_events ev USING (attempt_id)
      WHERE s.selected_strategy_id IS NOT NULL GROUP BY s.selected_strategy_id
    ), outcome_stats AS (
      SELECT l.trade_owner_strategy_id AS strategy_id,
             count(*) FILTER (WHERE l.reconciliation_status IN ('MATCHED','REPAIRED') AND l.realized_pnl_account IS NOT NULL) AS verified_closed_count,
             count(*) FILTER (WHERE l.realized_pnl_account > 0) AS win_count,
             count(*) FILTER (WHERE l.realized_pnl_account < 0) AS loss_count,
             COALESCE(sum(l.realized_pnl_account) FILTER (WHERE l.reconciliation_status IN ('MATCHED','REPAIRED')),0) AS net_realized_pnl_aud
      FROM forex.demo_trade_ledger l JOIN trial_proposals p USING (proposal_id)
      WHERE l.trade_owner_strategy_id IS NOT NULL GROUP BY l.trade_owner_strategy_id
    ), strategy_ids AS (
      SELECT strategy_id FROM signal_stats UNION SELECT strategy_id FROM selection_stats
      UNION SELECT strategy_id FROM attempt_stats UNION SELECT strategy_id FROM outcome_stats
    )
    SELECT COALESCE(json_agg(row_to_json(x) ORDER BY x.strategy_id)::text,'[]')
    FROM (SELECT ids.strategy_id, COALESCE(si.signal_count,0) signal_count,
      COALESCE(se.selected_count,0) selected_count, COALESCE(at.attempt_count,0) attempt_count,
      COALESCE(at.opened_count,0) opened_count, COALESCE(at.rejected_count,0) rejected_count,
      COALESCE(ou.verified_closed_count,0) verified_closed_count, COALESCE(ou.win_count,0) win_count,
      COALESCE(ou.loss_count,0) loss_count, COALESCE(ou.net_realized_pnl_aud,0) net_realized_pnl_aud
      FROM strategy_ids ids LEFT JOIN signal_stats si USING(strategy_id)
      LEFT JOIN selection_stats se USING(strategy_id) LEFT JOIN attempt_stats at USING(strategy_id)
      LEFT JOIN outcome_stats ou USING(strategy_id)) x;
    """
    body = f'''file="{REMOTE_FOREX}/{relative}"
test -f "$file" && [[ "$(sha256sum "$file" | head -c 64)" == "{digest}" ]]
docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At < "$file"'''
    return wrap("forex_m20_strategy_trial_summary", remote(body), digest)


# Backward-compatible action alias retained for the fixed command catalog.
m11_r1_verify_hour = verify_m11_data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fixed Forex M2 PostgreSQL adapter.")
    parser.add_argument("command", choices=sorted(READ_ONLY | MUTATING))
    parser.add_argument("--approve", action="store_true")
    args = parser.parse_args(argv)
    if args.command in MUTATING and not args.approve:
        parser.error("this mutating operation requires --approve")
    actions = {"preflight": preflight, "inspect": inspect, "vector-probe": vector_probe, "forex-m2-apply-schema": apply_schema, "forex-m2-import": import_snapshot, "forex-m2-verify": verify_snapshot, "forex-m2-provenance-negative-control": provenance_negative_control, "forex-m11-apply-schema": apply_m11_schema, "forex-m11-r1-apply-stage-schema": apply_m11_r1_stage_schema, "forex-m11-verify-schema": verify_m11_schema, "forex-m11-verify-data": verify_m11_data, "forex-m11-r1-verify-hour": m11_r1_verify_hour, "forex-m12-quality-probe": m12_quality_probe, "forex-m13-replay-probe": m13_replay_probe, "forex-m14-regime-probe": m14_regime_probe, "forex-m15-baseline-probe": m15_baseline_probe, "forex-m16-walk-forward-probe": m16_walk_forward_probe, "forex-m17-context-probe": m17_context_probe, "forex-m18-ollama-probe": m18_ollama_probe, "forex-m19-apply-schema": apply_m19_schema, "forex-m19-lineage-probe": m19_lineage_probe, "forex-m19-lineage-verify": m19_lineage_verify, "forex-m20-stage-schema": stage_m20_schema, "forex-m20-apply-schema": apply_m20_schema, "forex-m20-stage-ledger-schema": stage_m20_ledger_schema, "forex-m20-apply-ledger-schema": apply_m20_ledger_schema, "forex-m20-stage-cost-ledger-schema": stage_m20_cost_ledger_schema, "forex-m20-apply-cost-ledger-schema": apply_m20_cost_ledger_schema, "forex-m20-stage-open-position-schema": stage_m20_open_position_schema, "forex-m20-apply-open-position-schema": apply_m20_open_position_schema, "forex-m20-stage-continuous-lease-schema": stage_m20_continuous_lease_schema, "forex-m20-apply-continuous-lease-schema": apply_m20_continuous_lease_schema, "forex-m20-stage-outcome-reconciliation-schema": stage_m20_outcome_reconciliation_schema, "forex-m20-apply-outcome-reconciliation-schema": apply_m20_outcome_reconciliation_schema, "forex-m20-stage-regime-strategy-schema": stage_m20_regime_strategy_schema, "forex-m20-apply-regime-strategy-schema": apply_m20_regime_strategy_schema, "forex-m20-stage-projected-cost-schema": stage_m20_projected_cost_schema, "forex-m20-apply-projected-cost-schema": apply_m20_projected_cost_schema, "forex-m20-stage-mtf-context-schema": stage_m20_multi_timeframe_context_schema, "forex-m20-apply-mtf-context-schema": apply_m20_multi_timeframe_context_schema, "forex-m20-stage-strategy-trial-query": stage_m20_strategy_trial_query, "forex-m20-audit-verify": m20_audit_verify, "forex-m20-mtf-context-verify": m20_multi_timeframe_context_verify, "forex-m20-mtf-context-summary": m20_multi_timeframe_context_summary}
    actions["forex-m20-rejection-summary"] = m20_rejection_summary
    actions["forex-m20-unresolved-attempt-summary"] = m20_unresolved_attempt_summary
    actions["forex-m20-stage-remove-trade-count-cap-schema"] = stage_m20_remove_trade_count_cap_schema
    actions["forex-m20-apply-remove-trade-count-cap-schema"] = apply_m20_remove_trade_count_cap_schema
    actions["forex-m20-stage-unresolved-execution-schema"] = stage_m20_unresolved_execution_schema
    actions["forex-m20-apply-unresolved-execution-schema"] = apply_m20_unresolved_execution_schema
    actions["forex-m20-stage-broker-fee-ledger-schema"] = stage_m20_broker_fee_ledger_schema
    actions["forex-m20-apply-broker-fee-ledger-schema"] = apply_m20_broker_fee_ledger_schema
    actions["forex-m20-stage-persistent-risk-policy-schema"] = stage_m20_persistent_risk_policy_schema
    actions["forex-m20-apply-persistent-risk-policy-schema"] = apply_m20_persistent_risk_policy_schema
    actions["forex-m20-stage-risk-resume-audit-schema"] = stage_m20_risk_resume_audit_schema
    actions["forex-m20-apply-risk-resume-audit-schema"] = apply_m20_risk_resume_audit_schema
    actions["forex-m20-stage-wave1-gap-reconciliation"] = stage_m20_wave1_gap_reconciliation
    actions["forex-m20-apply-wave1-gap-reconciliation"] = apply_m20_wave1_gap_reconciliation
    actions["forex-m20-stage-listener-release"] = stage_m20_listener_release
    actions["forex-m20-stage-independent-risk-pauses-schema"] = stage_m20_independent_risk_pauses_schema
    actions["forex-m20-apply-independent-risk-pauses-schema"] = apply_m20_independent_risk_pauses_schema
    actions["forex-m20-stage-not-submitted-execution-schema"] = stage_m20_not_submitted_execution_schema
    actions["forex-m20-apply-not-submitted-execution-schema"] = apply_m20_not_submitted_execution_schema
    actions["forex-m20-wave1-reconciliation-context"] = m20_wave1_reconciliation_context
    actions["forex-m20-risk-policy-summary"] = m20_risk_policy_summary
    actions["forex-m20-current-lineage-summary"] = m20_current_lineage_summary
    actions["forex-m20-stage-fee-complete-reconciliation-ledger-schema"] = stage_m20_fee_complete_reconciliation_ledger_schema
    actions["forex-m20-apply-fee-complete-reconciliation-ledger-schema"] = apply_m20_fee_complete_reconciliation_ledger_schema
    actions["forex-m20-lifecycle-summary"] = m20_lifecycle_summary
    actions["forex-m20-strategy-trial-summary"] = m20_strategy_trial_summary
    payload = actions[args.command]()
    print(json.dumps(payload, indent=2))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
