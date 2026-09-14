from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from forex.m1_calendar_decision_overlay import apply_calendar_overlay


def _bridge():
    spec = importlib.util.spec_from_file_location(
        "m20_calendar_overlay_bridge", Path("t480/m20_postgres_audit_bridge.py"),
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _snapshot(overlay: dict) -> tuple[dict, dict]:
    proposal = {"proposal_id": "proposal-1", "snapshot_id": "snapshot-1", "action": "NO_TRADE",
                "decision_snapshot_sha256": "sha256:" + "a" * 64}
    snapshot = {
        "snapshot_id": "snapshot-1", "observed_at_utc": "2026-09-13T00:00:00Z",
        "captured_at_utc": "2026-09-13T00:00:01Z", "bid": 1.1, "ask": 1.1001,
        "spread_points": 1.0, "m1_closed_bars": [], "m5_closed_bars": [],
        "freshness_seconds": 1,
        "safety_gates": {"fresh_quote": True, "completed_m1": True, "normal_spread": True,
                         "no_existing_position": True, "demo_lease_active": True,
                         "news_blackout_inactive": True, "abnormal_volatility_inactive": True},
        "market_context": {}, "strategy_assessments": [], "calendar_overlay": overlay,
        "payload_sha256": proposal["decision_snapshot_sha256"],
    }
    return snapshot, proposal


def test_bridge_rejects_a_rehashed_but_semantically_forged_calendar_overlay():
    bridge = _bridge()
    overlay = apply_calendar_overlay(
        candidate={"proposal_id": "proposal-1", "action": "BUY"},
        gate_observation={"schema_version": "forex.m1-event-risk-gate.v1", "execution_authority": False,
                          "scope": "NEW_ENTRY_ONLY", "state": "FAIL_SAFE_CONTEXT_UNAVAILABLE",
                          "new_entry_permitted": False, "reason": "unavailable"},
    )
    forged = {**overlay, "gate_observation": {**overlay["gate_observation"],
              "state": "FAIL_SAFE_CONTEXT_INVENTED"}}
    forged_body = {key: value for key, value in forged.items() if key != "overlay_sha256"}
    forged["overlay_sha256"] = "sha256:" + hashlib.sha256(
        json.dumps(forged_body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    snapshot, proposal = _snapshot(forged)

    with pytest.raises(SystemExit, match="calendar overlay"):
        bridge._snapshot({"decision_snapshot": snapshot}, proposal)
