#!/usr/bin/env python3
"""Capture/verify the bounded M31 retained NO_TRADE evaluation, without network access."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from forex.m31_supplement import evaluate_no_trade_supplement, require, verify_original_hashes
from forex.m31_scorecard import _instant, _json, render_terminal
from forex.m31_evidence import REQUIRED as ORIGINAL_REQUIRED
import m20_demo_evidence_contract as m20

MARKER = "FOREX_M31_PROOF_OK"
SURFACE = "controlled GOMarketsMU-Demo workflow evaluation"
OPERATION = "retained predeclared M1 refusal-window evaluation"
NAMES = {"enriched.json", "historical.json", "evaluation.json", "tests.txt", "governance.txt", "configuration.json", "summary.txt"}


def read(path: Path) -> bytes:
    require(not path.is_symlink() and path.is_file(), f"not a regular artifact: {path.name}")
    return path.read_bytes()


def compute(bundle: Path) -> dict:
    original = verify_original_hashes(bundle / "original")
    return evaluate_no_trade_supplement(
        protocol_raw=original["protocol.json"], receipt_raw=original["protocol-receipt.json"],
        original_raw=original["completeness.json"], enriched_raw=read(bundle / "enriched.json"),
        lifecycle_raw=original["lifecycle.json"], broker_raw=original["broker-history.json"],
        historical_raw=read(bundle / "historical.json"))


def summary(report: dict) -> str:
    # The technical proof marker does not replace review or human signoff.
    return (MARKER + "\n" + render_terminal(report["scorecard"]) +
            "\nScope: refusal-window evaluation only; not an active-strategy performance test.\n"
            "Broker cross-check: zero EURUSD deals during the declared interval.\n"
            "Existing positions, floating P&L and whole-account returns are not evaluated.\n"
            "Historical null policy was preselected; its exact artifact was bound afterward.\n"
            "No direct proposal-to-account hash join is available; no trade attribution is claimed.\n"
            "Technical evidence only: completion recommendation and human signoff remain required.\n")


def current_revision() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def clean() -> None:
    lines = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=all"], cwd=ROOT, text=True).splitlines()
    require(not any(line[3:] not in {"project_state.json", "runs/run_history.json"} for line in lines),
            "material worktree must be clean")


def verify(bundle: Path) -> dict:
    require(not bundle.is_symlink() and bundle.is_dir(), "bundle is not a regular directory")
    clean()
    manifest = _json(read(bundle / "manifest.json"), "manifest")
    require(manifest.get("schema_version") == "1.0.0" and manifest.get("milestone_id") == "M31"
            and manifest.get("surface") == SURFACE and manifest.get("operation") == OPERATION
            and manifest.get("dirty_worktree") is False and type(manifest.get("exit_code")) is int
            and manifest["exit_code"] == 0 and manifest.get("observed_result") == MARKER
            and manifest.get("summary") == MARKER, "formal manifest binding is invalid")
    require(manifest.get("git_revision") == current_revision(), "evaluator revision differs from HEAD")
    fingerprint = m20.project_fingerprint(ROOT)
    require(manifest.get("configuration_fingerprint") == fingerprint, "configuration fingerprint differs")
    now = datetime.now(timezone.utc)
    captured = _instant(manifest.get("captured_at"), "evaluation capture")
    require(timedelta(0) <= now - captured < timedelta(hours=24), "evaluation is stale or future-dated")
    expected = NAMES | {"original/" + n for n in ORIGINAL_REQUIRED}
    require({p.name for p in bundle.iterdir()} == NAMES | {"original", "manifest.json"}, "bundle inventory differs")
    artifacts = manifest.get("artifacts")
    require(isinstance(artifacts, list) and all(isinstance(i, dict) for i in artifacts), "invalid inventory")
    names = [i.get("path") for i in artifacts]
    require(all(isinstance(n, str) for n in names) and len(names) == len(set(names)) and set(names) == expected, "invalid inventory")
    for item in artifacts:
        require(hashlib.sha256(read(bundle / item["path"])).hexdigest() == item.get("sha256"), "artifact digest mismatch")
    report = compute(bundle)
    require(_json(read(bundle / "evaluation.json"), "evaluation") == report, "evaluation recomputation differs")
    end = _instant(report["scorecard"]["interval"]["to_utc"], "observation end")
    broker_capture = _instant(report["broker_crosscheck"]["captured_at_utc"], "broker capture")
    require(end <= broker_capture <= captured <= now and now - end < timedelta(hours=24),
            "retained observation is stale or future-dated")
    require(report["scorecard"]["provenance"]["configuration_fingerprint"] == fingerprint
            and manifest.get("runtime_revision") == report["scorecard"]["provenance"]["application_revision"],
            "runtime provenance differs")
    config = _json(read(bundle / "configuration.json"), "configuration")
    require(config == {"configuration_fingerprint": fingerprint, "runtime_mode": "DEMO_TRADING",
                      "live_trading_enabled": False, "permitted_mt5_server": "GOMarketsMU-Demo"},
            "Demo configuration binding differs")
    state = json.loads((ROOT / "project_state.json").read_text())
    require(all(state.get(k) == v for k, v in config.items()), "current configuration boundary differs")
    tests = read(bundle / "tests.txt").decode()
    require(re.search(r"\b[1-9]\d* passed\b", tests) is not None
            and re.search(r"\b[1-9]\d* (?:failed|errors?)\b", tests) is None, "tests did not pass")
    require("milestone governance valid" in read(bundle / "governance.txt").decode(), "governance did not pass")
    require(read(bundle / "summary.txt").decode() == summary(report), "summary differs")
    return {"marker": MARKER, "formal_closeout": False, "git_revision": manifest["git_revision"], "execution_authority": False}


def capture(args: argparse.Namespace) -> None:
    clean()
    require(not args.bundle.exists(), "bundle exists; refusing overwrite")
    original = verify_original_hashes(args.original_bundle)
    enriched, historical = read(args.enriched_completeness), read(args.historical_reference)
    args.bundle.mkdir(parents=True)
    (args.bundle / "original").mkdir()
    for name, raw in original.items():
        (args.bundle / "original" / name).write_bytes(raw)
    (args.bundle / "enriched.json").write_bytes(enriched)
    (args.bundle / "historical.json").write_bytes(historical)
    report = compute(args.bundle)
    (args.bundle / "evaluation.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    (args.bundle / "summary.txt").write_text(summary(report))
    fingerprint = m20.project_fingerprint(ROOT)
    (args.bundle / "configuration.json").write_text(json.dumps({"configuration_fingerprint": fingerprint,
        "runtime_mode": "DEMO_TRADING", "live_trading_enabled": False, "permitted_mt5_server": "GOMarketsMU-Demo"}, sort_keys=True) + "\n")
    for name, command in (("tests.txt", [sys.executable, "-m", "pytest", "-o", "addopts=", "-q", "tests/milestones/test_m31.py", "tests/test_postgres_pgvector_adapter.py", "tests/test_m1_postgres_completeness.py", "tests/test_m20_history_report.py", "tests/test_triad.py"]),
                          ("governance.txt", [sys.executable, "scripts/forex_milestones.py", "validate"])):
        result = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (args.bundle / name).write_text(result.stdout)
        require(result.returncode == 0, f"{name} failed; preserve partial evidence")
    clean()
    names = sorted(NAMES | {"original/" + n for n in ORIGINAL_REQUIRED})
    manifest = {"schema_version": "1.0.0", "milestone_id": "M31", "captured_at": datetime.now(timezone.utc).isoformat(),
        "git_revision": current_revision(), "runtime_revision": report["scorecard"]["provenance"]["application_revision"],
        "dirty_worktree": False, "configuration_fingerprint": fingerprint, "surface": SURFACE, "operation": OPERATION,
        "expected_result": "reproducible predeclared NO_TRADE evaluation against the historical no-exposure null policy",
        "observed_result": MARKER, "exit_code": 0, "summary": MARKER,
        "redactions": ["No credentials or account login retained; broker account scope is a one-way hash."],
        "artifacts": [{"path": n, "sha256": hashlib.sha256(read(args.bundle / n)).hexdigest()} for n in names]}
    (args.bundle / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(verify(args.bundle), sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["capture", "verify"])
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--original-bundle", type=Path)
    parser.add_argument("--enriched-completeness", type=Path)
    parser.add_argument("--historical-reference", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "capture":
            require(all((args.original_bundle, args.enriched_completeness, args.historical_reference)), "capture requires retained sources")
            capture(args)
        else:
            print(json.dumps(verify(args.bundle), sort_keys=True))
        return 0
    except (ValueError, OSError, TypeError, KeyError, m20.VerificationError) as exc:
        print(f"M31 retained evidence refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
