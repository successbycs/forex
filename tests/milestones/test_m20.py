import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
FINGERPRINT = "sha256:" + "a" * 64
M20_EVIDENCE_SURFACE = "continuous cap-constrained automated GOMarketsMU-Demo EUR/USD M1 trading session"


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def operation_payload(now: datetime) -> dict:
    digest = "sha256:" + "b" * 64
    starts = now - timedelta(minutes=1)
    expires = now + timedelta(minutes=59)

    def stamp(value: datetime) -> str:
        return value.isoformat().replace("+00:00", "Z")

    def bars(timeframe: str, minutes: int) -> list[dict]:
        return [
            {
                "timeframe": timeframe,
                "opened_at_utc": stamp(now - timedelta(minutes=minutes * offset)),
                "closed_at_utc": stamp(now - timedelta(minutes=minutes * (offset - 1))),
                "close": 1.1 + offset / 10000,
            }
            for offset in (3, 2)
        ]

    return {
        "schema_version": "forex.m20.demo-trading-operation.v1",
        "marker": "FOREX_M20_DEMO_TRADING_OPERATION_OK",
        "server": "GOMarketsMU-Demo",
        "symbol": "EURUSD",
        "captured_at_utc": stamp(now),
        "configuration_fingerprint": FINGERPRINT,
        "session": {
            "session_id": "demo-session-1",
            "server": "GOMarketsMU-Demo",
            "instrument": "EURUSD",
            "starts_at_utc": stamp(starts),
            "expires_at_utc": stamp(expires),
            "max_trades": 10,
            "max_notional_per_trade_usd": 100,
            "max_cumulative_notional_usd": 1000,
            "max_open_positions": 1,
            "maximum_loss_per_trade_aud": 100,
            "status": "CLOSED",
        },
        "decision_snapshot": {
            "snapshot_id": "snapshot-1",
            "observed_at_utc": stamp(now),
            "captured_at_utc": stamp(now + timedelta(seconds=2)),
            "bid": 1.1,
            "ask": 1.1002,
            "spread_points": 2,
            "freshness_seconds": 2,
            "safety_gates": {
                "fresh_quote": True, "completed_m1": True, "normal_spread": True,
                "no_existing_position": True, "demo_lease_active": True,
                "news_blackout_inactive": True, "abnormal_volatility_inactive": True,
            },
            "m1_closed_bars": bars("M1", 1),
            "m5_closed_bars": [],
            "payload_sha256": digest,
        },
        "strategy_selection": {
            "proposal_id": "proposal-1", "trade_owner_id": "proposal-1",
            "trade_owner_strategy_id": None, "market_regime": "NO_CLEAR_REGIME",
            "market_regime_reason": "No fixed M1 strategy produced an eligible market signal.",
            "selected_strategy_id": None, "strategy_rule_version": None,
            "selection_status": "NO_SELECTION", "estimated_round_trip_cost_aud": None,
            "minimum_net_profit_aud": None, "expected_net_profit_at_take_profit_aud": None,
            "cost_coverage_status": "NOT_APPLICABLE",
        },
        "strategy_assessments": [
            {"id": "momentum_breakout", "label": "Momentum breakout", "signal": "NO_TRADE", "eligible_for_execution": True, "reason": "No closed-candle breakout."},
            {"id": "compression_breakout", "label": "Compression breakout", "signal": "NO_TRADE", "eligible_for_execution": True, "reason": "No compression signal."},
            {"id": "trend_pullback", "label": "Trend pullback", "signal": "NO_TRADE", "eligible_for_execution": True, "reason": "No pullback signal."},
            {"id": "range_reversion", "label": "Range reversion", "signal": "NO_TRADE", "eligible_for_execution": True, "reason": "No range rejection."},
            {"id": "session_breakout", "label": "Session breakout", "signal": "NO_TRADE", "eligible_for_execution": True, "reason": "No session breakout."},
        ],
        "proposal": {
            "proposal_id": "proposal-1",
            "session_id": "demo-session-1",
            "snapshot_id": "snapshot-1",
            "decision_snapshot_sha256": digest,
            "action": "NO_TRADE",
            "selected_timeframe": "M1",
            "decision_at_utc": stamp(now),
            "expires_at_utc": stamp(now + timedelta(minutes=5)),
            "notional_usd": None,
            "confidence": 100,
            "rationale": "M1 momentum is flat, so no order is sent.",
        },
        "execution": {"status": "NOT_SUBMITTED", "attempt_id": None},
        "reconciliation": {
            "session_id": "demo-session-1",
            "proposal_id": "proposal-1",
            "snapshot_id": "snapshot-1",
            "status": "NO_TRADE_RECONCILED",
        },
        "postgres_audit": {
            "session_id": "demo-session-1",
            "proposal_id": "proposal-1",
            "snapshot_id": "snapshot-1",
            "execution_attempt_id": None,
            "record_sha256": digest,
        },
    }


def fixture(tmp_path: Path) -> tuple[Path, Path]:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    for name in ("verify_m20_demo_evidence.sh", "m20_demo_evidence_contract.py"):
        (scripts / name).write_bytes((REPO_ROOT / "scripts" / name).read_bytes())
    (scripts / "forex_milestones.py").write_text(
        "import json\nprint(json.dumps({'configuration_fingerprint': '" + FINGERPRINT + "'}))\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "M20 test"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "--allow-empty", "-qm", "fixture"], cwd=tmp_path, check=True)
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=tmp_path, text=True).strip()
    bundle = tmp_path / "runs" / "evidence" / "M20" / "fixture"
    bundle.mkdir(parents=True)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    payload = operation_payload(now)
    wrapper = {
        "tool_id": "forex_t480",
        "operation": "m20_demo_trading_session",
        "ok": True,
        "configuration_fingerprint": FINGERPRINT,
        "result": {"ok": True, "exit_code": 0, "stdout": json.dumps(payload)},
    }
    write(bundle / "demo-trading-operation.json", wrapper)
    lifecycle = {
        "session_id": "demo-session-1", "proposal_id": "closed-proposal-1", "attempt_id": "closed-attempt-1",
        "action": "BUY", "submitted_at_utc": now.isoformat().replace("+00:00", "Z"),
        "actual_entry_price": "1.1001", "exit_price": 1.1003, "realized_pnl_account": 0.12,
        "account_currency": "AUD", "reconciliation_status": "MATCHED", "lifecycle": "CLOSED_MATCHED",
        "events": json.dumps(["OPENED", "CLOSED"]),
        "application_revision": revision, "configuration_fingerprint": FINGERPRINT,
        "decision_at_utc": now.isoformat(), "proposal_expires_at_utc": (now + timedelta(minutes=5)).isoformat(),
        "snapshot_captured_at_utc": now.isoformat(), "closed_at_utc": now.isoformat(),
        "snapshot_id": "closed-snapshot-1", "decision_snapshot_sha256": "sha256:" + "b" * 64,
        "snapshot_payload_sha256": "sha256:" + "b" * 64,
        "selected_strategy_id": "momentum_breakout", "trade_owner_strategy_id": "momentum_breakout",
        "gross_price_pnl_account": .2, "commission_account": -.06, "fee_account": -.02, "swap_account": 0,
        "opening_context": {"position_identifier": 99, "broker_filled_volume": .01},
    }
    deals = [
        {"ticket": index + 1, "position_identifier": 99, "time_utc": now.isoformat(),
         "entry": index, "type": index, "symbol": "EURUSD", "volume": .01,
         "price": price, "profit": profit, "commission": -.03, "fee": -.01, "swap": 0}
        for index, (price, profit) in enumerate(((1.1001, 0), (1.1003, .2)))
    ]
    lifecycle["closing_context"] = {"position_identifier": 99, "broker_history": {
        "server": "GOMarketsMU-Demo", "symbol": "EURUSD", "account_currency": "AUD",
        "position_identifier": 99, "broker_deals": deals,
        "broker_deals_sha256": "sha256:" + hashlib.sha256(json.dumps(deals, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
    }}
    write(bundle / "lifecycle-summary.json", {
        "tool_id": "forex_postgres_pgvector_t480", "operation": "forex_m20_lifecycle_summary",
        "result": {"ok": True, "exit_code": 0, "stdout": json.dumps([lifecycle])},
    })
    (tmp_path / "t480").mkdir()
    hashes = {}
    for name in ("m20_demo_listener_service", "m20_demo_trading_session", "m20_postgres_audit_bridge", "m20_discord_trade_notification"):
        data = (REPO_ROOT / "t480" / f"{name}.py").read_bytes()
        (tmp_path / "t480" / f"{name}.py").write_bytes(data)
        hashes[f"{name}.payload"] = "sha256:" + hashlib.sha256(data).hexdigest()
    diagnostics = {
        "captured_at_utc": now.isoformat(), "task_state": "Running", "logon_type": "S4U", "maintenance_hold_present": False,
        "deployment_binding": {"observation": "VALID", "application_revision": revision,
            "configuration_fingerprint": FINGERPRINT, "payload_sha256": hashes,
            "lease": {"session_id": "demo-session-1", "server": "GOMarketsMU-Demo", "symbol": "EURUSD",
                "maximum_trades": None, "maximum_duration_minutes": 0, "maximum_open_positions": 1,
                "maximum_notional_per_trade_usd": 10000, "maximum_cumulative_notional_usd": 100000, "maximum_loss_per_trade_aud": 100}},
    }
    for name, operation, value in (("listener-diagnostics.json", "m20_listener_diagnostics", diagnostics),
            ("listener-status.json", "m20_listener_status", {"running": True, "state": "RUNNING", "monitor": {"state": "IDLE"}, "heartbeat_at_utc": now.isoformat()})):
        write(bundle / name, {"tool_id": "forex_t480", "operation": operation, "ok": True,
            "configuration_fingerprint": FINGERPRINT, "result": {"ok": True, "exit_code": 0, "stdout": json.dumps(value)}})
    (bundle / "tests.txt").write_text("4 passed\n", encoding="utf-8")
    (bundle / "governance.txt").write_text("milestone governance valid\n", encoding="utf-8")
    (bundle / "repository-verification.txt").write_text("FOREX_REPOSITORY_VERIFICATION_OK\n", encoding="utf-8")
    write(bundle / "configuration.json", {
        "runtime_mode": "DEMO_TRADING",
        "agent_authority_mode": "DEMO_SESSION_BOUNDED",
        "live_trading_enabled": False,
        "permitted_mt5_server": "GOMarketsMU-Demo",
        "configuration_fingerprint": FINGERPRINT,
    })
    (bundle / "revision.txt").write_text(revision + "\n", encoding="utf-8")
    (bundle / "summary.txt").write_text("FOREX_M20_DEMO_TRADING_PROOF_OK\n", encoding="utf-8")
    write(bundle / "session-audit.json", {
        "schema_version": "forex.m20.demo-trading-evidence.v1",
        "operation_marker": payload["marker"],
        "server": payload["server"],
        "symbol": payload["symbol"],
        "captured_at_utc": payload["captured_at_utc"],
        "configuration_fingerprint": FINGERPRINT,
        **{key: payload[key] for key in ("session", "decision_snapshot", "proposal", "execution", "reconciliation", "postgres_audit")},
        "broker_matched_lifecycle": lifecycle,
    })
    artifacts = [
        {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        for path in sorted(bundle.iterdir())
        if path.is_file()
    ]
    write(bundle / "manifest.json", {
        "schema_version": "1.0.0",
        "milestone_id": "M20",
        "captured_at": now.isoformat().replace("+00:00", "Z"),
        "git_revision": revision,
        "dirty_worktree": False,
        "configuration_fingerprint": FINGERPRINT,
        "surface": M20_EVIDENCE_SURFACE,
        "operation": "fixed T480 m20_demo_trading_session operation",
        "expected_result": "fresh Demo EUR/USD data is assessed, recorded, bounded, and reconciled",
        "observed_result": "FOREX_M20_DEMO_TRADING_PROOF_OK",
        "exit_code": 0,
        "redactions": ["No credentials or account identifiers retained."],
        "summary": "FOREX_M20_DEMO_TRADING_PROOF_OK",
        "artifacts": artifacts,
    })
    return tmp_path, bundle


def verify(root: Path, bundle: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(root / "scripts" / "verify_m20_demo_evidence.sh"), str(bundle)],
        cwd=root,
        text=True,
        capture_output=True,
        env={**os.environ, "PYTHONOPTIMIZE": "1"},
    )


def update_artifact_digest(bundle: Path, name: str) -> None:
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for artifact in manifest["artifacts"]:
        if artifact["path"] == name:
            artifact["sha256"] = hashlib.sha256((bundle / name).read_bytes()).hexdigest()
    write(manifest_path, manifest)


def test_m20_demo_evidence_verifier_accepts_a_bound_assessment_with_a_matched_trade_lifecycle(tmp_path: Path):
    root, bundle = fixture(tmp_path)
    result = verify(root, bundle)
    assert result.returncode == 0, result.stderr
    assert "FOREX_M20_DEMO_TRADING_EVIDENCE_VERIFIED" in result.stdout


def test_m20_demo_evidence_surface_matches_active_contract():
    registry = json.loads((REPO_ROOT / "milestone_registry.json").read_text(encoding="utf-8"))
    contract = next(item for item in registry["milestones"] if item["milestone_id"] == "M20")
    assert contract["real_world_proof"]["surface"] == M20_EVIDENCE_SURFACE


def test_m20_demo_evidence_verifier_rejects_a_capture_without_a_matched_trade_lifecycle(tmp_path: Path):
    root, bundle = fixture(tmp_path)
    write(bundle / "lifecycle-summary.json", {
        "tool_id": "forex_postgres_pgvector_t480", "operation": "forex_m20_lifecycle_summary",
        "result": {"ok": True, "exit_code": 0, "stdout": "[]"},
    })
    update_artifact_digest(bundle, "lifecycle-summary.json")
    result = verify(root, bundle)
    assert result.returncode != 0
    assert "no broker-matched OPENED to CLOSED Demo trade" in result.stderr


@pytest.mark.parametrize("field,value", [
    ("application_revision", "0" * 40),
    ("configuration_fingerprint", "sha256:" + "c" * 64),
    ("decision_at_utc", "2020-01-01T00:00:00Z"),
    ("closed_at_utc", "2099-01-01T00:00:00Z"),
    ("snapshot_payload_sha256", "sha256:" + "c" * 64),
    ("commission_account", 0),
    ("fee_account", 0),
    ("realized_pnl_account", .2),
    ("actual_entry_price", "NaN"),
    ("exit_price", float("inf")),
    ("closing_context", {}),
])
def test_m20_verifier_rejects_unbound_or_unattributable_lifecycle(tmp_path: Path, field, value):
    root, bundle = fixture(tmp_path)
    wrapper = json.loads((bundle / "lifecycle-summary.json").read_text())
    rows = json.loads(wrapper["result"]["stdout"])
    rows[0][field] = value
    wrapper["result"]["stdout"] = json.dumps(rows)
    write(bundle / "lifecycle-summary.json", wrapper)
    update_artifact_digest(bundle, "lifecycle-summary.json")
    result = verify(root, bundle)
    assert result.returncode != 0
    assert "M20 evidence verification failed" in result.stderr


@pytest.mark.parametrize("field,value", [("position_identifier", 100), ("ticket", 1), ("volume", .02), ("type", 0), ("profit", 100)])
def test_m20_verifier_recomputes_broker_facts_even_with_matching_hash(tmp_path: Path, field, value):
    root, bundle = fixture(tmp_path)
    wrapper = json.loads((bundle / "lifecycle-summary.json").read_text())
    rows = json.loads(wrapper["result"]["stdout"])
    history = rows[0]["closing_context"]["broker_history"]
    history["broker_deals"][1][field] = value
    history["broker_deals_sha256"] = "sha256:" + hashlib.sha256(json.dumps(history["broker_deals"], sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    wrapper["result"]["stdout"] = json.dumps(rows)
    write(bundle / "lifecycle-summary.json", wrapper)
    update_artifact_digest(bundle, "lifecycle-summary.json")
    assert verify(root, bundle).returncode != 0


@pytest.mark.parametrize("field,value", [("application_revision", "0" * 40), ("configuration_fingerprint", "sha256:" + "c" * 64), ("observation", "UNAVAILABLE"), ("payload_sha256", {})])
def test_m20_verifier_rejects_drifted_listener_deployment(tmp_path: Path, field, value):
    root, bundle = fixture(tmp_path)
    wrapper = json.loads((bundle / "listener-diagnostics.json").read_text())
    diagnostics = json.loads(wrapper["result"]["stdout"])
    diagnostics["deployment_binding"][field] = value
    wrapper["result"]["stdout"] = json.dumps(diagnostics)
    write(bundle / "listener-diagnostics.json", wrapper)
    update_artifact_digest(bundle, "listener-diagnostics.json")
    assert verify(root, bundle).returncode != 0


def test_m20_capture_refuses_to_overwrite_existing_evidence(tmp_path: Path):
    root, bundle = fixture(tmp_path)
    script = root / "scripts" / "capture_m20_demo_evidence.sh"
    script.write_bytes((REPO_ROOT / "scripts" / script.name).read_bytes())
    before = {path.name: path.read_bytes() for path in bundle.iterdir()}
    result = subprocess.run(["bash", str(script), str(bundle)], capture_output=True, text=True)
    assert result.returncode != 0
    assert "File exists" in result.stderr
    assert before == {path.name: path.read_bytes() for path in bundle.iterdir()}


def test_m20_demo_evidence_verifier_rejects_tampering_even_with_python_optimization(tmp_path: Path):
    root, bundle = fixture(tmp_path)
    (bundle / "summary.txt").write_text("tampered\n", encoding="utf-8")
    result = verify(root, bundle)
    assert result.returncode != 0
    assert "artifact digest mismatch" in result.stderr


def test_m20_demo_evidence_verifier_rejects_mismatched_configuration_fingerprint(tmp_path: Path):
    root, bundle = fixture(tmp_path)
    configuration = json.loads((bundle / "configuration.json").read_text(encoding="utf-8"))
    configuration["configuration_fingerprint"] = "sha256:" + "c" * 64
    write(bundle / "configuration.json", configuration)
    update_artifact_digest(bundle, "configuration.json")
    result = verify(root, bundle)
    assert result.returncode != 0
    assert "configuration artifact fingerprint does not match manifest binding" in result.stderr


def test_m20_demo_evidence_verifier_rejects_obsolete_ollama_operation_shape(tmp_path: Path):
    root, bundle = fixture(tmp_path)
    wrapper = json.loads((bundle / "demo-trading-operation.json").read_text(encoding="utf-8"))
    wrapper["operation"] = "forex-m20-ollama-evaluation-probe"
    write(bundle / "demo-trading-operation.json", wrapper)
    update_artifact_digest(bundle, "demo-trading-operation.json")
    result = verify(root, bundle)
    assert result.returncode != 0
    assert "fixed M20 Demo session" in result.stderr
