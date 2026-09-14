from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import types
from pathlib import Path


def _runner(monkeypatch):
    monkeypatch.setitem(sys.modules, "MetaTrader5", types.SimpleNamespace(
        TIMEFRAME_M1=1, TIMEFRAME_M5=5, TIMEFRAME_H1=60,
    ))
    spec = importlib.util.spec_from_file_location(
        "m20_calendar_overlay_runner", Path("t480/m20_demo_trading_session.py"),
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _policy(*, enabled: bool) -> dict:
    return {
        "schema_version": "forex.m1-event-risk-gate-policy.v1", "enabled": enabled,
        "scope": "NEW_ENTRY_ONLY", "required_context_state": "QUALIFIED_CONTEXT_ONLY",
        "blackout_before_seconds": 1800, "blackout_after_seconds": 900,
        "execution_authority": False, "activation_requirement": "test activation",
    }


def _inputs() -> tuple[dict, dict]:
    body = {
        "observed_at_utc": "2026-09-13T00:00:00Z", "captured_at_utc": "2026-09-13T00:00:01Z",
        "bid": 1.1, "ask": 1.1001, "spread_points": 1.0, "freshness_seconds": 1,
        "m1_closed_bars": [], "m5_closed_bars": [], "safety_gates": {},
        "market_context": {}, "strategy_assessments": [], "financing": {}, "holding_review": {},
    }
    digest = "sha256:" + hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    snapshot = {"snapshot_id": "snapshot-1", **body, "payload_sha256": digest}
    proposal = {
        "proposal_id": "proposal-1", "action": "BUY", "proposed_entry": 1.1001,
        "snapshot_id": "snapshot-1",
        "stop_loss": 1.099, "take_profit": 1.101, "notional_usd": 10000.0,
        "confidence": 70, "rationale": "baseline", "decision_snapshot_sha256": digest,
    }
    return snapshot, proposal


def test_disabled_calendar_policy_preserves_candidate_and_binds_observation(monkeypatch):
    runner = _runner(monkeypatch)
    snapshot, proposal = _inputs()
    original = dict(proposal)

    gate, overlay = runner._apply_m1_calendar_overlay(
        snapshot=snapshot, proposal=proposal, policy=_policy(enabled=False),
    )

    assert gate["state"] == "ANNOTATION_ONLY_DISABLED"
    assert overlay["final_action"] == "BUY"
    assert {key: proposal[key] for key in ("action", "proposed_entry", "stop_loss", "take_profit", "notional_usd", "confidence", "rationale")} == {
        key: original[key] for key in ("action", "proposed_entry", "stop_loss", "take_profit", "notional_usd", "confidence", "rationale")
    }
    assert snapshot["calendar_overlay"] == overlay
    assert proposal["snapshot_id"] == snapshot["snapshot_id"]
    assert proposal["decision_snapshot_sha256"] == snapshot["payload_sha256"]
    assert snapshot["payload_sha256"] != original["decision_snapshot_sha256"]


def test_forced_false_calendar_gate_vetoes_before_a_proposal_can_be_reserved(monkeypatch):
    runner = _runner(monkeypatch)
    snapshot, proposal = _inputs()

    gate, overlay = runner._apply_m1_calendar_overlay(
        snapshot=snapshot, proposal=proposal, policy=_policy(enabled=True),
    )

    assert gate["new_entry_permitted"] is False
    assert overlay["final_action"] == "NO_TRADE"
    assert proposal["action"] == "NO_TRADE"
    assert all(proposal[field] is None for field in ("proposed_entry", "stop_loss", "take_profit", "notional_usd"))
    assert proposal["confidence"] == 100
    assert proposal["rationale"].startswith("CALENDAR_NEW_ENTRY_REFUSED:")


def test_calendar_overlay_binds_a_no_trade_already_refused_by_an_existing_gate(monkeypatch):
    runner = _runner(monkeypatch)
    snapshot, proposal = _inputs()
    proposal.update({"action": "NO_TRADE", "proposed_entry": None, "stop_loss": None,
                     "take_profit": None, "notional_usd": None, "confidence": 100,
                     "rationale": "existing position"})

    _, overlay = runner._apply_m1_calendar_overlay(
        snapshot=snapshot, proposal=proposal, policy=_policy(enabled=False),
    )

    assert overlay["candidate"]["action"] == "NO_TRADE"
    assert overlay["final_action"] == proposal["action"] == "NO_TRADE"
