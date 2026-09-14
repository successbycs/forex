#!/usr/bin/env python3
"""Validate one local fixed H_SLOW Demo preflight record without broker access."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def _reject_nonfinite(value: str) -> None:
    raise ValueError(f"nonfinite JSON constant: {value}")


def _read_input(path: Path) -> dict[str, object]:
    if not isinstance(path, Path):
        raise ValueError("input must be an existing non-symlink local JSON file")
    local_path = path.absolute()
    if (any(ancestor.is_symlink() for ancestor in (local_path, *local_path.parents))
            or not local_path.is_file()):
        raise ValueError("input must be an existing non-symlink local JSON file")
    raw = json.loads(
        local_path.read_bytes(), object_pairs_hook=_unique_object, parse_constant=_reject_nonfinite
    )
    if not isinstance(raw, dict):
        raise ValueError("preflight input must be a JSON object")
    return raw


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="one local preflight JSON record")
    args = parser.parse_args(argv)
    try:
        from forex.config import load_configuration
        from forex.h_slow_broker_preflight import validate_broker_preflight

        record = _read_input(args.input)
        configuration = load_configuration(ROOT, environ={})
        result = validate_broker_preflight(
            record,
            expected_broker_timestamp_offset_seconds=(
                configuration.mt5.broker_tick_time_offset_seconds
            ),
        )
        print(json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False))
    except (OSError, OverflowError, TypeError, ValueError) as exc:
        print(f"H_SLOW preflight validation refused: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
