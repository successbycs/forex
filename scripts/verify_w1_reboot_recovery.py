#!/usr/bin/env python3
"""Offline verifier for a retained T480 held reboot-recovery bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def payload(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(value, dict) and isinstance(value.get("result"), dict):
        value = value["result"]
    if isinstance(value, dict) and isinstance(value.get("stdout"), str):
        value = json.loads(value["stdout"])
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain an object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    raw = args.bundle / "raw"
    required = ("preflight-account.json", "preflight-listener.json", "postboot-account.json", "postboot-listener.json", "reboot-record.json")
    missing = [name for name in required if not (raw / name).is_file()]
    if missing:
        raise SystemExit("missing retained evidence: " + ", ".join(missing))
    before_account = payload(raw / "preflight-account.json")
    after_account = payload(raw / "postboot-account.json")
    before_listener = payload(raw / "preflight-listener.json")
    after_listener = payload(raw / "postboot-listener.json")
    reboot = payload(raw / "reboot-record.json").get("record") or payload(raw / "reboot-record.json")
    checks = {
        "demo_flat_before": before_account.get("server") == "GOMarketsMU-Demo" and before_account.get("open_positions") == 0,
        "demo_flat_after": after_account.get("server") == "GOMarketsMU-Demo" and after_account.get("open_positions") == 0,
        "hold_after": after_listener.get("state") == "MAINTENANCE_HOLD",
        "listener_after": after_listener.get("running") is True and float(after_listener.get("heartbeat_age_seconds", 9999)) < 30,
        "reboot_record": reboot.get("state") == "POSTBOOT_CAPTURED" and reboot.get("broker_mutation") == "NONE",
        "task_recovered": reboot.get("listener_task_state") == "Running" and reboot.get("watchdog_task_state") in {"Ready", "Running"},
        "release_preserved": reboot.get("listener_release_id") == reboot.get("postboot_release_id") == before_listener.get("release_id") == after_listener.get("release_id"),
    }
    hashes = {name: "sha256:" + hashlib.sha256((raw / name).read_bytes()).hexdigest() for name in required}
    result = {"marker": "FOREX_W1_REBOOT_RECOVERY_PROOF_OK", "checks": checks, "raw_sha256": hashes, "ok": all(checks.values())}
    print(json.dumps(result, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
