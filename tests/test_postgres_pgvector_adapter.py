from unittest import mock

from scripts import postgres_pgvector_adapter


def test_adapter_exposes_only_fixed_forex_operations():
    expected = {
        "preflight", "inspect", "vector-probe",
        "forex-m2-apply-schema", "forex-m2-import", "forex-m2-verify", "forex-m2-provenance-negative-control",
        "forex-m11-apply-schema", "forex-m11-r1-apply-stage-schema", "forex-m11-verify-schema", "forex-m11-verify-data", "forex-m11-r1-verify-hour",
        "forex-m12-quality-probe", "forex-m13-replay-probe", "forex-m14-regime-probe", "forex-m15-baseline-probe", "forex-m16-walk-forward-probe", "forex-m17-context-probe", "forex-m18-ollama-probe", "forex-m19-apply-schema", "forex-m19-lineage-probe", "forex-m19-lineage-verify", "forex-m20-stage-schema", "forex-m20-apply-schema", "forex-m20-stage-ledger-schema", "forex-m20-apply-ledger-schema", "forex-m20-stage-cost-ledger-schema", "forex-m20-apply-cost-ledger-schema", "forex-m20-stage-open-position-schema", "forex-m20-apply-open-position-schema", "forex-m20-stage-continuous-lease-schema", "forex-m20-apply-continuous-lease-schema", "forex-m20-stage-outcome-reconciliation-schema", "forex-m20-apply-outcome-reconciliation-schema", "forex-m20-stage-regime-strategy-schema", "forex-m20-apply-regime-strategy-schema", "forex-m20-audit-verify", "forex-m20-rejection-summary", "forex-m20-lifecycle-summary", "forex-m20-unresolved-attempt-summary",
    }
    expected.update({
        "forex-m20-stage-projected-cost-schema", "forex-m20-apply-projected-cost-schema",
        "forex-m20-strategy-trial-summary", "forex-m20-stage-mtf-context-schema",
        "forex-m20-apply-mtf-context-schema", "forex-m20-mtf-context-verify",
        "forex-m20-mtf-context-summary", "forex-m20-stage-strategy-trial-query",
        "forex-m20-stage-remove-trade-count-cap-schema",
        "forex-m20-apply-remove-trade-count-cap-schema",
        "forex-m20-stage-unresolved-execution-schema",
        "forex-m20-apply-unresolved-execution-schema",
        "forex-m20-stage-broker-fee-ledger-schema",
        "forex-m20-apply-broker-fee-ledger-schema",
        "forex-m20-stage-persistent-risk-policy-schema",
        "forex-m20-apply-persistent-risk-policy-schema",
        "forex-m20-stage-risk-resume-audit-schema",
        "forex-m20-apply-risk-resume-audit-schema",
        "forex-m20-stage-fee-complete-reconciliation-ledger-schema",
        "forex-m20-apply-fee-complete-reconciliation-ledger-schema",
        "forex-m20-risk-policy-summary",
    })
    assert postgres_pgvector_adapter.READ_ONLY | postgres_pgvector_adapter.MUTATING == expected


def test_m20_unresolved_execution_schema_staging_and_application_are_hash_bound():
    migration = "sql/migrations/017_m20_unresolved_execution_state.sql"
    transfer = mock.Mock(returncode=0, stdout="", stderr="")
    conversion = mock.Mock(stdout=r"\\wsl.localhost\Ubuntu\home\chris\projects\forex\sql\migrations\017_m20_unresolved_execution_state.sql\n")
    with mock.patch.object(postgres_pgvector_adapter, "asset", return_value=(migration, "a" * 64)), mock.patch.object(postgres_pgvector_adapter, "subprocess") as process, mock.patch.object(postgres_pgvector_adapter, "remote", return_value={"ok": True}) as remote:
        process.run.side_effect = [conversion, transfer]
        assert postgres_pgvector_adapter.stage_m20_unresolved_execution_schema()["ok"]
    staged = remote.call_args.args[0]
    assert "017_m20_unresolved_execution_state.sql" in staged
    assert "sha256sum" in staged and "install -m 0644" in staged
    with mock.patch.object(postgres_pgvector_adapter, "asset", return_value=(migration, "a" * 64)), mock.patch.object(postgres_pgvector_adapter, "remote", return_value={"ok": True}) as remote:
        assert postgres_pgvector_adapter.apply_m20_unresolved_execution_schema()["ok"]
    assert "sha256sum" in remote.call_args.args[0]


def test_m20_risk_resume_audit_schema_is_hash_bound_and_risk_state_is_read_only_summary():
    migration = "sql/migrations/020_m20_risk_resume_audit.sql"
    transfer = mock.Mock(returncode=0, stdout="", stderr="")
    conversion = mock.Mock(stdout=r"\\wsl.localhost\Ubuntu\home\chris\projects\forex\sql\migrations\020_m20_risk_resume_audit.sql\n")
    with mock.patch.object(postgres_pgvector_adapter, "asset", return_value=(migration, "a" * 64)), mock.patch.object(postgres_pgvector_adapter, "subprocess") as process, mock.patch.object(postgres_pgvector_adapter, "remote", return_value={"ok": True}) as remote:
        process.run.side_effect = [conversion, transfer]
        assert postgres_pgvector_adapter.stage_m20_risk_resume_audit_schema()["ok"]
    assert "020_m20_risk_resume_audit.sql" in remote.call_args.args[0]
    with mock.patch.object(postgres_pgvector_adapter, "asset", return_value=(migration, "a" * 64)), mock.patch.object(postgres_pgvector_adapter, "remote", return_value={"ok": True}) as remote:
        assert postgres_pgvector_adapter.apply_m20_risk_resume_audit_schema()["ok"]
    assert "sha256sum" in remote.call_args.args[0]
    with mock.patch.object(postgres_pgvector_adapter, "remote", return_value={"ok": True}) as remote:
        assert postgres_pgvector_adapter.m20_risk_policy_summary()["ok"]
    assert "demo_risk_policy_state" in remote.call_args.args[0]
    assert "demo_risk_policy_resume" in remote.call_args.args[0]


def test_m20_fee_complete_reconciliation_ledger_is_hash_bound_and_excludes_fee_less_pnl():
    migration = "sql/migrations/021_m20_fee_complete_reconciliation_ledger.sql"
    transfer = mock.Mock(returncode=0, stdout="", stderr="")
    conversion = mock.Mock(stdout=r"\\wsl.localhost\Ubuntu\home\chris\projects\forex\sql\migrations\021_m20_fee_complete_reconciliation_ledger.sql\n")
    with mock.patch.object(postgres_pgvector_adapter, "asset", return_value=(migration, "a" * 64)), mock.patch.object(postgres_pgvector_adapter, "subprocess") as process, mock.patch.object(postgres_pgvector_adapter, "remote", return_value={"ok": True}) as remote:
        process.run.side_effect = [conversion, transfer]
        assert postgres_pgvector_adapter.stage_m20_fee_complete_reconciliation_ledger_schema()["ok"]
    assert "021_m20_fee_complete_reconciliation_ledger.sql" in remote.call_args.args[0]
    with mock.patch.object(postgres_pgvector_adapter, "asset", return_value=(migration, "a" * 64)), mock.patch.object(postgres_pgvector_adapter, "remote", return_value={"ok": True}) as remote:
        assert postgres_pgvector_adapter.apply_m20_fee_complete_reconciliation_ledger_schema()["ok"]
    assert "sha256sum" in remote.call_args.args[0]
    with mock.patch.object(postgres_pgvector_adapter, "remote", return_value={"ok": True, "stdout": "", "stderr": ""}) as remote:
        assert postgres_pgvector_adapter.m20_audit_verify()["ok"]
    assert "fee_incomplete_excluded=" in "\n".join(call.args[0] for call in remote.call_args_list)


def test_schema_application_is_hash_bound_and_rerunnable():
    with mock.patch.object(postgres_pgvector_adapter, "asset", side_effect=[("sql/migrations/001_m2_historical_data.sql", "a" * 64), ("sql/migrations/002_m2_sealed_provenance.sql", "b" * 64)]), mock.patch.object(postgres_pgvector_adapter, "remote", return_value={"ok": True}) as remote:
        assert postgres_pgvector_adapter.apply_schema()["ok"]
    assert "sha256sum" in remote.call_args.args[0]
    assert "FOREX_M2_SCHEMA_ALREADY_APPLIED" in remote.call_args.args[0]


def test_import_is_hash_bound():
    with mock.patch.object(postgres_pgvector_adapter, "asset", return_value=("scripts/build_m2_postgres_import.py", "b" * 64)), mock.patch.object(postgres_pgvector_adapter, "remote", return_value={"ok": True}) as remote:
        assert postgres_pgvector_adapter.import_snapshot()["ok"]
    assert "sha256sum" in remote.call_args.args[0]
    assert "FOREX_M2_IMPORT_ALREADY_PRESENT" in remote.call_args.args[0]


def test_m11_schema_application_is_hash_bound():
    with mock.patch.object(postgres_pgvector_adapter, "asset", return_value=("sql/migrations/003_m11_gdelt_h1_aggregate.sql", "c" * 64)), mock.patch.object(postgres_pgvector_adapter, "remote", return_value={"ok": True}) as remote:
        assert postgres_pgvector_adapter.apply_m11_schema()["ok"]
    query = "\n".join(call.args[0] for call in remote.call_args_list)
    assert "sha256sum" in query
    assert "FOREX_M11_GDELT_SCHEMA_APPLIED" in query


def test_m11_schema_verification_names_only_the_expected_table_and_index():
    with mock.patch.object(postgres_pgvector_adapter, "remote", return_value={"ok": True}) as remote:
        assert postgres_pgvector_adapter.verify_m11_schema()["ok"]
    query = remote.call_args.args[0]
    assert "gdelt_h1_aggregate" in query
    assert "gdelt_h1_aggregate_alignment_idx" in query


def test_verification_query_checks_m2_lineage_and_point_in_time_controls():
    with mock.patch.object(postgres_pgvector_adapter, "remote", return_value={"ok": True}) as remote:
        assert postgres_pgvector_adapter.verify_snapshot()["ok"]
    query = remote.call_args.args[0]
    for required in ("source_status", "snapshot=", "lineage_ok", "bar_availability_ok", "price_bar_point_in_time", "snapshot_observation_point_in_time", "sealed_provenance_triggers"):
        assert required in query


def test_provenance_negative_control_attempts_both_sealed_mutations():
    with mock.patch.object(postgres_pgvector_adapter, "remote", return_value={"ok": True}) as remote:
        assert postgres_pgvector_adapter.provenance_negative_control()["ok"]
    query = remote.call_args.args[0]
    assert "UPDATE forex.raw_observation" in query
    assert "UPDATE forex.source_registry" not in query
    assert "FOREX_M2_SEALED_RAW_OBSERVATION_NEGATIVE_CONTROL_OK" in query


def test_m20_audit_schema_application_is_hash_bound_and_verification_is_fixed():
    transfer = mock.Mock(returncode=0, stdout="", stderr="")
    conversion = mock.Mock(stdout=r"\\wsl.localhost\Ubuntu\home\chris\projects\forex\sql\migrations\006_m20_demo_trading_audit.sql\n")
    with mock.patch.object(postgres_pgvector_adapter, "asset", return_value=("sql/migrations/006_m20_demo_trading_audit.sql", "d" * 64)), mock.patch.object(postgres_pgvector_adapter, "subprocess") as process, mock.patch.object(postgres_pgvector_adapter, "remote", return_value={"ok": True}) as remote:
        process.run.side_effect = [conversion, mock.Mock(returncode=0, stdout="", stderr=""), transfer]
        assert postgres_pgvector_adapter.stage_m20_schema()["ok"]
    assert "install -m 0644" in remote.call_args.args[0]
    assert "FOREX_M20_DEMO_AUDIT_SCHEMA_STAGED" in remote.call_args.args[0]
    with mock.patch.object(postgres_pgvector_adapter, "asset", return_value=("sql/migrations/006_m20_demo_trading_audit.sql", "d" * 64)), mock.patch.object(postgres_pgvector_adapter, "remote", return_value={"ok": True}) as remote:
        assert postgres_pgvector_adapter.apply_m20_schema()["ok"]
    assert "sha256sum" in remote.call_args.args[0]
    assert "FOREX_M20_DEMO_AUDIT_SCHEMA_APPLIED" in remote.call_args.args[0]
    with mock.patch.object(postgres_pgvector_adapter, "remote", return_value={"ok": True, "stdout": "", "stderr": ""}) as remote:
        assert postgres_pgvector_adapter.m20_audit_verify()["ok"]
    query = "\n".join(call.args[0] for call in remote.call_args_list)
    for required in ("demo_trade_session", "demo_execution_attempt", "demo_only=", "caps_ok=", "proposal_first=", "idempotency_ok=", "immutable_triggers="):
        assert required in query


def test_m20_rejection_summary_is_read_only_and_returns_only_audited_fields():
    with mock.patch.object(postgres_pgvector_adapter, "remote", return_value={"ok": True}) as remote:
        assert postgres_pgvector_adapter.m20_rejection_summary()["ok"]
    query = remote.call_args.args[0]
    assert "demo_position_event" in query
    assert "event_type='REJECTED'" in query
    assert "retcode" in query
    assert "broker_comment" in query and "stops_level_points" in query
    assert "password" not in query.lower()


def test_m20_lifecycle_summary_is_fixed_read_only_and_marks_open_or_terminal_state():
    with mock.patch.object(postgres_pgvector_adapter, "remote", return_value={"ok": True, "stdout": "[]", "stderr": ""}) as remote:
        assert postgres_pgvector_adapter.m20_lifecycle_summary()["ok"]
    query = "\n".join(call.args[0] for call in remote.call_args_list)
    for required in ("demo_execution_attempt", "demo_position_event", "demo_trade_ledger", "demo_open_position_state", "session_id", "actual_entry_price", "CLOSED_MATCHED", "CLOSED_RECONCILIATION_ERROR", "TERMINAL_REJECTED", "PENDING"):
        assert required in query
    assert "password" not in query.lower()


def test_m20_unresolved_attempt_summary_is_fixed_and_excludes_rejected_attempts():
    with mock.patch.object(postgres_pgvector_adapter, "remote", return_value={"ok": True}) as remote:
        assert postgres_pgvector_adapter.m20_unresolved_attempt_summary()["ok"]
    query = remote.call_args.args[0]
    for required in ("demo_execution_attempt", "demo_trade_outcome", "demo_position_event", "position_identifier", "event_type='REJECTED'"):
        assert required in query
    assert "password" not in query.lower()


def test_m20_strategy_trial_summary_is_fixed_read_only_and_covers_all_five_owners():
    with mock.patch.object(postgres_pgvector_adapter, "remote", return_value={"ok": True, "stdout": "[]", "stderr": ""}) as remote:
        assert postgres_pgvector_adapter.m20_strategy_trial_summary()["ok"]
    query = remote.call_args.args[0]
    source = (postgres_pgvector_adapter.ROOT / "sql/m20_strategy_trial_summary.sql").read_text()
    for required in ("signal_count", "selected_count", "attempt_count", "verified_closed_count", "net_realized_pnl_aud"):
        assert required in source
    assert "demo_strategy_signal" in source and "demo_strategy_selection" in source
    assert "forex.m20.11.m1-five-strategy-trial.v2" in source
    assert "m20_strategy_trial_summary.sql" in query
    assert "INSERT" not in query and "password" not in query.lower()


def test_m20_outcome_reconciliation_schema_staging_and_application_are_hash_bound():
    migration = "sql/migrations/012_m20_outcome_reconciliation_revision.sql"
    transfer = mock.Mock(returncode=0, stdout="", stderr="")
    conversion = mock.Mock(stdout=r"\\wsl.localhost\Ubuntu\home\chris\projects\forex\sql\migrations\012_m20_outcome_reconciliation_revision.sql\n")
    with mock.patch.object(postgres_pgvector_adapter, "asset", return_value=(migration, "f" * 64)), mock.patch.object(postgres_pgvector_adapter, "subprocess") as process, mock.patch.object(postgres_pgvector_adapter, "remote", return_value={"ok": True}) as remote:
        process.run.side_effect = [conversion, mock.Mock(returncode=0, stdout="", stderr=""), transfer]
        assert postgres_pgvector_adapter.stage_m20_outcome_reconciliation_schema()["ok"]
    assert "sha256sum" in remote.call_args.args[0]
    assert "FOREX_M20_OUTCOME_RECONCILIATION_SCHEMA_STAGED" in remote.call_args.args[0]
    with mock.patch.object(postgres_pgvector_adapter, "asset", return_value=(migration, "f" * 64)), mock.patch.object(postgres_pgvector_adapter, "remote", return_value={"ok": True}) as remote:
        assert postgres_pgvector_adapter.apply_m20_outcome_reconciliation_schema()["ok"]
    assert "sha256sum" in remote.call_args.args[0]
    assert "FOREX_M20_OUTCOME_RECONCILIATION_SCHEMA_APPLIED" in remote.call_args.args[0]


def test_m20_open_position_schema_staging_and_application_are_hash_bound():
    migration = "sql/migrations/010_m20_open_position_state.sql"
    transfer = mock.Mock(returncode=0, stdout="", stderr="")
    conversion = mock.Mock(stdout=r"\\wsl.localhost\Ubuntu\home\chris\projects\forex\sql\migrations\010_m20_open_position_state.sql\n")
    with mock.patch.object(postgres_pgvector_adapter, "asset", return_value=(migration, "e" * 64)), mock.patch.object(postgres_pgvector_adapter, "subprocess") as process, mock.patch.object(postgres_pgvector_adapter, "remote", return_value={"ok": True}) as remote:
        process.run.side_effect = [conversion, mock.Mock(returncode=0, stdout="", stderr=""), transfer]
        assert postgres_pgvector_adapter.stage_m20_open_position_schema()["ok"]
    staged = remote.call_args.args[0]
    assert "sha256sum" in staged
    assert "install -m 0644" in staged
    assert "FOREX_M20_OPEN_POSITION_STATE_STAGED" in staged
    with mock.patch.object(postgres_pgvector_adapter, "asset", return_value=(migration, "e" * 64)), mock.patch.object(postgres_pgvector_adapter, "remote", return_value={"ok": True}) as remote:
        assert postgres_pgvector_adapter.apply_m20_open_position_schema()["ok"]
    applied = remote.call_args.args[0]
    assert "sha256sum" in applied
    assert "FOREX_M20_OPEN_POSITION_STATE_APPLIED" in applied
