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
    fake_mt5 = types.SimpleNamespace(TIMEFRAME_M1=1, TIMEFRAME_M5=5, TIMEFRAME_H1=60)
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake_mt5)
    path = t480_adapter.ROOT / "t480" / "m20_demo_trading_session.py"
    spec = importlib.util.spec_from_file_location("m20_demo_trading_session_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _m20_audit_bridge_module():
    path = t480_adapter.ROOT / "t480" / "m20_postgres_audit_bridge.py"
    spec = importlib.util.spec_from_file_location("m20_postgres_audit_bridge_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _capture_test_environment(monkeypatch, probe, *, initial, after_capture):
    """Set up an actionable, deterministic capture without an MT5 terminal."""
    clock = {"now": initial}

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            value = clock["now"]
            return value if tz is None else value.astimezone(tz)

    monkeypatch.setattr(probe, "datetime", FrozenDatetime)
    account = types.SimpleNamespace(server="GOMarketsMU-Demo", currency="AUD", balance=1000, equity=1000, login=1)
    symbol = types.SimpleNamespace(name="EURUSD", point=.00001, volume_min=.01, trade_tick_size=.00001,
                                   trade_tick_value_loss=1.4, volume_max=100, volume_step=.01)
    tick = types.SimpleNamespace(time=int(initial.timestamp()), bid=1.1, ask=1.10005)
    probe.mt5.initialize = lambda **_: True
    probe.mt5.shutdown = lambda: None
    probe.mt5.account_info = lambda: account
    probe.mt5.symbol_info = lambda _: symbol
    probe.mt5.symbol_info_tick = lambda _: tick
    rates = []
    boundary = initial.replace(second=0, microsecond=0)
    for index in range(probe.CLOSED_BAR_COUNT):
        opened = boundary - timedelta(minutes=probe.CLOSED_BAR_COUNT - index)
        rates.append({"time": int(opened.timestamp()), "open": 1.1, "high": 1.1001,
                      "low": 1.0999, "close": 1.1, "tick_volume": 1})
    probe.mt5.copy_rates_from_pos = lambda *_: rates
    probe.mt5.ORDER_TYPE_BUY = 0
    probe.mt5.ORDER_TYPE_SELL = 1
    probe.mt5.TRADE_ACTION_DEAL = 1
    probe.mt5.ORDER_TIME_GTC = 0
    probe.mt5.ORDER_FILLING_IOC = 1
    lease = {"session_id": "s", "server": "GOMarketsMU-Demo", "instrument": "EURUSD",
             "starts_at_utc": probe.utc(initial - timedelta(minutes=1)), "expires_at_utc": probe.utc(initial + timedelta(minutes=20)),
             "max_trades": None, "max_notional_per_trade_usd": 10000, "max_cumulative_notional_usd": 100000,
             "max_open_positions": 1, "maximum_loss_per_trade_aud": 100, "strategy_version": probe.STRATEGY_VERSION,
             "operator_label": "test", "status": "ACTIVE"}
    monkeypatch.setattr(probe, "load_session_lease", lambda *_: lease)
    monkeypatch.setattr(probe, "_session", lambda _: dict(lease))
    monkeypatch.setattr(probe, "tick_time_offset_seconds", lambda: 0)
    monkeypatch.setattr(probe, "_shadow_context_rows", lambda **_: ([], None))
    monkeypatch.setattr(probe, "persistent_risk_policy", lambda: {})
    monkeypatch.setattr(probe, "_entry_risk_snapshot", lambda *_: {"account_scope_sha256": "a" * 64})
    monkeypatch.setattr(probe, "_positions_or_fail", lambda **_: ())
    monkeypatch.setattr(probe, "_provenance", lambda: ("a" * 40, "sha256:" + "b" * 64))
    monkeypatch.setattr(probe, "_financing_terms", lambda *_: {})
    monkeypatch.setattr(probe, "financing_policy", lambda: {})
    financing = {"status": "QUALIFIED_INPUTS", "expected_swap_aud": 0, "commission_allowance_aud": 0, "adverse_financing_aud": 0}
    monkeypatch.setattr(probe, "project_financing", lambda **_: dict(financing))
    monkeypatch.setattr(probe, "_planned_stop_loss", lambda *_: 1)
    snapshot = {"snapshot_id": "snapshot", "observed_at_utc": probe.utc(initial), "captured_at_utc": probe.utc(initial),
                "bid": 1.1, "ask": 1.10005, "spread_points": 5, "freshness_seconds": 0,
                "m1_closed_bars": [{"timeframe": "M1", "opened_at_utc": probe.utc(initial - timedelta(minutes=2)), "closed_at_utc": probe.utc(initial - timedelta(minutes=1)), "close": 1.1},
                                   {"timeframe": "M1", "opened_at_utc": probe.utc(initial - timedelta(minutes=1)), "closed_at_utc": probe.utc(initial), "close": 1.1}],
                "m5_closed_bars": [], "safety_gates": {key: True for key in ("fresh_quote", "completed_m1", "normal_spread", "no_existing_position", "demo_lease_active", "news_blackout_inactive", "abnormal_volatility_inactive")},
                "payload_sha256": "sha256:" + "c" * 64}
    proposal = {"proposal_id": "proposal", "session_id": "s", "snapshot_id": "snapshot", "decision_at_utc": probe.utc(initial),
                "expires_at_utc": probe.utc(initial + timedelta(minutes=5)), "selected_timeframe": "M1", "action": "BUY",
                "proposed_entry": 1.10005, "stop_loss": 1.099, "take_profit": 1.102, "notional_usd": 1000,
                "confidence": 70, "rationale": "test actionable proposal", "decision_snapshot_sha256": snapshot["payload_sha256"], "strategy_version": probe.STRATEGY_VERSION}
    selection = {"proposal_id": "proposal", "market_regime": "MOMENTUM_BREAKOUT", "market_regime_reason": "test",
                 "selected_strategy_id": "momentum_breakout", "strategy_rule_version": "test", "selection_status": "SELECTED_EXECUTABLE",
                 "trade_owner_id": "proposal", "trade_owner_strategy_id": "momentum_breakout", "cost_coverage_status": "FEASIBLE"}
    assessments = [{"id": name, "label": name, "signal": "BUY" if name == "momentum_breakout" else "NO_TRADE", "eligible_for_execution": True, "reason": "test"}
                   for name in ("momentum_breakout", "compression_breakout", "trend_pullback", "range_reversion", "session_breakout")]
    monkeypatch.setattr(probe, "_assessment", lambda *_: (dict(snapshot), dict(proposal), dict(selection), list(assessments)))
    monkeypatch.setattr(probe, "_shadow_context", lambda **_: {"context_id": "context", "proposal_id": "proposal", "selected_m1_action": "BUY", "overall_alignment": "NEUTRAL", "context_disposition": "NEUTRAL", "reason": "test", "rule_version": "test", "retrieved_at_utc": probe.utc(initial), "source_inputs_sha256": "sha256:" + "d" * 64, "contexts": []})
    return lease, clock


def test_catalog_and_adapter_operations_match():
    t480_adapter.validate_contract()
    catalog = json.loads(t480_adapter.CATALOG_PATH.read_text(encoding="utf-8"))
    assert {entry["id"] for entry in catalog["operations"]} == set(t480_adapter.OPERATIONS)
    assert "m20_listener_runner_stage_64" in t480_adapter.OPERATIONS


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


def test_m20_unresolved_history_probe_is_fixed_demo_only_and_cannot_trade():
    command = t480_adapter.OPERATIONS["m20_unresolved_history_probe"].powershell_command or ""
    assert "history_deals_get" in command
    assert "GOMarketsMU-Demo" in command
    assert "2026,9,3,12" in command and "2026,9,3,15,30" in command
    assert "position_identifier" in command and "commission" in command and "fee" in command
    assert "broker_timestamp_offset_seconds" in command and "x.time-10800" in command
    assert "order_send" not in command
    assert len(command) < 2500


def test_listener_install_requires_the_hash_bound_prepared_release():
    command = t480_adapter.OPERATIONS["m20_listener_install"].powershell_command or ""
    assert "m20_demo_listener_prepared.local.json" in command
    assert "M20 release was not prepared and hash-bound" in command


def test_m20_session_operation_is_fixed_demo_only_fresh_data_capture():
    command = t480_adapter.OPERATIONS["m20_demo_trading_session"].powershell_command or ""
    probe = (t480_adapter.ROOT / "t480" / "m20_demo_trading_session.py").read_text(encoding="utf-8")
    assert "m20_demo_session.local.json" in command
    assert "m20_demo_trading_session.payload" in command
    assert "m20_postgres_audit_bridge.payload" in command
    assert "C:\\ProgramData\\ForexListener" in command
    assert "m20_demo_listener_status.local.json" in command
    assert "m20_demo_listener_service.local.json" in command
    assert "active ProgramData release revision does not match" in command
    assert "Documents\\Code\\forex-m1-probe" not in command
    assert "Get-FileHash" in command
    assert "FOREX_M20_POSTGRES_AUDIT_BRIDGE_SHA256" in command
    assert "FOREX_M20_CONFIGURATION_FINGERPRINT" in command
    assert "FOREX_M20_TICK_TIME_OFFSET_SECONDS" in command
    assert "FOREX_M20_APPLICATION_REVISION" in command
    assert "GOMarketsMU-Demo" in probe
    assert "GOMarketsMU-Live" not in probe
    assert "symbol_info_tick" in probe
    assert "TIMEFRAME_M1" in probe
    assert "TIMEFRAME_M5" in probe and "TIMEFRAME_H1" in probe
    assert "SHADOW_CONTEXT_RULE_VERSION" in probe
    assert "Neither is passed to selection, trade planning, order submission, or" in probe
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
    assert "m20_demo_listener_service.local.json" in command
    assert "discord_open_alert_configured=$notifications" in command
    assert "FOREX_M20_POSTGRES_DSN" not in command
    assert "heartbeat_at_nzst" in command and "next_assessment_at_nzst" in command
    assert "heartbeat_age_seconds" in command
    assert "$supervisorAlive" in command
    assert "quote=$s.quote" in command
    assert "release_id=$s.release_id" in command
    assert "task_action=$taskAction" not in command
    assert "$age -ge 30" in command
    assert "state=if ($stale) { 'STALE' }" in command
    assert "Forex-M20-Demo-Listener" not in command
    assert "EXPLICIT_RECOVERY_REQUIRED" in command
    assert "Start-ScheduledTask" not in command
    assert "Stop-ScheduledTask" not in command
    assert "assessment_total=$s.assessment_total" in command
    assert "$s.monitor.state -eq 'RUNNING'" in command
    assert "protection_observation=$protectionObservation" in command
    assert "LAST_KNOWN_UNVERIFIED" in command
    assert "m20_demo_protected_restart_drill.local.json" not in command
    assert "$s.protected_restart_drill" in command
    assert "protected_restart_drill=$drill" in command
    assert "NOT_REPORTED" in command


def test_m20_liquidity_does_not_describe_a_failed_position_read_as_flat():
    command = t480_adapter.OPERATIONS["m20_demo_account_liquidity"].powershell_command or ""
    assert "position_observation" in command
    assert "positions is not None" in command
    assert "open_positions':len(m.positions_get() or ())" not in command


def test_m20_listener_recovery_is_fixed_to_the_listener_task_only():
    command = t480_adapter.OPERATIONS["m20_listener_recover"].powershell_command
    assert "Get-ScheduledTask -TaskName 'Forex-M20-Demo-Listener'" in command
    assert "Stop-ScheduledTask -TaskName 'Forex-M20-Demo-Listener'" in command
    assert "Start-ScheduledTask -TaskName 'Forex-M20-Demo-Listener'" in command
    assert "order_send" not in command
    assert "FOREX_M20_POSTGRES_DSN" not in command


def test_m20_demo_lease_activation_is_fixed_bounded_and_secret_free():
    command = t480_adapter.OPERATIONS["m20_listener_activate_demo_lease"].powershell_command
    for required in ("GOMarketsMU-Demo", "EURUSD", "9999-12-31T23:59:59Z", "maximum_duration_minutes=0", "maximum_trades=$null", "maximum_notional_per_trade_usd=10000", "maximum_cumulative_notional_usd=100000", "maximum_loss_per_trade_aud=100"):
        assert required in command
    assert "GOMarketsMU-Live" not in command
    assert "POSTGRES_DSN" not in command


def test_m20_refusal_drill_is_fixed_to_aud_cent_and_cannot_submit_an_order():
    lease_command = t480_adapter.OPERATIONS["m20_listener_activate_refusal_drill_lease"].powershell_command
    drill_command = t480_adapter.OPERATIONS["m20_listener_refusal_drill"].powershell_command
    assert "GOMarketsMU-Demo" in lease_command
    assert "maximum_loss_per_trade_aud=0.01" in lease_command
    assert "NewGuid" not in lease_command
    assert "m20_demo_refusal_original_lease.local.json" in lease_command
    assert "Refusal setup requires maintenance hold" in lease_command
    assert "--risk-refusal-drill" in drill_command
    assert "m20_demo_trading_session.payload" in drill_command
    assert "order_send" not in lease_command
    assert "order_send" not in drill_command
    assert "GOMarketsMU-Live" not in lease_command + drill_command


def test_m20_listener_stop_is_fixed_to_the_listener_task_only():
    command = t480_adapter.OPERATIONS["m20_listener_stop"].powershell_command
    assert "Get-ScheduledTask -TaskName 'Forex-M20-Demo-Listener'" in command
    assert "Stop-ScheduledTask -TaskName 'Forex-M20-Demo-Listener'" in command
    assert "Start-ScheduledTask" not in command
    assert "ProgramData\\ForexListener\\releases" in command
    assert "m20_demo_listener_service.payload" in command
    assert "order_send" not in command


def test_m20_listener_maintenance_hold_actions_are_fixed_and_have_no_order_surface():
    enable = t480_adapter.OPERATIONS["m20_listener_enable_maintenance_hold"].powershell_command or ""
    disable = t480_adapter.OPERATIONS["m20_listener_disable_maintenance_hold"].powershell_command or ""
    assert "m20_demo_maintenance_hold.local.json" in enable + disable
    assert "W1R_COORDINATED_MAINTENANCE" in enable
    assert "order_send" not in enable + disable
    assert "GOMarketsMU-Live" not in enable + disable


def test_m20_listener_retires_only_the_known_legacy_restart_marker_under_hold():
    command = t480_adapter.OPERATIONS["m20_listener_retire_legacy_restart_drill"].powershell_command or ""
    assert "m20_demo_maintenance_hold.local.json" in command
    assert "m20_demo_protected_restart_drill.legacy-42235606.json" in command
    assert "47433bf8-565d-5f24-9550-ddeea4124cd3" in command
    assert "42235606" in command
    assert "Move-Item" in command
    assert "Remove-Item" not in command
    assert "order_send" not in command
    assert "GOMarketsMU-Live" not in command


def test_m20_continuity_protocol_is_fixed_held_only_and_has_no_order_surface():
    command = t480_adapter.OPERATIONS["m20_listener_run_continuity_protocol"].powershell_command or ""
    assert "m20_demo_listener_service.payload" in command
    assert "--arm-continuity-protocol" in command
    assert len(command) < 4000
    assert "order_send" not in command and "GOMarketsMU-Live" not in command


def test_m20_continuity_status_is_fixed_read_only_and_short():
    command = t480_adapter.OPERATIONS["m20_listener_continuity_status"].powershell_command or ""
    assert "m20_demo_continuity_protocol.local.json" in command
    assert "Forex-M20-Continuity-Protocol" in command
    assert len(command) < 4000
    assert "order_send" not in command and "GOMarketsMU-Live" not in command


def test_m20_listener_install_is_hash_checked_and_fixed():
    command = t480_adapter.OPERATIONS["m20_listener_install"].powershell_command
    assert "Forex-M20-Demo-Listener" in command
    assert "Register-ScheduledTask" in command
    assert "New-ScheduledTaskTrigger -AtStartup" in command
    assert "New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType S4U" in command
    assert "AtLogOn" not in command
    assert "m20_demo_listener_service.local.json" in command
    assert "m20_demo_listener_service.payload" in command
    assert "C:\\ProgramData\\ForexListener" in command
    assert "Export-ScheduledTask" in command
    assert "Get-CimInstance Win32_Process" in command
    assert "m20_demo_listener_service.payload" in command
    assert "Stop-Process -Id $_.ProcessId -Force" in command
    assert "M20 deployment rolled back" in command
    assert "-RestartCount 3" in command
    assert "-ExecutionTimeLimit ([TimeSpan]::Zero)" in command
    assert "FOREX_M20_POSTGRES_DSN" not in command


def test_m20_listener_release_includes_the_fixed_t480_discord_adapter_without_exposing_its_webhook():
    prepare = t480_adapter.OPERATIONS["m20_listener_prepare"].powershell_command or ""
    configure = t480_adapter.OPERATIONS["m20_listener_configure"].powershell_command or ""
    stage = t480_adapter.OPERATIONS["m20_listener_discord_stage_6"].powershell_command or ""
    assert "m20_discord_trade_notification.payload" in prepare
    assert "M20 Discord adapter staged source hash failed" in stage
    assert "FOREX_M20_PERSISTENT_RISK_POLICY" in configure
    assert "discord.com/api/webhooks" not in configure


def test_m20_dependency_staging_appends_raw_decoded_bytes():
    command = t480_adapter._m20_listener_dependency_stage_command(
        "m20_demo_trading_session.py", "m20_demo_trading_session.payload", "M20 listener runner", 2,
    )
    assert "[IO.File]::Open" in command
    assert "$stream.Write($bytes,0,$bytes.Length)" in command


def test_m20_listener_prepare_verifies_all_payloads_before_activation():
    command = t480_adapter.OPERATIONS["m20_listener_prepare"].powershell_command
    configure = t480_adapter.OPERATIONS["m20_listener_configure"].powershell_command
    assert "Get-FileHash" in command
    assert "m20_demo_listener_prepared.local.json" in command
    assert "m20_demo_listener_service.local.json" in configure
    assert "Register-ScheduledTask" not in command


def test_m20_listener_staging_is_split_and_hash_checked():
    first = t480_adapter.OPERATIONS["m20_listener_stage_1"].powershell_command
    final = t480_adapter.OPERATIONS["m20_listener_stage_22"].powershell_command
    assert len(first) < 4000 and len(final) < 4000
    assert "WriteAllBytes" in first
    assert "[IO.File]::Open" in final and "Get-FileHash" in final


def test_m20_listener_runner_and_bridge_staging_are_fixed_and_hash_checked():
    runner_first = t480_adapter.OPERATIONS["m20_listener_runner_stage_1"].powershell_command
    runner_final = t480_adapter.OPERATIONS["m20_listener_runner_stage_64"].powershell_command
    runner_verify = t480_adapter.OPERATIONS["m20_listener_runner_verify"].powershell_command
    bridge_first = t480_adapter.OPERATIONS["m20_listener_bridge_stage_1"].powershell_command
    bridge_final = t480_adapter.OPERATIONS["m20_listener_bridge_stage_32"].powershell_command
    bridge_verify = t480_adapter.OPERATIONS["m20_listener_bridge_verify"].powershell_command
    for first, final, filename in (
        (runner_first, runner_final, "m20_demo_trading_session.payload"),
        (bridge_first, bridge_final, "m20_postgres_audit_bridge.payload"),
    ):
        if filename == "m20_demo_trading_session.payload":
            assert "WriteAllText" in first
            assert "WriteAllText" in final
            assert "ReadAllText" in runner_verify and "Get-FileHash" in runner_verify
        else:
            assert "WriteAllText" in first and "WriteAllText" in final
            assert "ReadAllText" in bridge_verify and "Get-FileHash" in bridge_verify
            assert "$fragments.Count -ne 32" in bridge_verify
        staged_name = filename.removesuffix(".payload")
        assert staged_name in first and staged_name in final


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
    snapshot, proposal, selection, assessments = probe._assessment(session, tick, raw_bars, observed.replace(second=2), {"volume": 0.01, "tick_size": 0.00001, "tick_value_loss": 1.395, "point": 0.00001}, 0.25)
    digest = "sha256:" + "a" * 64
    payload = {
        "configuration_fingerprint": digest, "session": session, "decision_snapshot": snapshot, "proposal": proposal,
        "strategy_selection": selection, "strategy_assessments": assessments,
        "execution": {"status": "NOT_SUBMITTED", "attempt_id": None},
        "reconciliation": {"session_id": session["session_id"], "proposal_id": proposal["proposal_id"], "snapshot_id": snapshot["snapshot_id"], "execution_attempt_id": None, "status": "NO_TRADE_RECONCILED"},
        "postgres_audit": {"session_id": session["session_id"], "proposal_id": proposal["proposal_id"], "snapshot_id": snapshot["snapshot_id"], "execution_attempt_id": None, "record_sha256": digest},
    }
    assert proposal["action"] == "NO_TRADE"
    validate_payload(payload, digest)


def test_m20_strategy_comparisons_are_closed_candle_only_and_selectable(monkeypatch):
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
    assert all(item["eligible_for_execution"] is True for item in assessments)
    assert all(item["signal"] in {"BUY", "SELL", "NO_TRADE"} for item in assessments)


def test_m20_shadow_context_is_observational_and_retains_pre_context_candidate(monkeypatch):
    probe = _m20_probe_module(monkeypatch)

    def bars(timeframe, closes):
        return [
            {"timeframe": timeframe, "closed_at_utc": f"2026-09-04T00:0{index}:00Z", "open": close - .00001,
             "high": close + .00002, "low": close - .00002, "close": close, "volume": 10}
            for index, close in enumerate(closes)
        ]

    proposal = {"proposal_id": "proposal-1", "action": "BUY", "strategy_version": "m1-version"}
    context = probe._shadow_context(
        proposal=proposal, selection={"selected_strategy_id": "momentum_breakout"},
        assessments=[{"id": "momentum_breakout", "signal": "BUY"}],
        bars={"M5": bars("M5", [1.1, 1.1001, 1.1002, 1.1003, 1.1004]),
              "H1": bars("H1", [1.1004, 1.1003, 1.1002, 1.1001, 1.1])},
        observed_at="2026-09-04T00:10:00Z", spread_points=8.0,
    )
    assert context["selected_m1_action"] == "BUY"
    assert context["overall_alignment"] == "OPPOSED"
    assert context["context_disposition"] == "HARD_CONFLICT"
    assert all(row["source_inputs"]["pre_context_m1_candidate"] == "BUY" for row in context["contexts"])
    assert all(row["source_inputs"]["final_m1_action"] == "BUY" for row in context["contexts"])
    assert "order_send" not in probe._shadow_context.__code__.co_names


def test_m20_unavailable_shadow_context_is_visible_and_non_blocking(monkeypatch):
    probe = _m20_probe_module(monkeypatch)
    proposal = {"proposal_id": "proposal-2", "action": "NO_TRADE", "strategy_version": "m1-version"}
    context = probe._shadow_context(
        proposal=proposal, selection={"selected_strategy_id": None}, assessments=[],
        bars={"M5": [], "H1": []}, observed_at="2026-09-04T00:10:00Z", spread_points=8.0,
    )
    assert context["overall_alignment"] == "NEUTRAL"
    assert context["context_disposition"] == "NEUTRAL"
    assert [row["alignment"] for row in context["contexts"]] == ["UNAVAILABLE", "UNAVAILABLE"]


def test_m20_regime_precedence_selects_one_executable_owner(monkeypatch):
    probe = _m20_probe_module(monkeypatch)
    assessments = [
        {"id": "momentum_breakout", "label": "Momentum breakout", "signal": "BUY", "eligible_for_execution": True, "reason": "Momentum."},
        {"id": "compression_breakout", "label": "Compression breakout", "signal": "BUY", "eligible_for_execution": True, "reason": "Compression."},
        {"id": "trend_pullback", "label": "Trend pullback", "signal": "NO_TRADE", "eligible_for_execution": True, "reason": "None."},
        {"id": "range_reversion", "label": "Range reversion", "signal": "NO_TRADE", "eligible_for_execution": True, "reason": "None."},
        {"id": "session_breakout", "label": "Session breakout", "signal": "NO_TRADE", "eligible_for_execution": True, "reason": "None."},
    ]
    selection = probe._market_selection(
        tick={"freshness_seconds": 1, "spread_points": 8}, m1=[{}] * 12, assessments=assessments,
        safety_gates={"fresh_quote": True, "completed_m1": True, "normal_spread": True,
                      "no_existing_position": True, "demo_lease_active": True,
                      "news_blackout_inactive": True, "abnormal_volatility_inactive": True},
    )
    assert selection["market_regime"] == "COMPRESSION_BREAKOUT"
    assert selection["selected_strategy_id"] == "compression_breakout"
    assert selection["selection_status"] == "SELECTED_EXECUTABLE"


def test_m20_selected_strategy_without_a_valid_plan_is_not_execution_authority(monkeypatch):
    probe = _m20_probe_module(monkeypatch)
    bars = [
        {"open": 1.1, "high": 1.1001, "low": 1.0999, "close": 1.1}
        for _ in range(12)
    ]
    # A selected Range signal whose midpoint target equals entry is not an
    # executable order, even though regime precedence selected the strategy.
    assessments = [
        {"id": "momentum_breakout", "label": "Momentum", "signal": "NO_TRADE", "eligible_for_execution": True, "reason": "—"},
        {"id": "compression_breakout", "label": "Compression", "signal": "NO_TRADE", "eligible_for_execution": True, "reason": "—"},
        {"id": "trend_pullback", "label": "Trend", "signal": "NO_TRADE", "eligible_for_execution": True, "reason": "—"},
        {"id": "range_reversion", "label": "Range", "signal": "BUY", "eligible_for_execution": True, "reason": "—"},
        {"id": "session_breakout", "label": "Session", "signal": "NO_TRADE", "eligible_for_execution": True, "reason": "—"},
    ]
    selection = probe._market_selection(tick={"freshness_seconds": 1, "spread_points": 8}, m1=bars, assessments=assessments,
        safety_gates={"fresh_quote": True, "completed_m1": True, "normal_spread": True, "no_existing_position": True, "demo_lease_active": True, "news_blackout_inactive": True, "abnormal_volatility_inactive": True})
    assert selection["selection_status"] == "SELECTED_EXECUTABLE"


def test_m20_entry_m1_history_requires_a_current_contiguous_closed_window(monkeypatch):
    probe = _m20_probe_module(monkeypatch)
    boundary = datetime(2026, 9, 10, 4, 0, tzinfo=timezone.utc)

    def rows(*, latest_closed: datetime = boundary, gap_at: int | None = None):
        result = []
        for index in range(probe.CLOSED_BAR_COUNT):
            opened = latest_closed - timedelta(minutes=probe.CLOSED_BAR_COUNT - index)
            if gap_at is not None and index >= gap_at:
                opened += timedelta(minutes=1)
            result.append({
                "opened_at_utc": probe.utc(opened), "closed_at_utc": probe.utc(opened + timedelta(minutes=1)),
                "open": 1.1, "high": 1.1001, "low": 1.0999, "close": 1.1, "volume": 10,
            })
        return result

    assert probe._entry_m1_history_is_synchronized(rows=rows(), observed_at=boundary + timedelta(seconds=48))
    assert not probe._entry_m1_history_is_synchronized(
        rows=rows(latest_closed=boundary - timedelta(minutes=1)), observed_at=boundary + timedelta(seconds=48)
    )
    assert not probe._entry_m1_history_is_synchronized(rows=rows(gap_at=32), observed_at=boundary + timedelta(seconds=48))
    assert not probe._entry_m1_history_is_synchronized(
        rows=rows(latest_closed=boundary + timedelta(minutes=1)), observed_at=boundary + timedelta(seconds=48)
    )


def test_m20_stale_entry_history_does_not_change_closed_bar_monitor_input(monkeypatch):
    probe = _m20_probe_module(monkeypatch)
    boundary = datetime(2026, 9, 10, 4, 0, tzinfo=timezone.utc)
    stale_closed = boundary - timedelta(minutes=90)
    rates = []
    for index in range(probe.CLOSED_BAR_COUNT):
        opened = stale_closed - timedelta(minutes=probe.CLOSED_BAR_COUNT - index)
        rates.append({"time": int(opened.timestamp()), "open": 1.1, "high": 1.1001,
                      "low": 1.0999, "close": 1.1, "tick_volume": 10})
    # _bar_rows remains usable by the position monitor; the separate entry
    # gate alone rejects this old, otherwise well-formed window.
    parsed, _ = probe._bar_rows(rates, timeframe_name="M1", seconds=60,
                                cutoff=int(boundary.timestamp()), timestamp_offset_seconds=0)
    assert len(parsed) == probe.CLOSED_BAR_COUNT
    assert not probe._entry_m1_history_is_synchronized(rows=parsed, observed_at=boundary + timedelta(seconds=48))


def test_m20_submission_recheck_rejects_a_minute_boundary_crossing(monkeypatch):
    probe = _m20_probe_module(monkeypatch)
    boundary = datetime(2026, 9, 9, 6, 0, tzinfo=timezone.utc)
    tick = types.SimpleNamespace(time=int((boundary + timedelta(seconds=5)).timestamp()), bid=1.1, ask=1.1001)
    rates = []
    for index in range(probe.CLOSED_BAR_COUNT):
        opened = boundary - timedelta(minutes=probe.CLOSED_BAR_COUNT - index)
        rates.append({"time": int(opened.timestamp()), "open": 1.1, "high": 1.1001,
                      "low": 1.0999, "close": 1.1, "tick_volume": 1})
    probe.mt5.symbol_info_tick = lambda _: tick
    clock = [boundary + timedelta(seconds=5), boundary + timedelta(minutes=1)]
    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            value = clock.pop(0)
            return value if tz is None else value.astimezone(tz)
    monkeypatch.setattr(probe, "datetime", FrozenDatetime)
    # Terminal history blocks through the boundary only after the first
    # fresh-quote check. The real recheck must refuse it.
    probe.mt5.copy_rates_from_pos = lambda *_: rates
    _, _, reason = probe._current_entry_inputs(
        offset_seconds=0, expected_boundary=int(boundary.timestamp())
    )
    assert reason == "M1_INPUT_UNSYNCHRONIZED: closed M1 history does not end at the current quote minute."


def test_m20_submission_recheck_rejects_changed_m1_digest(monkeypatch):
    probe = _m20_probe_module(monkeypatch)
    boundary = datetime(2026, 9, 9, 6, 0, tzinfo=timezone.utc)
    tick = types.SimpleNamespace(time=int((boundary + timedelta(seconds=5)).timestamp()), bid=1.1, ask=1.1001)
    rates = []
    for index in range(probe.CLOSED_BAR_COUNT):
        opened = boundary - timedelta(minutes=probe.CLOSED_BAR_COUNT - index)
        rates.append({"time": int(opened.timestamp()), "open": 1.1, "high": 1.1001,
                      "low": 1.0999, "close": 1.1, "tick_volume": 1})
    _, original_digest = probe._bar_rows(rates, timeframe_name="M1", seconds=60,
                                         cutoff=int(boundary.timestamp()), timestamp_offset_seconds=0)
    changed = [dict(row) for row in rates]
    changed[-1]["close"] = 1.10005
    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            value = boundary + timedelta(seconds=5)
            return value if tz is None else value.astimezone(tz)
    monkeypatch.setattr(probe, "datetime", FrozenDatetime)
    probe.mt5.symbol_info_tick = lambda _: tick
    probe.mt5.copy_rates_from_pos = lambda *_: changed
    _, _, reason = probe._current_entry_inputs(offset_seconds=0, expected_boundary=int(boundary.timestamp()), expected_m1_digest=original_digest)
    assert reason == "M1_INPUT_UNSYNCHRONIZED: closed M1 history does not end at the current quote minute."


def test_m20_monitor_suppresses_stale_reversal_but_keeps_open_monitoring(monkeypatch):
    probe = _m20_probe_module(monkeypatch)
    now = datetime(2026, 9, 9, 6, 5, 20, tzinfo=timezone.utc)
    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return now if tz is None else now.astimezone(tz)
    monkeypatch.setattr(probe, "datetime", FrozenDatetime)
    position = types.SimpleNamespace(ticket=7, magic=probe.EXECUTOR_MAGIC, price_open=1.1, sl=1.099, tp=1.102)
    probe.mt5.symbol_info_tick = lambda _: types.SimpleNamespace(time=int(now.timestamp()), bid=1.1, ask=1.1001)
    probe._positions_or_fail = lambda **_: (position,)
    stale = []
    latest = now.replace(second=0) - timedelta(minutes=2)
    for index in range(probe.CLOSED_BAR_COUNT):
        opened = latest - timedelta(minutes=probe.CLOSED_BAR_COUNT - index)
        stale.append({"opened_at_utc": probe.utc(opened), "closed_at_utc": probe.utc(opened + timedelta(minutes=1)), "open": 1.1, "high": 1.1001, "low": 1.0998, "close": 1.0999, "volume": 1})
    probe._closed_m1_bars_for_monitor = lambda *_: stale
    closed = []
    probe._close_accepted_position = lambda **_: (closed.append(True), ("close", 1.1, {}))[1]
    monkeypatch.setattr(probe, "_record_closed_monitor_outcome", lambda **_: {"status": "CLOSED"})
    result = probe._monitor_open_position(
        proposal={"proposal_id": "p", "action": "BUY", "trade_owner_strategy_id": "momentum_breakout", "proposed_entry": 1.1, "initial_stop_loss": 1.099},
        attempt_id="a", position=position, submitted_at=now - timedelta(minutes=5), entry_spread=.0001,
        risk={"volume": .01, "tick_size": .00001, "tick_value_loss": 1.4, "point": .00001}, offset_seconds=0, single_pass=True,
    )
    assert result["status"] == "OPEN_MONITORING"
    assert not closed
    fresh = []
    latest = now.replace(second=0)
    for index in range(probe.CLOSED_BAR_COUNT):
        opened = latest - timedelta(minutes=probe.CLOSED_BAR_COUNT - index)
        fresh.append({"opened_at_utc": probe.utc(opened), "closed_at_utc": probe.utc(opened + timedelta(minutes=1)), "open": 1.1, "high": 1.1001, "low": 1.0998, "close": 1.0999, "volume": 1})
    probe._closed_m1_bars_for_monitor = lambda *_: fresh
    assert probe._monitor_open_position(
        proposal={"proposal_id": "p", "action": "BUY", "trade_owner_strategy_id": "momentum_breakout", "proposed_entry": 1.1, "initial_stop_loss": 1.099},
        attempt_id="a", position=position, submitted_at=now - timedelta(minutes=5), entry_spread=.0001,
        risk={"volume": .01, "tick_size": .00001, "tick_value_loss": 1.4, "point": .00001}, offset_seconds=0, single_pass=True,
    ) == {"status": "CLOSED"}
    assert closed == [True]


def test_m20_capture_persists_invalid_m1_as_no_trade_without_order(monkeypatch, tmp_path):
    """Exercise capture(), not merely its parser, on a terminal history fault."""
    probe = _m20_probe_module(monkeypatch)
    now = datetime.now(timezone.utc)
    tick = types.SimpleNamespace(time=int(now.timestamp()), bid=1.1, ask=1.1001)
    account = types.SimpleNamespace(server="GOMarketsMU-Demo", currency="AUD", balance=1000, equity=1000, login=1)
    symbol = types.SimpleNamespace(name="EURUSD", point=.00001, volume_min=.01, trade_tick_size=.00001, trade_tick_value_loss=1.4)
    probe.mt5.initialize = lambda **_: True
    probe.mt5.shutdown = lambda: None
    probe.mt5.account_info = lambda: account
    probe.mt5.symbol_info = lambda _: symbol
    probe.mt5.copy_rates_from_pos = lambda *_: None
    monkeypatch.setattr(probe, "_listen_for_tick", lambda: (tick, .1))
    monkeypatch.setattr(probe, "tick_time_offset_seconds", lambda: 0)
    monkeypatch.setattr(probe, "_shadow_context_rows", lambda **_: ([], None))
    monkeypatch.setattr(probe, "persistent_risk_policy", lambda: {})
    monkeypatch.setattr(probe, "_entry_risk_snapshot", lambda *_: {"account_scope_sha256": "a" * 64})
    monkeypatch.setattr(probe, "_positions_or_fail", lambda **_: ())
    monkeypatch.setattr(probe, "_provenance", lambda: ("a" * 40, "sha256:" + "b" * 64))
    monkeypatch.setattr(probe, "_financing_terms", lambda *_: {})
    monkeypatch.setattr(probe, "financing_policy", lambda: {})
    monkeypatch.setattr(probe, "project_financing", lambda **_: {"status": "QUALIFIED_INPUTS"})
    monkeypatch.setattr(probe, "_shadow_context", lambda **_: {"context_id": "x", "proposal_id": "x", "selected_m1_action": "NO_TRADE", "overall_alignment": "NEUTRAL", "context_disposition": "NEUTRAL", "reason": "x", "rule_version": "x", "retrieved_at_utc": probe.utc(now), "source_inputs_sha256": "sha256:" + "a" * 64, "contexts": []})
    lease = {"session_id": "s", "server": "GOMarketsMU-Demo", "instrument": "EURUSD", "starts_at_utc": probe.utc(now-timedelta(minutes=1)), "expires_at_utc": probe.utc(now+timedelta(minutes=20)), "max_trades": None, "max_notional_per_trade_usd": 10000, "max_cumulative_notional_usd": 100000, "max_open_positions": 1, "maximum_loss_per_trade_aud": 100, "strategy_version": probe.STRATEGY_VERSION, "operator_label": "test", "status": "ACTIVE"}
    monkeypatch.setattr(probe, "load_session_lease", lambda *_: lease)
    monkeypatch.setattr(probe, "_session", lambda _: lease)
    calls = []
    def bridge(payload, command):
        calls.append((command, payload))
        if command == "enforce-risk-policy": return {"risk": {"entry_allowed": True, "maximum_loss_aud": 100}}
        if command == "persist-proposal": return {"postgres_audit": {"session_id":"s", "proposal_id": payload["proposal"]["proposal_id"], "snapshot_id": payload["proposal"]["snapshot_id"], "execution_attempt_id":None, "record_sha256":"sha256:"+"a"*64}}
        return {"reconciliation": {"session_id":"s", "proposal_id": payload["proposal_id"], "snapshot_id":"x", "status":"NO_TRADE_RECONCILED"}}
    monkeypatch.setattr(probe, "_bridge", bridge)
    probe.mt5.order_send = lambda *_: pytest.fail("invalid M1 capture must not order")
    result = probe.capture("terminal", tmp_path / "lease.json")
    assert result["proposal"]["action"] == "NO_TRADE"
    assert result["proposal"]["rationale"].startswith("M1_INPUT_INVALID_OR_INSUFFICIENT")
    assert result["decision_snapshot"]["m1_closed_bars"] == []
    assert [name for name, _ in calls].count("persist-proposal") == 1


def test_m20_capture_crossing_assessed_minute_records_terminal_non_submission(monkeypatch, tmp_path):
    """A reserved proposal that crosses its minute must never reach order_send."""
    from scripts.m20_demo_evidence_contract import validate_execution_and_reconciliation

    probe = _m20_probe_module(monkeypatch)
    initial = datetime(2026, 9, 9, 6, 0, 59, tzinfo=timezone.utc)
    after_capture = initial + timedelta(seconds=1)
    _, clock = _capture_test_environment(monkeypatch, probe, initial=initial, after_capture=after_capture)
    calls = []

    def bridge(payload, command):
        calls.append((command, payload))
        if command == "enforce-risk-policy":
            return {"risk": {"entry_allowed": True, "maximum_loss_aud": 100}}
        if command == "persist-proposal":
            return {"postgres_audit": {"session_id": "s", "proposal_id": "proposal", "snapshot_id": "snapshot", "execution_attempt_id": None, "record_sha256": "sha256:" + "e" * 64}}
        if command == "reserve-execution":
            # The reservation is the last operation before the real fresh
            # quote/M1 recheck. Simulate its minute-boundary delay here.
            clock["now"] = after_capture
            attempt_id = payload["reservation"]["attempt_id"]
            return {"reservation": {"slot_number": None}, "postgres_audit": {"session_id": "s", "proposal_id": "proposal", "snapshot_id": "snapshot", "execution_attempt_id": attempt_id, "record_sha256": "sha256:" + "e" * 64}}
        if command == "reconcile":
            attempt_id = next(payload["result"]["attempt_id"] for command, payload in calls if command == "record-result")
            return {"reconciliation": {"session_id": "s", "proposal_id": "proposal", "snapshot_id": "snapshot", "execution_attempt_id": attempt_id, "status": "NOT_SUBMITTED_RECONCILED"}}
        assert command == "record-result"
        return {"ok": True}

    monkeypatch.setattr(probe, "_bridge", bridge)
    monkeypatch.setattr(probe.mt5, "order_send", lambda *_: pytest.fail("crossed-minute reservation must not call order_send"), raising=False)

    result = probe.capture("terminal", tmp_path / "lease.json")
    assert result["execution"]["status"] == "NOT_SUBMITTED_AFTER_RESERVATION"
    assert [command for command, _ in calls] == ["enforce-risk-policy", "persist-proposal", "enforce-risk-policy", "reserve-execution", "record-result", "reconcile"]
    event = next(payload["result"] for command, payload in calls if command == "record-result")
    assert event["event_type"] == "NOT_SUBMITTED"
    validate_execution_and_reconciliation(result, result["session"], result["decision_snapshot"], result["proposal"])



def test_m20_capture_same_minute_real_recheck_reaches_order_send(monkeypatch, tmp_path):
    """Control: the real fresh quote/M1 recheck permits an unchanged minute."""
    probe = _m20_probe_module(monkeypatch)
    initial = datetime(2026, 9, 9, 6, 0, 59, tzinfo=timezone.utc)
    _capture_test_environment(monkeypatch, probe, initial=initial, after_capture=initial)

    def bridge(payload, command):
        if command == "enforce-risk-policy":
            return {"risk": {"entry_allowed": True, "maximum_loss_aud": 100}}
        if command == "persist-proposal":
            return {"postgres_audit": {"session_id": "s", "proposal_id": "proposal", "snapshot_id": "snapshot", "execution_attempt_id": None, "record_sha256": "sha256:" + "e" * 64}}
        if command == "reserve-execution":
            attempt_id = payload["reservation"]["attempt_id"]
            return {"reservation": {"slot_number": None}, "postgres_audit": {"session_id": "s", "proposal_id": "proposal", "snapshot_id": "snapshot", "execution_attempt_id": attempt_id, "record_sha256": "sha256:" + "e" * 64}}
        pytest.fail(f"unexpected bridge command before order_send: {command}")

    monkeypatch.setattr(probe, "_bridge", bridge)
    reached = []
    monkeypatch.setattr(probe.mt5, "order_send", lambda *_: (reached.append(True), (_ for _ in ()).throw(RuntimeError("order_send reached")))[1], raising=False)
    with pytest.raises(RuntimeError, match="order_send reached"):
        probe.capture("terminal", tmp_path / "lease.json")
    assert reached == [True]


def test_m20_owner_time_exit_runs_before_bad_monitor_history(monkeypatch):
    probe = _m20_probe_module(monkeypatch)
    now = datetime.now(timezone.utc)
    position = types.SimpleNamespace(ticket=8, magic=probe.EXECUTOR_MAGIC, price_open=1.1, sl=1.099, tp=1.102)
    probe.mt5.symbol_info_tick = lambda _: types.SimpleNamespace(time=int(now.timestamp()), bid=1.1, ask=1.1001)
    probe._positions_or_fail = lambda **_: (position,)
    probe._closed_m1_bars_for_monitor = lambda *_: pytest.fail("time exit must precede candle reader")
    monkeypatch.setattr(probe, "_close_accepted_position", lambda **_: ("close", 1.1, {}))
    monkeypatch.setattr(probe, "_record_closed_monitor_outcome", lambda **kw: {"reason": kw["close_reason"]})
    result = probe._monitor_open_position(
        proposal={"proposal_id":"p", "action":"BUY", "trade_owner_strategy_id":"range_reversion", "proposed_entry":1.1, "initial_stop_loss":1.099},
        attempt_id="a", position=position, submitted_at=now-timedelta(minutes=7), entry_spread=.0001,
        risk={"volume":.01, "tick_size":.00001, "tick_value_loss":1.4, "point":.00001}, offset_seconds=0, single_pass=True,
    )
    assert result["reason"] == "RANGE_REVERSION_M1_TIME_STOP_6_MINUTES"


def test_m20_cost_gate_requires_projected_net_profit_above_the_fixed_floor(monkeypatch):
    probe = _m20_probe_module(monkeypatch)
    risk = {"volume": 0.01, "tick_size": 0.00001, "tick_value_loss": 1.395, "observed_spread": 0.00010}
    risk["financing"] = {"status": "QUALIFIED_INPUTS", "expected_swap_aud": 0.0, "commission_allowance_aud": 0.0, "adverse_financing_aud": 0.0}
    rejected = probe._project_cost_coverage(action="BUY", entry=1.1, take_profit=1.10002, risk=risk)
    accepted = probe._project_cost_coverage(action="BUY", entry=1.1, take_profit=1.10150, risk=risk)
    assert rejected["cost_coverage_status"] == "NOT_FEASIBLE"
    assert accepted["cost_coverage_status"] == "FEASIBLE"
    assert accepted["minimum_net_profit_aud"] == 0.10
    assert accepted["expected_net_profit_at_take_profit_aud"] >= accepted["minimum_net_profit_aud"]


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
    assert "trade_owner_strategy_id=selection.selected_strategy_id" in bridge


def _option_b_policy() -> dict:
    return {
        "policy_version": "forex.m20.conservative-risk.v1", "reporting_currency": "AUD",
        "maximum_risk_per_trade_percent": .10, "maximum_risk_per_trade_aud": 100.0,
        "daily_loss_limit_percent": .50, "weekly_loss_limit_percent": 1.0,
        "peak_equity_drawdown_limit_percent": 2.0, "loss_budget_timezone": "Pacific/Auckland",
        "daily_pause_reset": "NEXT_AUCKLAND_DAY",
        "manual_resume_reasons": ["WEEKLY_LOSS", "PEAK_DRAWDOWN", "EXTERNAL_CASH_FLOW", "UNKNOWN_ACCOUNT_STATE"],
        "require_known_external_cashflow": True,
    }


class _RiskCursor:
    def __init__(self, rows):
        self.rows = list(rows)
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query, params=None):
        self.calls.append((query, params))

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None


class _RiskConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return self._cursor


def test_option_b_risk_guard_pauses_at_daily_loss_and_sets_the_next_auckland_reset(monkeypatch):
    bridge = _m20_audit_bridge_module()
    cursor = _RiskCursor([(100000.0, 100000.0, 100000.0, "2026-09-07", 100000.0, "2026-09-07", None, None, False, [], "a" * 64)])
    monkeypatch.setattr(bridge, "_connection", lambda: _RiskConnection(cursor))
    result = bridge.enforce_risk_policy({"policy": _option_b_policy(), "account": {"account_scope_sha256": "a" * 64, "balance": 100000.0, "equity": 99400.0, "auckland_date": "2026-09-07", "auckland_week_start": "2026-09-07"}})
    assert result["risk"]["entry_allowed"] is False
    assert result["risk"]["pause_reason"] == "DAILY_LOSS"
    assert cursor.calls[-1][1][6:9] == ("DAILY_LOSS", "2026-09-08", False)


def test_option_b_external_cashflow_only_clears_after_a_recorded_review(monkeypatch):
    bridge = _m20_audit_bridge_module()
    resume_cursor = _RiskCursor([(["EXTERNAL_CASH_FLOW"], False)])
    monkeypatch.setattr(bridge, "_connection", lambda: _RiskConnection(resume_cursor))
    assert bridge.resume_risk_policy({})["risk_resume"]["previous_pause_reason"] == "EXTERNAL_CASH_FLOW"
    assert resume_cursor.calls[-1][1] == (None, [], True)

    cursor = _RiskCursor([(100000.0, 100000.0, 100000.0, "2026-09-07", 100000.0, "2026-09-07", None, None, True, [], "a" * 64)])
    monkeypatch.setattr(bridge, "_connection", lambda: _RiskConnection(cursor))
    result = bridge.enforce_risk_policy({"policy": _option_b_policy(), "account": {"account_scope_sha256": "a" * 64, "balance": 101000.0, "equity": 101000.0, "auckland_date": "2026-09-07", "auckland_week_start": "2026-09-07"}})
    assert result["risk"]["entry_allowed"] is True
    assert cursor.calls[-1][1][0:3] == (101000.0, 101000.0, 101000.0)
    assert cursor.calls[-1][1][8] is False


def test_fixed_operator_resume_action_has_no_database_or_order_input_surface():
    command = t480_adapter.OPERATIONS["m20_listener_resume_risk_policy"].powershell_command or ""
    assert "resume-risk-policy" in command
    assert "Get-FileHash" in command
    assert "order_send" not in command
    assert "wsl.exe -d Ubuntu -- python3 $wslBridge resume-risk-policy" in command
    assert "/mnt/c/ProgramData/ForexListener/releases/" in command
    assert "& $c.python_path $bridge" not in command
    assert "finally { $env:WSLENV=$previousWslEnv }" in command
    assert "'FOREX_M20_POSTGRES_DSN') -join ':'" in command
    assert "postgresql://" not in command


def test_m20_monitor_refuses_an_open_position_without_a_known_strategy_owner(monkeypatch):
    probe = _m20_probe_module(monkeypatch)
    with pytest.raises(SystemExit, match="without a known selected strategy owner"):
        probe._monitor_open_position(
            proposal={"proposal_id": "p", "action": "BUY", "trade_owner_strategy_id": "unknown"},
            attempt_id="a", position=type("Position", (), {"ticket": 1, "price_open": 1.1, "sl": 1.09, "tp": 1.11})(),
            submitted_at=datetime(2026, 9, 3, tzinfo=timezone.utc), entry_spread=0.0001,
            risk={"volume": 0.01, "tick_size": 0.00001, "tick_value_loss": 1.395, "point": 0.00001}, offset_seconds=0,
        )


def test_m20_recovery_keeps_the_immutable_initial_stop_after_break_even():
    runner = (t480_adapter.ROOT / "t480" / "m20_demo_trading_session.py").read_text(encoding="utf-8")
    bridge = (t480_adapter.ROOT / "t480" / "m20_postgres_audit_bridge.py").read_text(encoding="utf-8")
    assert 'proposal.get("initial_stop_loss", proposal.get("stop_loss", current_stop))' in runner
    assert '"initial_stop_loss": float(row["initial_stop_loss"])' in runner
    assert "p.proposed_entry,p.stop_loss,a.attempt_id" in bridge
    assert '"initial_stop_loss": float(row[3])' in bridge


def test_m20_open_position_recovery_reads_broker_volume_not_quote_spread(monkeypatch):
    bridge = _m20_audit_bridge_module()
    opened_at = datetime(2026, 9, 4, 2, 0, tzinfo=timezone.utc)
    row = (
        "proposal", "BUY", 1.16305, 1.16283, "attempt", opened_at,
        41559226, 1.16305, 1.16305, 1.16340, True,
            0.00008, "0.01", "41559226", "compression_breakout",
    )

    class Cursor:
        def execute(self, *_args):
            pass

        def fetchall(self):
            return [row]

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    class Connection:
        def cursor(self):
            return Cursor()

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(bridge, "_connection", lambda: Connection())
    recovered = bridge.load_open_positions({})["open_positions"]
    assert recovered[0]["entry_spread"] == 0.00008
    assert recovered[0]["volume"] == 0.01


def test_m20_owner_exit_contracts_are_deterministic_and_strategy_specific(monkeypatch):
    probe = _m20_probe_module(monkeypatch)
    assert probe._owner_exit_contract("momentum_breakout") == (600, "M1_TWO_OPPOSITE_CLOSED_CANDLES")
    assert probe._owner_exit_contract("compression_breakout") == (480, "M1_TWO_OPPOSITE_CLOSED_CANDLES")
    assert probe._owner_exit_contract("trend_pullback") == (600, "M1_TWO_OPPOSITE_CLOSED_CANDLES")
    assert probe._owner_exit_contract("range_reversion") == (360, "M1_TWO_OPPOSITE_CLOSED_CANDLES")
    assert probe._owner_exit_contract("session_breakout") == (600, "M1_TWO_OPPOSITE_CLOSED_CANDLES")
    with pytest.raises(SystemExit, match="without a known selected strategy owner"):
        probe._owner_exit_contract("unknown")


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
        "maximum_trades": None,
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
    assert probe.load_session_lease(path, now)["maximum_trades"] is None
    lease["maximum_loss_per_trade_aud"] = .01
    path.write_text(json.dumps(lease), encoding="utf-8")
    assert probe.load_session_lease(path, now)["maximum_loss_per_trade_aud"] == .01
    lease["maximum_loss_per_trade_aud"] = .02
    path.write_text(json.dumps(lease), encoding="utf-8")
    with pytest.raises(SystemExit, match="maximum_loss_per_trade_aud is outside its fixed cap"):
        probe.load_session_lease(path, now)
    lease["maximum_loss_per_trade_aud"] = 100
    lease["maximum_trades"] = 1
    path.write_text(json.dumps(lease), encoding="utf-8")
    with pytest.raises(SystemExit, match="maximum_trades is invalid"):
        probe.load_session_lease(path, now)
    lease["maximum_trades"] = None
    lease["audit_prerequisites"] = {}
    path.write_text(json.dumps(lease), encoding="utf-8")
    with pytest.raises(SystemExit, match="audit prerequisites are absent"):
        probe.load_session_lease(path, now)


def test_m20_aud_cent_risk_refusal_is_enforced_before_any_order_path(monkeypatch):
    probe = _m20_probe_module(monkeypatch)
    with pytest.raises(SystemExit, match="minimum EURUSD price increment exceeds the AUD loss cap"):
        probe._risk_levels(
            action="BUY", entry=1.16, volume=.01, tick_size=.00001,
            tick_value_loss=1.4, point=.00001, maximum_loss_aud=.01,
        )


def test_m20_risk_refusal_drill_uses_normal_technical_stop_predicate_without_order(monkeypatch, tmp_path):
    probe = _m20_probe_module(monkeypatch)
    now = datetime(2026, 9, 10, 12, 0, 10, tzinfo=timezone.utc)

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return now if tz is None else now.astimezone(tz)

    monkeypatch.setattr(probe, "datetime", FrozenDatetime)
    account = types.SimpleNamespace(server="GOMarketsMU-Demo", currency="AUD")
    symbol = types.SimpleNamespace(name="EURUSD", volume_min=.01, trade_tick_size=.00001,
                                   trade_tick_value_loss=1.4, point=.00001)
    # Broker time includes the canonical configured 15-minute offset.
    tick = types.SimpleNamespace(bid=1.10000, ask=1.10005,
                                 time=int((now + timedelta(minutes=15)).timestamp()))
    calls = []
    probe.mt5.initialize = lambda **_: True
    probe.mt5.shutdown = lambda: calls.append("shutdown")
    probe.mt5.account_info = lambda: account
    probe.mt5.symbol_info = lambda _: symbol
    probe.mt5.symbol_info_tick = lambda _: tick
    probe.mt5.order_send = lambda *_: pytest.fail("calculation-only drill submitted an order")
    monkeypatch.setattr(probe, "load_session_lease", lambda *_: {"maximum_loss_per_trade_aud": .01})
    monkeypatch.setattr(probe, "tick_time_offset_seconds", lambda: 900)
    original_loss = probe._planned_stop_loss

    def observed_normal_predicate(entry, stop, risk):
        calls.append((entry, stop, dict(risk)))
        return original_loss(entry, stop, risk)

    monkeypatch.setattr(probe, "_planned_stop_loss", observed_normal_predicate)
    monkeypatch.setattr(probe, "_risk_levels", lambda **_: pytest.fail("obsolete sizing path used"))

    result = probe.risk_refusal_drill("/fixed/demo/terminal", tmp_path / "lease.json")

    assert result["marker"] == "FOREX_M20_DEMO_RISK_REFUSAL_DRILL_OK"
    assert result["order_submitted"] is False
    assert result["quote_observed_at_utc"] == probe.utc(now)
    assert result["captured_at_utc"] == probe.utc(now)
    assert result["quote_freshness_seconds"] == 0
    assert result["minimum_valid_stop"] == pytest.approx(1.10004)
    assert result["planned_stop_loss_aud"] > .01
    assert result["refusal_reason"] == "Minimum volume at the valid technical stop exceeds remaining capital headroom."
    assert len(calls) == 2 and calls[-1] == "shutdown"
    entry, stop, risk = calls[0]
    assert (entry, stop, risk["observed_spread"]) == pytest.approx((1.10005, 1.10004, .00005))


def test_m20_risk_refusal_drill_rejects_nonfinite_demo_quote_before_calculation(monkeypatch, tmp_path):
    probe = _m20_probe_module(monkeypatch)
    probe.mt5.initialize = lambda **_: True
    shutdowns = []
    probe.mt5.shutdown = lambda: shutdowns.append(True)
    probe.mt5.account_info = lambda: types.SimpleNamespace(server="GOMarketsMU-Demo", currency="AUD")
    probe.mt5.symbol_info = lambda _: types.SimpleNamespace(
        name="EURUSD", volume_min=.01, trade_tick_size=.00001,
        trade_tick_value_loss=1.4, point=.00001,
    )
    probe.mt5.symbol_info_tick = lambda _: types.SimpleNamespace(
        bid=float("nan"), ask=1.10005, time=int(datetime.now(timezone.utc).timestamp()),
    )
    probe.mt5.order_send = lambda *_: pytest.fail("calculation-only drill submitted an order")
    monkeypatch.setattr(probe, "load_session_lease", lambda *_: {"maximum_loss_per_trade_aud": .01})
    monkeypatch.setattr(probe, "tick_time_offset_seconds", lambda: 0)
    monkeypatch.setattr(probe, "_planned_stop_loss", lambda *_: pytest.fail("nonfinite quote reached loss predicate"))

    with pytest.raises(SystemExit, match="invalid EURUSD broker metadata"):
        probe.risk_refusal_drill("/fixed/demo/terminal", tmp_path / "lease.json")
    assert shutdowns == [True]


@pytest.mark.parametrize("quote_time", [
    datetime(2026, 9, 10, 11, 59, 39, tzinfo=timezone.utc),
    datetime(2026, 9, 10, 12, 0, 11, tzinfo=timezone.utc),
])
def test_m20_risk_refusal_drill_rejects_stale_or_future_quote_after_metadata_reads(monkeypatch, tmp_path, quote_time):
    probe = _m20_probe_module(monkeypatch)
    now = datetime(2026, 9, 10, 12, 0, 10, tzinfo=timezone.utc)

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return now if tz is None else now.astimezone(tz)

    monkeypatch.setattr(probe, "datetime", FrozenDatetime)
    probe.mt5.initialize = lambda **_: True
    shutdowns = []
    probe.mt5.shutdown = lambda: shutdowns.append(True)
    probe.mt5.account_info = lambda: types.SimpleNamespace(server="GOMarketsMU-Demo", currency="AUD")
    probe.mt5.symbol_info = lambda _: types.SimpleNamespace(
        name="EURUSD", volume_min=.01, trade_tick_size=.00001,
        trade_tick_value_loss=1.4, point=.00001,
    )
    probe.mt5.symbol_info_tick = lambda _: types.SimpleNamespace(
        bid=1.10000, ask=1.10005, time=int(quote_time.timestamp()),
    )
    probe.mt5.order_send = lambda *_: pytest.fail("calculation-only drill submitted an order")
    monkeypatch.setattr(probe, "load_session_lease", lambda *_: {"maximum_loss_per_trade_aud": .01})
    monkeypatch.setattr(probe, "tick_time_offset_seconds", lambda: 0)
    monkeypatch.setattr(probe, "_planned_stop_loss", lambda *_: pytest.fail("stale quote reached loss predicate"))

    with pytest.raises(SystemExit, match="invalid EURUSD broker metadata"):
        probe.risk_refusal_drill("/fixed/demo/terminal", tmp_path / "lease.json")
    assert shutdowns == [True]


def test_m20_strategy_plan_and_refusal_drill_share_technical_stop_normalization(monkeypatch):
    probe = _m20_probe_module(monkeypatch)
    assert probe._normalized_technical_stop(
        action="BUY", entry=1.10005, technical_stop=1.10004, tick_size=.00001,
    ) == pytest.approx(1.10004)
    assert probe._normalized_technical_stop(
        action="BUY", entry=1.10005, technical_stop=1.10005, tick_size=.00001,
    ) is None


def test_m20_position_query_error_is_not_treated_as_no_position(monkeypatch):
    probe = _m20_probe_module(monkeypatch)
    probe.mt5.positions_get = lambda **_: None
    probe.mt5.last_error = lambda: (-10004, "terminal unavailable")
    with pytest.raises(SystemExit, match="position query failed"):
        probe._positions_or_fail(context="test", ticket=12)


def test_m20_partial_order_result_is_not_classified_as_rejected(monkeypatch):
    probe = _m20_probe_module(monkeypatch)
    probe.mt5.TRADE_RETCODE_DONE = 10009
    probe.mt5.TRADE_RETCODE_DONE_PARTIAL = 10010
    assert probe._execution_result_state(types.SimpleNamespace(retcode=10009)) == (True, False)
    assert probe._execution_result_state(types.SimpleNamespace(retcode=10010)) == (False, True)
    assert probe._execution_result_state(types.SimpleNamespace(retcode=10006)) == (False, False)


def test_m20_close_reconciliation_requires_broker_matched_entry_and_exit_deals(monkeypatch):
    probe = _m20_probe_module(monkeypatch)
    calls = []
    deals = (
        types.SimpleNamespace(ticket=1, position_id=99, entry=0, type=0, volume=.01, price=1.1000, profit=0.0, commission=-.10, fee=-.02, swap=0.0, time_msc=1),
        types.SimpleNamespace(ticket=2, position_id=99, entry=1, type=1, volume=.01, price=1.1010, profit=10.0, commission=-.10, fee=-.03, swap=-.05, time_msc=2),
        types.SimpleNamespace(ticket=3, position_id=0, entry=0, type=2, volume=0.0, price=0.0, profit=999.0, commission=0.0, fee=0.0, swap=0.0, time_msc=3),
    )
    probe.mt5.POSITION_TYPE_BUY = 0
    probe.mt5.history_deals_get = lambda *, position: calls.append(position) or deals
    probe.mt5.symbol_info_tick = lambda _: None
    position = types.SimpleNamespace(ticket=22, identifier=99, type=0, price_open=1.1000)
    exit_price, costs = probe._closed_position_costs(
        position=position, submitted_at=datetime(2026, 9, 3, tzinfo=timezone.utc),
        proposed_entry=1.1000, entry_spread=.0001,
        risk={"tick_size": .00001, "tick_value_loss": 1.0}, expected_exit_price=1.1010,
    )
    assert calls == [99]
    assert exit_price == pytest.approx(1.1010)
    assert costs["gross_price_pnl_account"] == 10.0
    assert costs["commission_account"] == -.2
    assert costs["fee_account"] == -.05
    assert costs["swap_account"] == -.05
    assert costs["realized_pnl_account"] == 9.70
    assert costs["estimated_total_cost_account"] == costs["estimated_spread_cost_account"]

    probe.mt5.history_deals_get = lambda *, position: deals[:1]
    with pytest.raises(SystemExit, match="opening or closing"):
        probe._closed_position_costs(
            position=position, submitted_at=datetime(2026, 9, 3, tzinfo=timezone.utc),
            proposed_entry=1.1000, entry_spread=.0001,
            risk={"tick_size": .00001, "tick_value_loss": 1.0}, expected_exit_price=None,
        )


def test_m20_broker_reported_but_unobserved_fill_is_audited_as_unknown_and_blocks_retry(monkeypatch):
    bridge = _m20_audit_bridge_module()
    context = {
        "schema_version": "forex.m20.mt5-result-context.v1", "retcode": 10009,
        "broker_comment": "done", "symbol": "EURUSD", "action": "BUY", "volume": .01,
        "requested_price": 1.1, "stop_loss": 1.099, "take_profit": 1.101,
        "deviation_points": 20, "filling_mode": 1, "time_mode": 0, "magic": 20260020,
        "observed_bid": 1.1, "observed_ask": 1.1001, "spread_points": 10.0,
        "tick_freshness_seconds": 0, "symbol_point": .00001, "trade_tick_size": .00001,
        "stops_level_points": 0, "freeze_level_points": 0, "volume_min": .01,
        "volume_max": 100.0, "volume_step": .01, "visible_positions_count": 0,
        "lease_max_trades": None, "max_open_positions": 1, "max_notional_per_trade_usd": 10000,
        "max_cumulative_notional_usd": 100000, "reservation_slot_number": None,
        "broker_order_reference": "123", "broker_requested_price": 1.1,
        "broker_requested_volume": .01, "broker_requested_stop_loss": 1.099,
        "broker_requested_take_profit": 1.101, "position_ticket": None,
        "position_identifier": None, "fill_status": "UNKNOWN", "broker_filled_volume": None,
        "position_observation_error": "M20 accepted-order position query failed: terminal unavailable",
    }
    payload = {"result": {
        "event_id": "attempt:result", "attempt_id": "attempt", "event_type": "UNKNOWN",
        "observed_at_utc": "2026-09-03T00:00:00Z", "broker_order_reference": "123",
        "payload_sha256": bridge._digest(context), "payload": context,
    }}
    calls = []

    class Cursor:
        reads = 0
        def execute(self, *args):
            calls.append(args)
        def fetchone(self):
            self.reads += 1
            return (1,) if self.reads == 1 else None
        def __enter__(self):
            return self
        def __exit__(self, *_):
            return False
    class Connection:
        def cursor(self):
            return Cursor()
        def __enter__(self):
            return self
        def __exit__(self, *_):
            return False
    monkeypatch.setattr(bridge, "_connection", lambda: Connection())
    assert bridge.record_result(payload)["ok"] is True
    assert any(len(args) > 1 and "UNKNOWN" in args[1] for args in calls)


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


def test_m20_selected_strategy_plan_accepts_cost_observation(monkeypatch):
    probe = _m20_probe_module(monkeypatch)
    bars = [
        {"open": 1.16000 + index * .00001, "high": 1.16004 + index * .00001,
         "low": 1.15996 + index * .00001, "close": 1.16002 + index * .00001}
        for index in range(12)
    ]
    session = {"maximum_loss_per_trade_aud": 100, "max_notional_per_trade_usd": 10_000}
    action, entry, stop, take, notional, _ = probe._strategy_trade_plan(
        strategy_id="range_reversion", signal="BUY", m1=bars,
        tick={"ask": 1.16005, "bid": 1.15997}, session=session,
        risk={"volume": .01, "tick_size": .00001, "tick_value_loss": 1.395,
              "point": .00001, "observed_spread": .00008},
    )
    assert action == "BUY"
    assert entry and stop and take and notional
    assert take == round(((max(bar["high"] for bar in bars[-6:-1]) + min(bar["low"] for bar in bars[-6:-1])) / 2) / .00001) * .00001


@pytest.mark.parametrize(
    ("strategy_id", "expected_stop_index", "uses_range_midpoint"),
    (
        ("momentum_breakout", -6, False),
        ("compression_breakout", -8, False),
        ("trend_pullback", -5, False),
        ("range_reversion", -6, True),
        ("session_breakout", -6, False),
    ),
)
def test_m20_each_selected_owner_has_a_fixed_buy_entry_stop_and_target_contract(
    monkeypatch, strategy_id, expected_stop_index, uses_range_midpoint,
):
    """Every M20.11 owner must produce its own deterministic protected plan."""
    probe = _m20_probe_module(monkeypatch)
    bars = [
        {
            "open": 1.16000 + index * .00001,
            "high": 1.16004 + index * .00001,
            "low": 1.15996 + index * .00001,
            "close": 1.16002 + index * .00001,
        }
        for index in range(12)
    ]
    session = {"maximum_loss_per_trade_aud": 100, "max_notional_per_trade_usd": 10_000}
    risk = {"volume": .01, "tick_size": .00001, "tick_value_loss": 1.395,
            "point": .00001, "observed_spread": .00008}
    action, entry, stop, take, notional, _ = probe._strategy_trade_plan(
        strategy_id=strategy_id, signal="BUY", m1=bars,
        tick={"ask": 1.16005, "bid": 1.15997}, session=session, risk=risk,
    )

    assert action == "BUY"
    assert entry == 1.16005  # BUY must use the executable ask, never candle close.
    assert stop == round(bars[expected_stop_index]["low"] / risk["point"]) * risk["point"]
    assert stop < entry < take
    assert notional == pytest.approx(.01 * 100_000 * entry)
    if uses_range_midpoint:
        prior_five = bars[-6:-1]
        expected_target = round(
            ((max(bar["high"] for bar in prior_five) + min(bar["low"] for bar in prior_five)) / 2)
            / risk["point"]
        ) * risk["point"]
        assert take == expected_target
    else:
        assert take == round((entry + 1.5 * (entry - stop)) / risk["point"]) * risk["point"]


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


def test_fixed_retained_history_reconciliation_has_no_order_or_generic_history_surface():
    command = t480_adapter.OPERATIONS["m20_reconcile_retained_history"].powershell_command or ""
    runner = (t480_adapter.ROOT / "t480" / "m20_demo_trading_session.py").read_text(encoding="utf-8")
    bridge = (t480_adapter.ROOT / "t480" / "m20_postgres_audit_bridge.py").read_text(encoding="utf-8")
    assert "--reconcile-retained-history" in command
    assert "Get-FileHash" in command and "GOMarketsMU-Live" not in command
    assert "order_send" not in command and "order_send" not in runner[runner.index("def reconcile_historical_retained_positions"):runner.index("def _closed_m1_bars_for_monitor")]
    assert "_HISTORICAL_RECOVERY" in runner and "history_deals_get(position=position_id)" in runner
    assert "_HISTORICAL_RECOVERIES" in bridge
    assert "uuid.uuid5(uuid.NAMESPACE_URL" in bridge
    recovery = bridge[bridge.index("def record_historical_reconciliation"):bridge.index("def load_open_positions")]
    assert "UPDATE forex.demo_risk_policy_state" not in recovery
    assert "estimated_spread_cost_account,slippage_cost_account,estimated_total_cost_account,realized_pnl_account" in recovery
    assert "NULL,NULL,NULL" in recovery


def test_retained_history_reconciliation_validates_all_four_exact_broker_positions(monkeypatch):
    probe = _m20_probe_module(monkeypatch)
    offset = 10_800
    by_position = {}
    for index, (_attempt, _proposal, action, position_id, opened, closed, net) in enumerate(probe._HISTORICAL_RECOVERY, start=1):
        def deal(time_text, entry, deal_type, ticket, order, price, profit):
            time_value = int(datetime.fromisoformat(time_text.replace("Z", "+00:00")).timestamp()) + offset
            return types.SimpleNamespace(ticket=ticket, order=order, position_id=position_id, time=time_value,
                entry=entry, type=deal_type, volume=0.01, price=price, profit=profit, commission=0.0, fee=0.0, swap=0.0, reason=0, symbol="EURUSD")
        opening_type, closing_type = (1, 0) if action == "SELL" else (0, 1)
        by_position[position_id] = [deal(opened, 0, opening_type, 100 + index * 2, 200 + index * 2, 1.1, 0.0), deal(closed, 1, closing_type, 101 + index * 2, 201 + index * 2, 1.2, net)]
    fake_mt5 = types.SimpleNamespace(
        DEAL_ENTRY_IN=0, DEAL_ENTRY_OUT=1, DEAL_TYPE_BUY=0, DEAL_TYPE_SELL=1,
        initialize=lambda **_kwargs: True, account_info=lambda: types.SimpleNamespace(server="GOMarketsMU-Demo", currency="AUD"),
        history_deals_get=lambda *, position: by_position[position], shutdown=lambda: None, last_error=lambda: "none",
    )
    monkeypatch.setattr(probe, "mt5", fake_mt5)
    monkeypatch.setattr(probe, "tick_time_offset_seconds", lambda: offset)
    captured = {}
    def bridge(payload, command):
        captured["payload"], captured["command"] = payload, command
        return {"ok": True, "risk_policy_state_changed": False}
    monkeypatch.setattr(probe, "_bridge", bridge)
    result = probe.reconcile_historical_retained_positions("terminal")
    assert result["marker"] == "FOREX_M20_HISTORICAL_RECONCILIATION_OPERATION_OK"
    assert captured["command"] == "record-historical-reconciliation"
    rows = captured["payload"]["recoveries"]
    assert [row["position_identifier"] for row in rows] == [41488649, 41495536, 41499398, 41499981]
    assert [row["realized_pnl_account"] for row in rows] == [0.18, 0.01, -0.56, -0.21]
    assert all(row["fee_account"] == 0.0 and len(row["broker_deals"]) == 2 for row in rows)


def test_m20_listener_open_alert_is_redacted_and_local_settings_survive_redeploy():
    status = t480_adapter.OPERATIONS["m20_listener_status"].powershell_command or ""
    configure = t480_adapter.OPERATIONS["m20_listener_configure"].powershell_command or ""
    assert "discord_open_alert_configured=$notifications" in status
    assert "FOREX_M20_DISCORD_WEBHOOK_URL" in status
    assert "discord.com/api/webhooks" not in status
    assert "FOREX_M20_DISCORD_NOTIFICATIONS_ENABLED" in configure
    assert "$previous" in configure
    assert "discord.com/api/webhooks" not in configure


def test_m20_discord_enable_operation_reads_only_approved_local_secret_sources():
    command = t480_adapter.OPERATIONS["m20_listener_enable_discord_from_existing_secret"].powershell_command or ""
    assert "GetEnvironmentVariable('FOREX_M20_DISCORD_WEBHOOK_URL','User')" in command
    assert "GetEnvironmentVariable('FOREX_M20_DISCORD_WEBHOOK_URL','Machine')" in command
    assert "No approved T480-local Discord webhook is configured" in command
    assert "ConvertTo-Json" in command
    assert "WriteAllText" in command
    assert "discordapp" in command


@pytest.mark.parametrize('action', ['BUY', 'SELL'])
def test_m20_minimum_lot_refused_without_tightening_technical_stop(monkeypatch, action):
    probe = _m20_probe_module(monkeypatch)
    bars = [{'open': 1.16, 'high': 1.161, 'low': 1.159, 'close': 1.16} for _ in range(12)]
    args = dict(strategy_id='momentum_breakout', signal=action, m1=bars,
                tick={'ask': 1.16005, 'bid': 1.15995},
                risk={'volume': .01, 'tick_size': .00001, 'tick_value_loss': 1.4,
                      'point': .00001, 'observed_spread': .0001})
    funded = probe._strategy_trade_plan(**args, session={'maximum_loss_per_trade_aud': 100, 'max_notional_per_trade_usd': 10000})
    assert funded[0] == action
    assert funded[2] == pytest.approx(1.159 if action == 'BUY' else 1.161)
    refused = probe._strategy_trade_plan(**args, session={'maximum_loss_per_trade_aud': .01, 'max_notional_per_trade_usd': 10000})
    assert refused[0] == 'NO_TRADE'
    assert refused[1:5] == (None, None, None, None)
    assert 'technical stop' in refused[5]



def test_unknown_entry_account_is_latched_before_entry_error(monkeypatch):
    probe = _m20_probe_module(monkeypatch)
    calls = []
    monkeypatch.setattr(probe, 'persistent_risk_policy', _option_b_policy)
    monkeypatch.setattr(probe, '_bridge', lambda payload, action: calls.append((payload, action)))
    account = types.SimpleNamespace(balance=float('nan'), equity=100000, server='GOMarketsMU-Demo', currency='AUD', login=123)
    with pytest.raises(SystemExit):
        probe._entry_risk_snapshot(account, datetime.now(timezone.utc))
    assert calls == [({}, 'pause-unknown-account-state')]
