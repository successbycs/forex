#!/usr/bin/env python3
"""One fixed BLS request through shared T480 transport, then immutable retention."""
import argparse
import ast
import base64
import gzip
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def probe_program(source: bytes, year: int, month: int) -> bytes:
    """Ship the same functions without local CLI/docstrings over Windows SSH."""
    tree = ast.parse(source)
    guard = ast.dump(ast.parse("if __name__ == '__main__': pass").body[0].test)
    tree.body = [node for node in tree.body if not (isinstance(node, ast.If) and ast.dump(node.test) == guard)
                 and not (isinstance(node, ast.FunctionDef) and node.name in {"main", "_bounded_year", "_bounded_month"})]
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef)) and node.body:
            if isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str):
                node.body.pop(0)
    program = ast.unparse(tree) + f"\nprint(json.dumps(collect_month({year}, {month}), sort_keys=True, allow_nan=False))\n"
    return program.encode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--month", type=int, required=True)
    parser.add_argument("--capture-id", required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--resume", action="store_true", help="Process retained response only; no network request")
    args = parser.parse_args()
    try:
        from forex.bls_collection import monthly_url, retain_response, resume_collection, retain_transport_observation
        from forex.event_capture_store import _safe_id, _sha, _layout
        monthly_url(args.year, args.month)
        _safe_id(args.capture_id)
        if args.resume:
            result = resume_collection(args.store, capture_id=args.capture_id, year=args.year, month=args.month)
        else:
            if (args.store / "acquisitions" / args.capture_id).exists() or (args.store / "transport" / args.capture_id).exists():
                raise ValueError("capture acquisition already exists; use --resume without re-fetching")
            _layout(args.store)
            policy = json.loads((ROOT / "config/bls_collection.json").read_bytes())
            if (policy.get("schema_version") != "forex.bls-collection-policy.v1"
                    or policy.get("operation_id") != "bls_monthly_calendar_probe"
                    or policy.get("source_id") != "bls-monthly-release-calendar"
                    or type(policy.get("automatic_retries")) is not int or policy["automatic_retries"] != 0
                    or policy.get("execution_authority") is not False
                    or type(policy.get("transport_deadline_seconds")) is not int
                    or not 25 <= policy["transport_deadline_seconds"] <= 60):
                raise ValueError("BLS collection policy is invalid")
            import t480_adapter as transport
            probe_bytes = (ROOT / "t480/bls_monthly_probe.py").read_bytes()
            program = probe_program(probe_bytes, args.year, args.month)
            payload = base64.b64encode(gzip.compress(program, mtime=0)).decode("ascii")
            operation = transport.Operation("bls_monthly_calendar_probe", "One bounded public BLS monthly calendar request",
                powershell_command=(f"$ErrorActionPreference='Stop'; '{payload}' | wsl.exe -d "
                    f"{transport.TRANSPORT_SETTINGS.wsl_distribution} -- python3 -c "
                    "'import sys,base64,gzip;exec(gzip.decompress(base64.b64decode(sys.stdin.read())))'; exit $LASTEXITCODE"),
                timeout_seconds=policy["transport_deadline_seconds"])
            observed = transport.execute_operation(operation, target=transport.target(), settings=transport.TRANSPORT_SETTINGS)
            retain_transport_observation(args.store, capture_id=args.capture_id, year=args.year, month=args.month,
                observation=observed, probe_sha256=_sha(probe_bytes),
                source_declaration_sha256=_sha((ROOT / "config/event_sources.json").read_bytes()),
                program_sha256=_sha(program))
            if not observed.get("ok") or observed.get("result", {}).get("exit_code") != 0:
                raise ValueError("shared BLS transport failed; no publisher response established")
            raw = observed["result"]["stdout"].encode("utf-8")
            result = retain_response(args.store, capture_id=args.capture_id, raw=raw, year=args.year, month=args.month)
        print(json.dumps(result, sort_keys=True, allow_nan=False))
        return 0 if result["outcome"] == "SUCCESS" else 3
    except (OSError, ValueError, TypeError, KeyError, OverflowError, RuntimeError) as exc:
        print(f"BLS collection refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
