#!/usr/bin/env python3
"""Verify retained M33 T480 reboot/guardian receipts without contacting T480."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def receipt(path: Path) -> dict:
    value = json.loads(path.read_text())
    if value.get("ok") is not True or value.get("result", {}).get("exit_code") != 0:
        raise ValueError(f"unsuccessful fixed receipt: {path.name}")
    output = value["result"].get("stdout")
    if not isinstance(output, str):
        raise ValueError(f"missing fixed output: {path.name}")
    return json.loads(output)


def verify(bundle: Path) -> None:
    required = {
        "preflight-listener.json", "preflight-held-readiness.json", "reboot-request.json",
        "postboot-recovery-record-final.json", "postboot-guardian-scheduler.json",
        "guardian-recurrence-cycle-2.json", "final-listener-status.json", "final-held-readiness.json",
    }
    missing = required - {item.name for item in bundle.iterdir() if item.is_file()}
    if missing:
        raise ValueError("missing required receipts: " + ",".join(sorted(missing)))
    reboot = receipt(bundle / "reboot-request.json")
    if reboot.get("broker_mutation") != "NONE" or reboot.get("armed") is not True:
        raise ValueError("reboot was not the fixed no-order protocol")
    recovered = receipt(bundle / "postboot-recovery-record-final.json")
    if recovered.get("record", {}).get("state") != "POSTBOOT_CAPTURED":
        raise ValueError("postboot recovery was not captured")
    guardian = receipt(bundle / "guardian-recurrence-cycle-2.json")
    status = guardian.get("status", {})
    if guardian.get("last_result") != 0 or not guardian.get("last_run_utc"):
        raise ValueError("guardian task did not complete")
    if status.get("entry_eligible") is not False or status.get("state") != "BLOCKED_POLICY":
        raise ValueError("guardian was not fail-closed")
    listener = receipt(bundle / "final-listener-status.json")
    binding = listener.get("runtime_binding", {})
    if listener.get("state") != "MAINTENANCE_HOLD" or binding.get("server") != "GOMarketsMU-Demo" or binding.get("currency") != "AUD":
        raise ValueError("final listener binding/hold is invalid")
    held = receipt(bundle / "final-held-readiness.json")
    assessment = held.get("assessment", {})
    if held.get("maintenance_hold") is not True or assessment.get("open_positions") != 0 or assessment.get("broker_mutation") != "NONE" or assessment.get("order_submission") != "STRUCTURALLY_UNAVAILABLE":
        raise ValueError("final held no-order invariant is invalid")
    digest = hashlib.sha256(b"".join((bundle / name).read_bytes() for name in sorted(required))).hexdigest()
    print(json.dumps({"marker": "FOREX_M33_LOCAL_TRADING_HEALTH_OK", "receipt_set_sha256": "sha256:" + digest}, separators=(",", ":")))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    try:
        verify(args.bundle)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"M33 T480 health evidence error: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
