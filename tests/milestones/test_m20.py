import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess


REPO_ROOT = Path(__file__).resolve().parents[2]
FINGERPRINT = "sha256:" + "a" * 64


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
            "m1_closed_bars": bars("M1", 1),
            "m5_closed_bars": bars("M5", 5),
            "payload_sha256": digest,
        },
        "proposal": {
            "proposal_id": "proposal-1",
            "session_id": "demo-session-1",
            "snapshot_id": "snapshot-1",
            "decision_snapshot_sha256": digest,
            "action": "NO_TRADE",
            "selected_timeframe": "M5",
            "decision_at_utc": stamp(now),
            "expires_at_utc": stamp(now + timedelta(minutes=5)),
            "notional_usd": None,
            "confidence": 100,
            "rationale": "M1 and M5 conflict, so no order is sent.",
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
    (bundle / "tests.txt").write_text("4 passed\n", encoding="utf-8")
    (bundle / "governance.txt").write_text("milestone governance valid\n", encoding="utf-8")
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
        "surface": "bounded automated GOMarketsMU-Demo EUR/USD trading session",
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


def test_m20_demo_evidence_verifier_accepts_a_bound_no_trade_session(tmp_path: Path):
    root, bundle = fixture(tmp_path)
    result = verify(root, bundle)
    assert result.returncode == 0, result.stderr
    assert "FOREX_M20_DEMO_TRADING_EVIDENCE_VERIFIED" in result.stdout


def test_m20_demo_evidence_verifier_rejects_tampering_even_with_python_optimization(tmp_path: Path):
    root, bundle = fixture(tmp_path)
    (bundle / "summary.txt").write_text("tampered\n", encoding="utf-8")
    result = verify(root, bundle)
    assert result.returncode != 0
    assert "artifact digest mismatch" in result.stderr


def test_m20_demo_evidence_verifier_rejects_obsolete_ollama_operation_shape(tmp_path: Path):
    root, bundle = fixture(tmp_path)
    wrapper = json.loads((bundle / "demo-trading-operation.json").read_text(encoding="utf-8"))
    wrapper["operation"] = "forex-m20-ollama-evaluation-probe"
    write(bundle / "demo-trading-operation.json", wrapper)
    update_artifact_digest(bundle, "demo-trading-operation.json")
    result = verify(root, bundle)
    assert result.returncode != 0
    assert "fixed M20 Demo session" in result.stderr
