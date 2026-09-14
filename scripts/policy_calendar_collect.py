#!/usr/bin/env python3
"""Collect exactly one fixed first-party policy calendar through T480."""
from __future__ import annotations

import argparse
import ast
import base64
import gzip
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
# Scripts normally start with their own directory on sys.path.  The collector
# needs both installed Forex code and the repository-owned T480 probe, while
# --help must remain side-effect free under PYTHONPATH=src.
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))


def probe_program(source: bytes, family_name: str) -> bytes:
    """Ship the fixed probe implementation through the existing T480 path."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef)) and node.body:
            if isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str):
                node.body.pop(0)
    program = ast.unparse(tree) + (
        "\nimport json\nprint(json.dumps(collect_policy_calendar(PolicyCalendarFamily."
        + family_name + "), sort_keys=True, allow_nan=False))\n"
    )
    return program.encode("utf-8")


def main(argv: list[str] | None = None) -> int:
    from forex.first_party_policy_capture import (
        PolicyCalendarCaptureError,
        reserve_transport_capture,
        retain_transport_result,
    )
    from t480.first_party_policy_calendar_probe import PolicyCalendarFamily

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family", required=True, choices=[family.value for family in PolicyCalendarFamily])
    parser.add_argument("--capture-id", required=True)
    parser.add_argument("--store", type=Path, required=True)
    args = parser.parse_args(argv)
    family = PolicyCalendarFamily(args.family)
    try:
        # This reservation is intentionally before importing/using the shared
        # transport.  A duplicate ID must never cause a second remote request.
        reservation = reserve_transport_capture(args.store, capture_id=args.capture_id)
        import t480_adapter as transport

        probe_bytes = (ROOT / "t480/first_party_policy_calendar_probe.py").read_bytes()
        program = probe_program(probe_bytes, family.name)
        payload = base64.b64encode(gzip.compress(program, mtime=0)).decode("ascii")
        operation = transport.Operation(
            "first_party_policy_calendar_probe",
            "One bounded fixed first-party policy-calendar request",
            powershell_command=(
                "$ErrorActionPreference='Stop'; '" + payload + "' | wsl.exe -d "
                + transport.TRANSPORT_SETTINGS.wsl_distribution
                + " -- python3 -c 'import sys,base64,gzip;exec(gzip.decompress(base64.b64decode(sys.stdin.read())))'; exit $LASTEXITCODE"
            ),
            timeout_seconds=35,
        )
        try:
            observed = transport.execute_operation(operation, target=transport.target(), settings=transport.TRANSPORT_SETTINGS)
        except Exception:
            observed = {
                "operation": "first_party_policy_calendar_probe",
                "ok": False,
                "result": {"exit_code": 1, "stdout": ""},
                "error_code": "TRANSPORT_EXCEPTION",
            }
        result = retain_transport_result(
            args.store,
            capture_id=args.capture_id,
            family=family,
            transport_observation=observed,
            probe_sha256="sha256:" + __import__("hashlib").sha256(probe_bytes).hexdigest(),
            program_sha256="sha256:" + __import__("hashlib").sha256(program).hexdigest(),
            reservation=reservation,
        )
    except (OSError, ValueError, TypeError, KeyError, PolicyCalendarCaptureError) as exc:
        print(f"policy calendar collection refused: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0 if result["outcome"] == "SUCCESS" else 3


if __name__ == "__main__":
    raise SystemExit(main())
