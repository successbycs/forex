import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import types
from datetime import datetime, timedelta, timezone

import pytest

from forex.t480_dependency import inspect_dependency
from scripts import t480_adapter


def _m20_probe_module(monkeypatch):
    fake_mt5 = types.SimpleNamespace(TIMEFRAME_M1=1)
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake_mt5)
    path = t480_adapter.ROOT / "t480" / "m20_demo_trading_session.py"
    spec = importlib.util.spec_from_file_location("m20_demo_trading_session_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_catalog_and_adapter_operations_match():
    t480_adapter.validate_contract()
    catalog = json.loads(t480_adapter.CATALOG_PATH.read_text(encoding="utf-8"))
    assert {entry["id"] for entry in catalog["operations"]} == set(t480_adapter.OPERATIONS)


def test_adapter_emits_the_governed_project_fingerprint_for_evidence_binding():
    fingerprint = t480_adapter.project_configuration_fingerprint()
    assert fingerprint.startswith("sha256:")
    assert len(fingerprint) == 71


def test_adapter_is_read_only_and_has_no_arbitrary_command_surface():
    assert all(not operation.approval_required for operation in t480_adapter.OPERATIONS.values())
    help_text = t480_adapter.parser().format_help()
    assert "--command" not in help_text
    assert "--script" not in help_text
    assert "--approve" not in help_text


def test_configuration_rejects_unknown_fields(tmp_path):
    payload = dict(t480_adapter.APP_CONFIG)
    payload["unexpected"] = "value"
    path = tmp_path / "config.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        t480_adapter.load_application_config(path)


def test_configuration_rejects_unsafe_paths(tmp_path):
    payload = dict(t480_adapter.APP_CONFIG)
    payload["application_root"] = "/safe/path; touch /tmp/not-allowed"
    path = tmp_path / "config.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        t480_adapter.load_application_config(path)


def test_mt5_status_is_process_only():
    operation = t480_adapter.OPERATIONS["mt5_process_status"]
    command = operation.powershell_command or ""
    assert "Get-Process" in command
    assert "MetaTrader5" not in command
    assert "account_info" not in command
    assert "symbol_info_tick" not in command
    assert "order_send" not in command


def test_m1_mt5_probe_is_fixed_and_read_only():
    command = t480_adapter.OPERATIONS["m1_mt5_demo_probe"].powershell_command or ""
    probe = (t480_adapter.ROOT / "t480" / "m1_mt5_demo_probe.py").read_text(encoding="utf-8")
    assert "copy_rates_from_pos" in probe
    assert "TIMEFRAME_H1" in probe
    assert "BAR_COUNT = 720" in probe
    assert "bars_encoding" in probe
    assert "gzip+base64-json" in probe
    assert "symbol_info_tick" not in probe
    assert "order_send" not in probe
    assert "OEM" not in command
    assert "mt5.local.json" in command
    assert "m1_mt5_demo_probe.py" in command
    assert "terminal_path" in command
    assert "python_path" in command
    assert "--command" not in t480_adapter.parser().format_help()
    assert t480_adapter.OPERATIONS["m1_mt5_demo_probe"].approval_required is False

def test_m1_probe_checks_demo_server_before_any_market_data_call():
    probe = (t480_adapter.ROOT / "t480" / "m1_mt5_demo_probe.py").read_text(encoding="utf-8")
    assert probe.index('account.server != "GOMarketsMU-Demo"') < probe.index("symbol_info")
    assert probe.index('account.server != "GOMarketsMU-Demo"') < probe.index("copy_rates_from_pos")

def test_m1_verification_marker_is_reserved_for_a_successful_fixed_probe(monkeypatch):
    monkeypatch.setattr(t480_adapter, "require_dependency", lambda _: None)
    monkeypatch.setattr(t480_adapter, "append_execution_log", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        t480_adapter,
        "execute",
        lambda operation_id: {"operation": operation_id, "ok": True, "result": {}},
    )
    assert t480_adapter.main(["verify", "--operation", "m1_mt5_demo_probe"]) == 0


def test_requirements_prohibit_trading_and_arbitrary_market_data_access():
    prohibited = " ".join(t480_adapter.requirements()["prohibited"])
    assert "generic MetaTrader API" in prohibited
    assert "arbitrary" in prohibited
    assert "order" in prohibited


def test_m20_session_operation_is_fixed_demo_only_fresh_data_capture():
    command = t480_adapter.OPERATIONS["m20_demo_trading_session"].powershell_command or ""
    probe = (t480_adapter.ROOT / "t480" / "m20_demo_trading_session.py").read_text(encoding="utf-8")
    assert "m20_demo_session.local.json" in command
    assert "m20_demo_trading_session.py" in command
    assert "m20_postgres_audit_bridge.py" in command
    assert "Get-FileHash" in command
    assert "FOREX_M20_POSTGRES_AUDIT_BRIDGE_SHA256" in command
    assert "FOREX_M20_CONFIGURATION_FINGERPRINT" in command
    assert "FOREX_M20_TICK_TIME_OFFSET_SECONDS" in command
    assert "FOREX_M20_APPLICATION_REVISION" in command
    assert "GOMarketsMU-Demo" in probe
    assert "GOMarketsMU-Live" not in probe
    assert "symbol_info_tick" in probe
    assert "TIMEFRAME_M1" in probe
    assert "TIMEFRAME_M5" not in probe
    assert "copy_rates_from_pos" in probe
    assert "MAX_TICK_AGE_SECONDS = 30" in probe
    assert "tick_time_offset_seconds" in probe
    assert "FOREX_M20_DEMO_TRADING_OPERATION_OK" in probe
    assert '"persist-proposal"' in probe
    assert '"reconcile"' in probe
    assert "order_send" in probe
    capture_source = probe[probe.index("def capture("):]
    assert capture_source.index('"reserve-execution"') < capture_source.index("order_send")
    assert "positions_get" in probe
    assert t480_adapter.OPERATIONS["m20_demo_trading_session"].approval_required is False


def test_m20_listener_status_is_fixed_and_redacted():
    command = t480_adapter.OPERATIONS["m20_listener_status"].powershell_command
    assert "m20_demo_listener_status.local.json" in command
    assert "C:\\ProgramData\\ForexListener\\state" in command
    assert "Documents\\Code\\forex-m1-probe\\m20_demo_listener_status" not in command
    assert "m20_demo_listener_service.local.json" not in command
    assert "FOREX_M20_POSTGRES_DSN" not in command
    assert "heartbeat_at_nzst" in command and "next_assessment_at_nzst" in command
    assert "heartbeat_age_seconds" in command
    assert "release_id=$s.release_id" in command
    assert "task_action=$taskAction" in command
    assert "$age -ge 30" in command
    assert "state=if ($stale) { 'STALE' }" in command
    assert "Forex-M20-Demo-Listener" in command
    assert "RESTART_REQUESTED" in command and "COOLDOWN" in command
    assert "assessment_total=$s.assessment_total" in command
    assert "$s.monitor.state -eq 'RUNNING'" in command


def test_m20_listener_recovery_is_fixed_to_the_listener_task_only():
    command = t480_adapter.OPERATIONS["m20_listener_recover"].powershell_command
    assert "Get-ScheduledTask -TaskName 'Forex-M20-Demo-Listener'" in command
    assert "Stop-ScheduledTask -TaskName 'Forex-M20-Demo-Listener'" in command
    assert "Start-ScheduledTask -TaskName 'Forex-M20-Demo-Listener'" in command
    assert "order_send" not in command
    assert "FOREX_M20_POSTGRES_DSN" not in command


def test_m20_demo_lease_activation_is_fixed_bounded_and_secret_free():
    command = t480_adapter.OPERATIONS["m20_listener_activate_demo_lease"].powershell_command
    for required in ("GOMarketsMU-Demo", "EURUSD", "9999-12-31T23:59:59Z", "maximum_duration_minutes=0", "maximum_trades=10", "maximum_notional_per_trade_usd=10000", "maximum_cumulative_notional_usd=100000", "maximum_loss_per_trade_aud=100"):
        assert required in command
    assert "GOMarketsMU-Live" not in command
    assert "POSTGRES_DSN" not in command


def test_m20_listener_stop_is_fixed_to_the_listener_task_only():
    command = t480_adapter.OPERATIONS["m20_listener_stop"].powershell_command
    assert "Get-ScheduledTask -TaskName 'Forex-M20-Demo-Listener'" in command
    assert "Stop-ScheduledTask -TaskName 'Forex-M20-Demo-Listener'" in command
    assert "Start-ScheduledTask" not in command
    assert "ProgramData\\ForexListener\\releases" in command
    assert "m20_demo_listener_service.payload" in command
    assert "order_send" not in command


def test_m20_listener_install_is_hash_checked_and_fixed():
    command = t480_adapter.OPERATIONS["m20_listener_install"].powershell_command
    assert "Forex-M20-Demo-Listener" in command
    assert "Register-ScheduledTask" in command
    assert "m20_demo_listener_service.local.json" in command
    assert "m20_demo_listener_service.payload" in command
    assert "C:\\ProgramData\\ForexListener" in command
    assert "Export-ScheduledTask" in command
    assert "M20 deployment rolled back" in command
    assert "-RestartCount 3" in command
    assert "-ExecutionTimeLimit ([TimeSpan]::Zero)" in command
    assert "FOREX_M20_POSTGRES_DSN" not in command


def test_m20_listener_prepare_verifies_all_payloads_before_activation():
    command = t480_adapter.OPERATIONS["m20_listener_prepare"].powershell_command
    assert "Get-FileHash" in command
    assert "m20_demo_listener_service.local.json" in command
    assert "Register-ScheduledTask" not in command


def test_m20_listener_staging_is_split_and_hash_checked():
    first = t480_adapter.OPERATIONS["m20_listener_stage_1"].powershell_command
    final = t480_adapter.OPERATIONS["m20_listener_stage_12"].powershell_command
    assert len(first) < 4000 and len(final) < 4000
    assert "WriteAllBytes" in first
    assert "Add-Content" in final and "Get-FileHash" in final


def test_m20_listener_runner_and_bridge_staging_are_fixed_and_hash_checked():
    runner_first = t480_adapter.OPERATIONS["m20_listener_runner_stage_1"].powershell_command
    runner_final = t480_adapter.OPERATIONS["m20_listener_runner_stage_40"].powershell_command
    bridge_first = t480_adapter.OPERATIONS["m20_listener_bridge_stage_1"].powershell_command
    bridge_final = t480_adapter.OPERATIONS["m20_listener_bridge_stage_24"].powershell_command
    for first, final, filename in (
        (runner_first, runner_final, "m20_demo_trading_session.payload"),
        (bridge_first, bridge_final, "m20_postgres_audit_bridge.payload"),
    ):
        assert "WriteAllBytes" in first
        assert "Add-Content" in final
        assert "Get-FileHash" in final
        assert filename in first and filename in final


def test_m20_runner_builds_the_same_no_trade_shape_accepted_by_the_evidence_contract(monkeypatch):
    from scripts.m20_demo_evidence_contract import validate_payload

    probe = _m20_probe_module(monkeypatch)
    observed = datetime(2026, 9, 3, 0, 10, tzinfo=timezone.utc)
    stamp = lambda value: value.isoformat().replace("+00:00", "Z")
    session = {
        "session_id": "06f0cf82-0651-423a-9c08-078dce04db21", "server": "GOMarketsMU-Demo",
        "instrument": "EURUSD", "starts_at_utc": stamp(observed.replace(minute=0)),
        "expires_at_utc": stamp(observed + timedelta(minutes=50)), "max_trades": 10,
            "max_notional_per_trade_usd": 10000, "max_cumulative_notional_usd": 100000,
            "max_open_positions": 1, "maximum_loss_per_trade_aud": 100, "strategy_version": probe.STRATEGY_VERSION,
        "operator_label": probe.OPERATOR_LABEL, "status": "ACTIVE",
    }
    def bars(timeframe, minutes, values):
        return [
            {"timeframe": timeframe, "opened_at_utc": stamp(observed - timedelta(minutes=minutes * (2 - index))),
             "closed_at_utc": stamp(observed - timedelta(minutes=minutes * (1 - index))), "close": value}
            for index, value in enumerate(values)
        ]
    # The M1-only runner does not collect or retain M5 candles.
    raw_bars = {"M1": bars("M1", 1, (1.1000, 1.1001)), "M5": []}
    tick = {"observed_at_utc": stamp(observed), "freshness_seconds": 2, "bid": 1.1, "ask": 1.1002, "spread_points": 2.0}
    snapshot, proposal = probe._assessment(session, tick, raw_bars, observed.replace(second=2), {"volume": 0.01, "tick_size": 0.00001, "tick_value_loss": 1.395, "point": 0.00001}, 0.25)
    digest = "sha256:" + "a" * 64
    payload = {
        "configuration_fingerprint": digest, "session": session, "decision_snapshot": snapshot, "proposal": proposal,
        "execution": {"status": "NOT_SUBMITTED", "attempt_id": None},
        "reconciliation": {"session_id": session["session_id"], "proposal_id": proposal["proposal_id"], "snapshot_id": snapshot["snapshot_id"], "execution_attempt_id": None, "status": "NO_TRADE_RECONCILED"},
        "postgres_audit": {"session_id": session["session_id"], "proposal_id": proposal["proposal_id"], "snapshot_id": snapshot["snapshot_id"], "execution_attempt_id": None, "record_sha256": digest},
    }
    assert proposal["action"] == "NO_TRADE"
    validate_payload(payload, digest)


def test_m20_shadow_strategy_comparisons_are_closed_candle_only_and_cannot_execute(monkeypatch):
    probe = _m20_probe_module(monkeypatch)
    bars = [
        {"open": 1.10000 + index * .00001, "high": 1.10003 + index * .00001,
         "low": 1.09998 + index * .00001, "close": 1.10001 + index * .00001}
        for index in range(12)
    ]
    assessments = probe._strategy_assessments(
        m1=bars,
        tick={"observed_at_utc": "2026-09-03T09:00:00Z", "spread_points": 8.0},
        active_action="NO_TRADE",
    )
    assert [item["id"] for item in assessments] == [
        "momentum_breakout", "compression_breakout", "trend_pullback",
        "range_reversion", "session_breakout",
    ]
    assert assessments[0]["eligible_for_execution"] is True
    assert all(item["eligible_for_execution"] is False for item in assessments[1:])
    assert all(item["signal"] in {"BUY", "SELL", "NO_TRADE"} for item in assessments)


def test_m20_audit_bridge_is_fixed_and_fails_closed_without_local_deployment():
    bridge = (t480_adapter.ROOT / "t480" / "m20_postgres_audit_bridge.py").read_text(encoding="utf-8")
    assert "FOREX_M20_POSTGRES_DSN" in bridge
    assert "psycopg.connect" in bridge
    assert "persist-proposal" in bridge
    assert "reserve-execution" in bridge
    assert "record-result" in bridge
    assert "record-closed-outcome" in bridge
    assert "estimated_total_cost_account" in bridge
    assert "reconcile" in bridge
    assert "pg_advisory_xact_lock" in bridge
    assert "FOR UPDATE SKIP LOCKED" in bridge
    assert "SELECT pg_advisory_xact_lock" in bridge
    assert "GOMarketsMU-Demo" in bridge
    assert "GOMarketsMU-Live" not in bridge
    assert "order_send" not in bridge
    assert "sys.argv[1] if len(sys.argv) == 2" in bridge
    assert "M20 audit bridge command is not fixed" in bridge


def test_m20_reconciliation_requires_both_closed_event_and_outcome():
    bridge = (t480_adapter.ROOT / "t480" / "m20_postgres_audit_bridge.py").read_text(encoding="utf-8")
    assert '"CLOSED" in row[4]' in bridge
    assert 'row[5] is not None' in bridge
    assert 'row[10] == "MATCHED"' in bridge
    assert 'else "PENDING"' in bridge
    assert 'row[1] == "NO_TRADE" and row[3] is None' in bridge
    assert '"costs"' in bridge


def test_m20_session_operation_has_no_caller_supplied_arguments():
    help_text = t480_adapter.parser().format_help()
    assert "m20_demo_trading_session" in t480_adapter.OPERATIONS
    assert "--symbol" not in help_text
    assert "--server" not in help_text
    assert "--timeframe" not in help_text
    assert "--lease" not in help_text


def test_m20_session_lease_rejects_missing_audit_or_widened_cap(tmp_path, monkeypatch):
    probe = _m20_probe_module(monkeypatch)
    lease = {
        "schema_version": "forex.m20.demo-session-lease.v1",
        "session_id": "06f0cf82-0651-423a-9c08-078dce04db21",
        "enabled": True,
        "server": "GOMarketsMU-Demo",
        "symbol": "EURUSD",
        "starts_at_utc": "2026-09-03T00:00:00Z",
        "expires_at_utc": "2026-09-03T01:00:00Z",
        "maximum_trades": 10,
        "maximum_duration_minutes": 60,
        "maximum_open_positions": 1,
        "maximum_notional_per_trade_usd": 100,
        "maximum_cumulative_notional_usd": 1000,
        "maximum_loss_per_trade_aud": 100,
        "audit_prerequisites": {
            "postgres_audit_schema": "READY",
            "proposal_persistence": "READY",
            "idempotency_store": "READY",
        },
    }
    path = tmp_path / "m20_demo_session.local.json"
    path.write_text(json.dumps(lease), encoding="utf-8")
    now = datetime(2026, 9, 3, 0, 30, tzinfo=timezone.utc)
    assert probe.load_session_lease(path, now)["maximum_trades"] == 10
    lease["maximum_trades"] = 11
    path.write_text(json.dumps(lease), encoding="utf-8")
    with pytest.raises(SystemExit, match="outside its fixed cap"):
        probe.load_session_lease(path, now)
    lease["maximum_trades"] = 10
    lease["audit_prerequisites"] = {}
    path.write_text(json.dumps(lease), encoding="utf-8")
    with pytest.raises(SystemExit, match="audit prerequisites are absent"):
        probe.load_session_lease(path, now)


def test_m20_risk_stop_is_conservative_against_the_aud_loss_cap(monkeypatch):
    probe = _m20_probe_module(monkeypatch)
    entry, volume, tick_size, tick_value, point = 1.16018, 0.01, 0.00001, 1.395, 0.00001
    stop, _, _ = probe._risk_levels(
        action="SELL", entry=entry, volume=volume, tick_size=tick_size,
        tick_value_loss=tick_value, point=point, maximum_loss_aud=100,
    )
    actual_loss = abs(entry - stop) / tick_size * volume * tick_value
    assert actual_loss <= 100
    with pytest.raises(SystemExit, match="minimum EURUSD price increment"):
        probe._risk_levels(
            action="BUY", entry=entry, volume=volume, tick_size=tick_size,
            tick_value_loss=20_000, point=point, maximum_loss_aud=100,
        )


def test_m20_monitor_requires_two_new_opposite_closed_m1_candles(monkeypatch):
    probe = _m20_probe_module(monkeypatch)
    opened_at = datetime(2026, 9, 3, 0, 0, 30, tzinfo=timezone.utc)
    stamp = lambda value: value.isoformat().replace("+00:00", "Z")
    bars = [
        {"opened_at_utc": stamp(datetime(2026, 9, 3, 0, 0, tzinfo=timezone.utc)), "closed_at_utc": stamp(datetime(2026, 9, 3, 0, 1, tzinfo=timezone.utc)), "open": 1.1000, "close": 1.0999},
        {"opened_at_utc": stamp(datetime(2026, 9, 3, 0, 1, tzinfo=timezone.utc)), "closed_at_utc": stamp(datetime(2026, 9, 3, 0, 2, tzinfo=timezone.utc)), "open": 1.0999, "close": 1.0998},
    ]
    assert probe._two_opposite_completed_m1_candles(bars=bars, action="BUY", opened_at=opened_at)
    assert not probe._two_opposite_completed_m1_candles(bars=bars, action="SELL", opened_at=opened_at)
    assert not probe._two_opposite_completed_m1_candles(bars=bars, action="BUY", opened_at=datetime(2026, 9, 3, 0, 1, 30, tzinfo=timezone.utc))


def test_shared_core_root_cannot_be_redirected_by_environment(monkeypatch):
    monkeypatch.setenv("CS_AI_LAB_INFRA_ROOT", "/tmp/untrusted-core")
    assert t480_adapter.SHARED_CORE_ROOT == Path(
        t480_adapter.APP_CONFIG["shared_core"]["repository_root"]
    )


def test_t480_target_configuration_includes_the_configured_shared_lab_root():
    assert t480_adapter.SHARED_LAB_TARGET_PATH == Path(
        t480_adapter.APP_CONFIG["shared_lab_root"]
    ) / ".env.t480.local"


def test_shared_dependency_allows_unrelated_owner_changes_but_rejects_locked_file_drift(tmp_path):
    repository = tmp_path / "shared-core"
    repository.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
    paths = ["t480_core/__init__.py", "t480_core/core.py", "t480/transport-config.json"]
    for index, relative in enumerate(paths):
        path = repository / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"locked-content-{index}\n", encoding="utf-8")
    subprocess.run(["git", "add", "--", *paths], cwd=repository, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Forex Test",
            "-c",
            "user.email=forex-test@example.invalid",
            "commit",
            "-qm",
            "fixture",
        ],
        cwd=repository,
        check=True,
    )
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repository, text=True, capture_output=True, check=True
    ).stdout.strip()
    config = {
        "shared_core": {
            "repository": "fixture/shared-core",
            "repository_root": str(repository),
            "expected_git_revision": revision,
            "require_clean_worktree": False,
            "require_tracked_files": True,
            "files": [
                {
                    "path": relative,
                    "sha256": hashlib.sha256((repository / relative).read_bytes()).hexdigest(),
                }
                for relative in paths
            ],
        }
    }
    assert inspect_dependency(config)["ok"] is True
    config["shared_core"]["expected_git_revision"] = "0" * 40
    revision_drift = inspect_dependency(config)
    assert revision_drift["ok"] is False
    assert "owner repository revision does not match the locked revision" in revision_drift["errors"]
    config["shared_core"]["expected_git_revision"] = revision
    (repository / paths[1]).write_text("drifted\n", encoding="utf-8")
    drifted = inspect_dependency(config)
    assert drifted["ok"] is False
    assert f"locked dependency hash mismatch: {paths[1]}" in drifted["errors"]
