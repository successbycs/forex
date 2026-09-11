#!/usr/bin/env python3
"""Offline verifier for retained T480 held reboot-recovery evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def envelope(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a governed operation envelope and its JSON object stdout."""
    outer = json.loads(path.read_text(encoding="utf-8"))
    result = outer.get("result") if isinstance(outer, dict) else None
    if not isinstance(result, dict):
        raise ValueError(f"{path.name} has no operation result")
    value: Any = result.get("stdout")
    if not isinstance(value, str):
        raise ValueError(f"{path.name} has no JSON stdout")
    value = json.loads(value)
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} stdout must be an object")
    return result, value


def instant(value: str | None) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def success(result: dict[str, Any]) -> bool:
    return result.get("ok") is True and result.get("exit_code") == 0


def flat_demo(value: dict[str, Any]) -> bool:
    return (
        value.get("ok") is True
        and value.get("server") == "GOMarketsMU-Demo"
        and value.get("currency") == "AUD"
        and value.get("position_observation") == "AVAILABLE"
        and value.get("open_positions") == 0
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    raw = args.bundle / "raw"
    required = (
        "preflight-account.json", "preflight-listener.json", "preflight-watchdog.json",
        "postboot-host.json", "postboot-account.json", "postboot-listener.json",
        "postboot-watchdog.json", "reboot-record.json", "postboot-diagnostics.json",
    )
    missing = [name for name in required if not (raw / name).is_file()]
    if missing:
        raise SystemExit("missing retained evidence: " + ", ".join(missing))

    before_account_result, before_account = envelope(raw / "preflight-account.json")
    before_listener_result, before_listener = envelope(raw / "preflight-listener.json")
    before_watchdog_result, before_watchdog = envelope(raw / "preflight-watchdog.json")
    host_result, host = envelope(raw / "postboot-host.json")
    after_account_result, after_account = envelope(raw / "postboot-account.json")
    after_listener_result, after_listener = envelope(raw / "postboot-listener.json")
    after_watchdog_result, after_watchdog = envelope(raw / "postboot-watchdog.json")
    record_result, record_payload = envelope(raw / "reboot-record.json")
    diagnostics_result, diagnostics = envelope(raw / "postboot-diagnostics.json")
    reboot = record_payload.get("record") if isinstance(record_payload.get("record"), dict) else {}

    booted_at = instant(host.get("uptime_since_utc"))
    preflight_finished = instant(before_listener_result.get("finished_at"))
    postboot_started = instant(host_result.get("started_at"))
    watchdog_after_run = instant(after_watchdog.get("last_run_utc"))
    listener_sessions = [item.get("SessionId") for item in diagnostics.get("processes", []) if isinstance(item, dict)]
    checks = {
        "successful_operation_envelopes": all(success(item) for item in (
            before_account_result, before_listener_result, before_watchdog_result, host_result,
            after_account_result, after_listener_result, after_watchdog_result, record_result,
            diagnostics_result,
        )),
        "demo_flat_before": flat_demo(before_account),
        "demo_flat_after": flat_demo(after_account),
        "maintenance_hold_before_and_after": (
            before_listener.get("state") == "MAINTENANCE_HOLD"
            and after_listener.get("state") == "MAINTENANCE_HOLD"
        ),
        "host_reboot_chronology": (
            booted_at is not None and preflight_finished is not None and postboot_started is not None
            and preflight_finished < booted_at < postboot_started
        ),
        "watchdog_s4u_and_ran_after_boot": (
            before_watchdog.get("installed") is True and after_watchdog.get("installed") is True
            and before_watchdog.get("logon_type") == after_watchdog.get("logon_type") == "S4U"
            and after_watchdog.get("last_result") == 0
            and watchdog_after_run is not None and booted_at is not None and watchdog_after_run > booted_at
        ),
        "listener_s4u_session_zero": (
            diagnostics.get("logon_type") == "S4U"
            and diagnostics.get("task_state") in {"Ready", "Running"}
            and bool(listener_sessions) and all(session == 0 for session in listener_sessions)
        ),
        "listener_recovered_held_and_fresh": (
            after_listener.get("running") is True
            and float(after_listener.get("heartbeat_age_seconds", 9999)) < 30
            and reboot.get("state") == "POSTBOOT_CAPTURED"
            and reboot.get("listener_task_state") == "Running"
            and reboot.get("watchdog_task_state") in {"Ready", "Running"}
            and reboot.get("broker_mutation") == "NONE"
        ),
        "release_and_assessment_preserved": (
            reboot.get("listener_release_id") == reboot.get("postboot_release_id")
            == before_listener.get("release_id") == after_listener.get("release_id")
            and before_listener.get("assessment_total") == after_listener.get("assessment_total")
            and before_account.get("balance") == after_account.get("balance")
        ),
    }
    hashes = {name: "sha256:" + hashlib.sha256((raw / name).read_bytes()).hexdigest() for name in required}
    result = {"marker": "FOREX_W1_REBOOT_RECOVERY_PROOF_OK", "checks": checks, "raw_sha256": hashes, "ok": all(checks.values())}
    print(json.dumps(result, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
