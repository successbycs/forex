#!/usr/bin/env python3
"""Run one durable BLS scheduling pass; no trading or service activation."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def _constant(value):
    raise ValueError("nonfinite JSON value")


def _json(raw):
    return json.loads(raw, object_pairs_hook=_pairs, parse_constant=_constant)


def collect_once(store, *, year, month, capture_id, resume):
    command = [sys.executable, str(ROOT / "scripts/bls_collect.py"),
               "--store", str(store), "--year", str(year), "--month", str(month),
               "--capture-id", capture_id]
    if resume:
        command.append("--resume")
    # Greater than the collector's maximum 60-second transport deadline.
    # A timeout leaves its durable claim unresolved; never retry a fresh GET.
    completed = subprocess.run(command, capture_output=True, text=True, timeout=90, check=False)
    if completed.returncode not in (0, 3):
        raise ValueError("collector did not return a retained observation; local recovery required")
    result = _json(completed.stdout)
    if (not isinstance(result, dict) or result.get("schema_version") != "forex.bls-collection-result.v1"
            or result.get("capture_id") != capture_id or result.get("execution_authority") is not False
            or (completed.returncode == 0) != (result.get("outcome") == "SUCCESS")):
        raise ValueError("collector summary does not bind the requested capture and outcome")
    # Independently rebuild the summary from retained bytes. Child stdout alone
    # must not clear a pending claim or determine a publisher backoff.
    from forex.bls_collection import resume_collection
    retained = resume_collection(store, year=year, month=month, capture_id=capture_id)
    if result != retained:
        raise ValueError("collector summary does not match retained observation")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        from forex.bls_scheduler import run_schedule_once
        policy = _json((ROOT / "config/bls_scheduler.json").read_bytes())
        result = run_schedule_once(args.store, now_utc=datetime.now(timezone.utc).isoformat(),
            policy=policy, collect=lambda **kwargs: collect_once(args.store, **kwargs))
        print(json.dumps(result, sort_keys=True, allow_nan=False))
        return 3 if result["state"] == "RECOVERY_REQUIRED" else 0
    except (OSError, ValueError, TypeError, KeyError, RuntimeError, subprocess.TimeoutExpired):
        print("BLS scheduler refused; inspect retained scheduler and collector state before recovery", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
