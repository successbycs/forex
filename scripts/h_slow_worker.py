#!/usr/bin/env python3
"""Run one explicitly configured, submission-disabled H_SLOW durable pass.

This command deliberately has no broker adapter, account discovery, route,
claim, or order-submission option.  The operator must provide an already
configured local PostgreSQL DSN through a named environment variable and must
apply the reviewed lifecycle schema before invoking it.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

_REQUIRED = {"research_decision", "envelope", "stream_registry", "evaluated_at_utc", "maximum_observation_age_seconds"}
_OPTIONAL = {"trial_mandate"}


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _constant(value: str) -> None:
    raise ValueError(f"nonfinite JSON constant: {value}")


def _input(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_bytes(), object_pairs_hook=_pairs, parse_constant=_constant)
    if not isinstance(value, dict) or set(value) - _REQUIRED - _OPTIONAL or not _REQUIRED <= set(value):
        raise ValueError("input must contain exactly the runtime fields and optional trial_mandate")
    return value


def _dsn(variable: str) -> str:
    if re.fullmatch(r"FOREX_H_SLOW_[A-Z0-9_]+", variable) is None:
        raise ValueError("DSN environment variable name is not permitted")
    value = os.environ.get(variable)
    if not value:
        raise ValueError(f"required local DSN environment variable is unset: {variable}")
    return value


def run_once(*, payload: dict[str, Any], dsn: str) -> dict[str, Any]:
    """Construct the existing persistence adapter without selecting a target."""
    try:
        import psycopg
    except ImportError as exc:
        raise ValueError("psycopg is required only for an explicitly configured durable worker") from exc
    from forex.h_slow_persistence import HSlowLifecycleStore
    from forex.h_slow_worker import run_h_slow_worker_once

    store = HSlowLifecycleStore(lambda: psycopg.connect(dsn), stream_registry=payload["stream_registry"])
    result = run_h_slow_worker_once(store=store, **payload)
    if result.get("execution_authority") is not False or result.get("submission_status") != "DISABLED_NOT_ROUTED":
        raise ValueError("disabled worker returned an unsafe result")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="retained H_SLOW worker JSON input")
    parser.add_argument("--dsn-env", default="FOREX_H_SLOW_DSN",
                        help="named local environment variable containing the PostgreSQL DSN")
    arguments = parser.parse_args(argv)
    try:
        result = run_once(payload=_input(arguments.input), dsn=_dsn(arguments.dsn_env))
        print(json.dumps(result, sort_keys=True, allow_nan=False))
        return 0
    except (OSError, ValueError, TypeError, OverflowError) as exc:
        print(f"H_SLOW durable worker refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
