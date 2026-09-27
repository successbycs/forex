"""Capture a no-order M33.2 guardian observation matrix from live local facts.

The runner does not change the listener, Scheduled Tasks, MT5, broker, or
guardian status.  It obtains one live local observation through the installed
guardian collector, then applies explicitly labelled in-memory fault variants
to the pure policy.  This proves state distinction without manufacturing a
runtime fault; M33.4 still owns real fault and lifecycle proof.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from dataclasses import asdict, replace
from datetime import UTC, datetime
from importlib.machinery import SourceFileLoader
from pathlib import Path
from typing import Any, Callable


HERE = Path(__file__).resolve().parent
_IMMUTABLE_RELEASE = HERE.parent.name == "guardian-releases"


def _load_guardian() -> Any:
    if not _IMMUTABLE_RELEASE:
        if str(HERE.parent / "src") not in sys.path:
            sys.path.insert(0, str(HERE.parent / "src"))
        from t480 import trading_health_guardian
        return trading_health_guardian
    payload = HERE / "trading_health_guardian.payload"
    spec = importlib.util.spec_from_loader(
        "forex_m33_matrix_guardian", SourceFileLoader("forex_m33_matrix_guardian", str(payload))
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("M33 guardian payload is unavailable for matrix capture")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    temporary.replace(path)


def _require_held_demo_baseline(root: Path, guardian: Any) -> dict[str, Any]:
    hold = guardian._read_json(root / "m20_demo_maintenance_hold.local.json")
    listener = guardian._read_json(root / "m20_demo_listener_status.local.json")
    binding = listener.get("runtime_binding") if isinstance(listener, dict) else None
    if not (isinstance(hold, dict) and hold.get("enabled") is True):
        raise RuntimeError("M33 matrix capture requires the existing maintenance hold")
    if not (isinstance(listener, dict) and listener.get("state") == "MAINTENANCE_HOLD"):
        raise RuntimeError("M33 matrix capture requires a held listener heartbeat")
    if not (isinstance(binding, dict) and binding.get("server") == "GOMarketsMU-Demo"
            and binding.get("currency") == "AUD" and binding.get("state") == "MAPPED"):
        raise RuntimeError("M33 matrix capture requires the mapped GOMarketsMU-Demo/AUD binding")
    return listener


def run_matrix(root: Path, output: Path, now: datetime | None = None,
               observation_loader: Callable[[Path, datetime], tuple[Any, Any, Any, Any]] | None = None) -> dict[str, Any]:
    """Write a labelled classification matrix derived from one live observation."""
    guardian = _load_guardian()
    now = now or datetime.now(UTC)
    listener = _require_held_demo_baseline(root, guardian)
    loader = observation_loader or guardian._observation
    observed, _mode, _retry, _attempts = loader(root, now)
    required = {
        "session_ok": True, "managed_mt5_count": 1, "unattributable_mt5_count": 0,
        "mt5_identity_ok": True, "mt5_responding": True, "permissions_ok": True,
        "broker_connected": True, "data_fresh": True, "db_available": True,
        "listener_present": True, "monitoring_fresh": True,
    }
    failed = [name for name, value in required.items() if getattr(observed, name) != value]
    if failed:
        raise RuntimeError("M33 matrix baseline is not healthy enough: " + ",".join(failed))

    cases = (
        ("healthy_monitor_only", "MONITOR_ONLY", {}, "MONITOR_ONLY"),
        ("operator_stopped", "STOPPED", {}, "STOPPED_BY_OPERATOR"),
        ("listener_absent", "RUN_DEMO", {"listener_present": False}, "RECOVERING_LISTENER"),
        ("listener_stalled", "RUN_DEMO", {"listener_heartbeat_age_s": 31.0, "data_fresh": False}, "RECOVERING_LISTENER"),
        ("managed_duplicate_flat", "RUN_DEMO", {
            "managed_mt5_count": 2, "exposure_flat": True, "inflight_unresolved": False,
        }, "RECOVERING_MT5"),
        ("audit_dependency_blocked", "RUN_DEMO", {"db_available": False}, "BLOCKED_DEPENDENCY"),
    )
    results = []
    for case_id, mode, overrides, expected_state in cases:
        decision = guardian.classify(replace(observed, **overrides), mode)
        if decision.state != expected_state or decision.entry_eligible:
            raise RuntimeError(f"M33 matrix case {case_id} was not fail-closed as specified")
        results.append({
            "case_id": case_id, "intent_mode": mode, "simulated_fields": sorted(overrides),
            "expected_state": expected_state, "state": decision.state,
            "reasons": list(decision.reasons), "recommended_action": decision.recommended_action,
            "entry_eligible": decision.entry_eligible,
        })
    record = {
        "schema_version": "forex.trading-health-observation-matrix.v1",
        "captured_at_utc": now.isoformat().replace("+00:00", "Z"),
        "listener_release_id": listener.get("release_id"),
        "baseline": {key: asdict(observed).get(key) for key in required},
        "cases": results,
        "broker_mutation": "NONE",
        "note": "Variants are in-memory policy inputs derived from the held live baseline; they are not runtime fault injections.",
    }
    _atomic_json(output, record)
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture the held no-order M33 guardian observation matrix.")
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run_matrix(args.state_root, args.output), separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
