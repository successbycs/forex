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
    assert "m20_demo_listener_service.local.json" not in command
    assert "FOREX_M20_POSTGRES_DSN" not in command
    assert "heartbeat_at_nzst" in command and "next_assessment_at_nzst" in command
    assert "heartbeat_age_seconds" in command
    assert "$supervisorAlive" in command
    assert "quote=$s.quote" in command
    assert "release_id=$s.release_id" in command
    assert "task_action=$taskAction" in command
    assert "$age -ge 30" in command
    assert "state=if ($stale) { 'STALE' }" in command
    assert "Forex-M20-Demo-Listener" in command
    assert "EXPLICIT_RECOVERY_REQUIRED" in command
    assert "Start-ScheduledTask" not in command
    assert "Stop-ScheduledTask" not in command
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
    for required in ("GOMarketsMU-Demo", "EURUSD", "9999-12-31T23:59:59Z", "maximum_duration_minutes=0", "maximum_trades=$null", "maximum_notional_per_trade_usd=10000", "maximum_cumulative_notional_usd=100000", "maximum_loss_per_trade_aud=100"):
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


def test_m20_listener_release_includes_the_fixed_t480_discord_adapter_without_exposing_its_webhook():
    prepare = t480_adapter.OPERATIONS["m20_listener_prepare"].powershell_command or ""
    configure = t480_adapter.OPERATIONS["m20_listener_configure"].powershell_command or ""
    stage = t480_adapter.OPERATIONS["m20_listener_discord_stage_4"].powershell_command or ""
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
    final = t480_adapter.OPERATIONS["m20_listener_stage_15"].powershell_command
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


def test_m20_cost_gate_requires_projected_net_profit_above_the_fixed_floor(monkeypatch):
    probe = _m20_probe_module(monkeypatch)
    risk = {"volume": 0.01, "tick_size": 0.00001, "tick_value_loss": 1.395, "observed_spread": 0.00010}
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
    cursor = _RiskCursor([(100000.0, 100000.0, 100000.0, "2026-09-07", 100000.0, "2026-09-07", None, None, False)])
    monkeypatch.setattr(bridge, "_connection", lambda: _RiskConnection(cursor))
    result = bridge.enforce_risk_policy({"policy": _option_b_policy(), "account": {"balance": 100000.0, "equity": 99400.0, "auckland_date": "2026-09-07", "auckland_week_start": "2026-09-07"}})
    assert result["risk"]["entry_allowed"] is False
    assert result["risk"]["pause_reason"] == "DAILY_LOSS"
    assert cursor.calls[-1][1][6:9] == ("DAILY_LOSS", "2026-09-08", False)


def test_option_b_external_cashflow_only_clears_after_a_recorded_review(monkeypatch):
    bridge = _m20_audit_bridge_module()
    resume_cursor = _RiskCursor([("EXTERNAL_CASH_FLOW",)])
    monkeypatch.setattr(bridge, "_connection", lambda: _RiskConnection(resume_cursor))
    assert bridge.resume_risk_policy({})["risk_resume"]["previous_pause_reason"] == "EXTERNAL_CASH_FLOW"
    assert resume_cursor.calls[-1][1] == (True,)

    cursor = _RiskCursor([(100000.0, 100000.0, 100000.0, "2026-09-07", 100000.0, "2026-09-07", None, None, True)])
    monkeypatch.setattr(bridge, "_connection", lambda: _RiskConnection(cursor))
    result = bridge.enforce_risk_policy({"policy": _option_b_policy(), "account": {"balance": 101000.0, "equity": 101000.0, "auckland_date": "2026-09-07", "auckland_week_start": "2026-09-07"}})
    assert result["risk"]["entry_allowed"] is True
    assert cursor.calls[-1][1][0:3] == (101000.0, 101000.0, 101000.0)
    assert cursor.calls[-1][1][8] is False


def test_fixed_operator_resume_action_has_no_database_or_order_input_surface():
    command = t480_adapter.OPERATIONS["m20_listener_resume_risk_policy"].powershell_command or ""
    assert "resume-risk-policy" in command
    assert "Get-FileHash" in command
    assert "order_send" not in command
    assert "FOREX_M20_POSTGRES_DSN" not in command


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
    lease["maximum_trades"] = 1
    path.write_text(json.dumps(lease), encoding="utf-8")
    with pytest.raises(SystemExit, match="maximum_trades is invalid"):
        probe.load_session_lease(path, now)
    lease["maximum_trades"] = None
    lease["audit_prerequisites"] = {}
    path.write_text(json.dumps(lease), encoding="utf-8")
    with pytest.raises(SystemExit, match="audit prerequisites are absent"):
        probe.load_session_lease(path, now)


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
        def execute(self, *args):
            calls.append(args)
        def fetchone(self):
            return (1,)
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


def test_m20_selected_strategy_plan_keeps_cost_observation_out_of_risk_inputs(monkeypatch):
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
