#!/usr/bin/env python3
"""Run a fresh, read-only four-role Triad review with bounded retries.

This is a delivery helper, not a completion authority.  It never signs off,
proves a milestone, edits evidence, or changes a reviewer response.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TRIAD = [sys.executable, str(ROOT / "scripts" / "forex_triad.py")]
MILESTONES = [sys.executable, str(ROOT / "scripts" / "forex_milestones.py")]
ROLES = ("SOLUTION_ARCHITECT", "SENIOR_SOFTWARE_DEVELOPER", "AI_ENGINEER", "FINANCIAL_DOMAIN_EXPERT")


def run(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=ROOT, text=True, capture_output=True, check=False)


def packet_dir(milestone_id: str) -> Path:
    prepared = run([*TRIAD, "prepare", "--id", milestone_id])
    if prepared.returncode:
        raise RuntimeError(prepared.stderr.strip() or prepared.stdout.strip())
    return Path(prepared.stdout.strip())


def role_filename(role: str) -> str:
    return role.lower() + ".json"


def prompt(cycle: Path, role: str) -> str:
    packet = cycle / "packets" / f"{role.lower()}.md"
    template = cycle / "templates" / f"{role.lower()}.json"
    # Avoid shell interpolation: the paths are supplied as plain model input.
    return (
        f"You are the independent read-only {role} reviewer. Read {packet} and {template}, "
        "the cycle request, the bound raw evidence, and current committed files. Do not edit, "
        "commit, deploy, sign off, prove, or read another review. Return only a completed JSON "
        "object that exactly follows the supplied template and the output schema."
    )


def review_role(cycle: Path, role: str, attempts: int) -> tuple[bool, list[dict[str, str]]]:
    submissions = cycle / "submissions"; submissions.mkdir(exist_ok=True)
    events: list[dict[str, str]] = []
    schema = ROOT / "config" / "schemas" / "triad-review.schema.json"
    for number in range(1, attempts + 1):
        raw = submissions / f"{role.lower()}.attempt-{number}.raw.json"
        command = [
            "codex", "exec", "--ephemeral", "-s", "read-only", "-C", str(ROOT),
            "--output-schema", str(schema), "-o", str(raw), prompt(cycle, role),
        ]
        result = run(command)
        event = {"role": role, "attempt": str(number), "exit_code": str(result.returncode), "raw": str(raw.relative_to(ROOT)), "error": result.stderr.strip()}
        if result.returncode == 0 and raw.is_file():
            validation = run([*TRIAD, "validate-review", "--cycle", str(cycle), "--review", str(raw)])
            event["validation"] = validation.stdout.strip() or validation.stderr.strip()
            if validation.returncode == 0:
                shutil.copyfile(raw, submissions / role_filename(role))
                events.append(event)
                return True, events
        events.append(event)
    return False, events


def main() -> int:
    parser = argparse.ArgumentParser(description="Run bounded fresh Codex Triad reviews.")
    parser.add_argument("--id", required=True, help="milestone ID")
    parser.add_argument("--attempts", type=int, default=3, choices=(1, 2, 3))
    parser.add_argument("--record-recommendation", action="store_true")
    args = parser.parse_args()
    cycle = packet_dir(args.id)
    events: list[dict[str, str]] = []
    passed = True
    for role in ROLES:
        ok, role_events = review_role(cycle, role, args.attempts)
        events.extend(role_events); passed = passed and ok
    (cycle / "review-runner-attempts.json").write_text(json.dumps(events, indent=2) + "\n")
    if not passed:
        print(json.dumps({"status": "REVIEW_AUTOMATION_FAILED", "cycle": str(cycle), "attempts": events}, indent=2))
        return 2
    recommendation = run([*TRIAD, "recommend", "--cycle", str(cycle)])
    if recommendation.returncode:
        print(recommendation.stderr, file=sys.stderr); return 2
    recommendation_path = cycle / "recommendation.json"
    assessed = run([*TRIAD, "assess", "--recommendation", str(recommendation_path)])
    if assessed.returncode:
        print(assessed.stderr, file=sys.stderr); return 2
    if args.record_recommendation:
        recorded = run([*MILESTONES, "record-triad-recommendation", "--id", args.id, "--recommendation", str(recommendation_path)])
        if recorded.returncode:
            print(recorded.stderr, file=sys.stderr); return 2
    print(json.dumps({"status": "RECOMMENDATION_READY", "cycle": str(cycle), "recommendation": str(recommendation_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
