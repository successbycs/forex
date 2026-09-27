import hashlib
import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


SOURCE = Path("scripts/verify_m33_final_health_evidence.py")
OLD_REBOOT_BUNDLE = Path("runs/local/m33-health-wave1/20260926T054000Z-postdeploy-coldboot")


def module():
    spec = importlib.util.spec_from_file_location("m33_final_evidence_test", SOURCE)
    assert spec and spec.loader
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def digest(path):
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def rebind(root, name):
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["receipts"]:
        if entry["path"] == name:
            entry["sha256"] = digest(root / name)
    for entry in manifest["soak_observations"]:
        if entry["path"] == name:
            entry["sha256"] = digest(root / name)
    manifest_path.write_text(json.dumps(manifest))


def receipt(identity, **extra):
    return {
        **identity,
        "entry_eligible": False,
        "maintenance_hold": True,
        "broker_mutation": "NONE",
        **extra,
    }


def bundle(tmp_path):
    root = tmp_path / "bundle"
    root.mkdir()
    identity = {
        "configuration_fingerprint": "sha256:" + "a" * 64,
        "listener_release_id": "listener-release",
        "guardian_release_id": "guardian-release",
        "boot_id": "final-boot",
    }
    values = {
        "recovery-before.json": receipt(identity, managed_mt5_count=1, unattributable_mt5_count=0, open_positions=0, pending_orders=0),
        "recovery-action.json": receipt(identity, action="RESTART_LISTENER", request_id="request-1"),
        "recovery-executor.json": receipt(identity, request_id="request-1", state="VERIFIED"),
        "recovery-after.json": receipt(identity, request_id="request-1", monitor_state="IDLE", managed_mt5_count=1, unattributable_mt5_count=0, open_positions=0, pending_orders=0),
        "cold-boot-1-before.json": receipt(identity, observed_boot_id="before-1"),
        "cold-boot-1-after.json": receipt(identity, observed_boot_id="after-1", human_sign_in=False, listener_task_s4u=True, guardian_task_s4u=True, first_cycles_ok=True),
        "cold-boot-2-before.json": receipt(identity, observed_boot_id="before-2"),
        "cold-boot-2-after.json": receipt(identity, observed_boot_id="after-2", human_sign_in=False, listener_task_s4u=True, guardian_task_s4u=True, first_cycles_ok=True),
        "lifecycle-pnl.json": receipt(identity, state="CLOSED_MATCHED", proposal_id="proposal", attempt_id="attempt", position_identifier="position", broker_close_ticket="close", account_currency="AUD", actual_broker_pnl_aud=0.12, postgres_coverage_row_id="coverage"),
    }
    for name, value in values.items():
        (root / name).write_text(json.dumps(value))
    start = datetime(2026, 9, 20, tzinfo=timezone.utc)
    soak = []
    for index in range(97):
        name = f"soak-{index:03}.json"
        (root / name).write_text(json.dumps(receipt(identity, t16_connected=False, monitor_state="IDLE", managed_mt5_count=1, unattributable_mt5_count=0, observed_at_utc=(start + timedelta(minutes=15 * index)).isoformat().replace("+00:00", "Z"))))
        soak.append({"path": name, "sha256": digest(root / name)})
    captured = "2026-09-21T00:00:00Z"
    receipts = [{"path": name, "sha256": digest(root / name), "captured_at_utc": captured, "operation_id": "fixed-operation", "redaction": "no credentials or account numbers"} for name in values]
    (root / "manifest.json").write_text(json.dumps({"schema_version": "forex.m33.final-health-evidence.v1", "final_release": identity, "receipts": receipts, "soak_observations": soak}))
    return root


def test_complete_final_bundle_emits_only_final_marker(tmp_path, capsys):
    verifier = module()
    verifier.verify(bundle(tmp_path))
    assert "FOREX_M33_LOCAL_TRADING_HEALTH_OK" in capsys.readouterr().out


def test_historical_or_partial_lifecycle_is_refused(tmp_path):
    verifier = module()
    root = bundle(tmp_path)
    path = root / "lifecycle-pnl.json"
    value = json.loads(path.read_text())
    value["state"] = "PENDING_NATURAL_TRADE"
    path.write_text(json.dumps(value))
    rebind(root, path.name)
    with pytest.raises(ValueError, match="lifecycle state"):
        verifier.verify(root)


def test_t16_connected_or_short_soak_is_refused(tmp_path):
    verifier = module()
    root = bundle(tmp_path)
    path = root / "soak-001.json"
    value = json.loads(path.read_text())
    value["t16_connected"] = True
    path.write_text(json.dumps(value))
    rebind(root, path.name)
    with pytest.raises(ValueError, match="T16 state"):
        verifier.verify(root)


def test_pre_final_reboot_bundle_cannot_be_reused_as_m33_4_proof():
    verifier = module()
    with pytest.raises(ValueError):
        verifier.verify(OLD_REBOOT_BUNDLE)
