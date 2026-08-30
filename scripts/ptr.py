#!/usr/bin/env python3
"""Prepare one deterministic, read-only Triad reviewer handoff.

PTR means "pass to reviewer".  It deliberately does not launch another Codex
process or write a review result: those behaviours made a timed-out process
look like a completed review.  A human pastes the emitted prompt into a fresh
Reviewer Codex session, then records the returned JSON through the existing
Triad workflow.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]

ROLE_NAMES = {
    "ai_engineer": "AI Engineer",
    "solution_architect": "Solution Architect",
    "senior_software_developer": "Senior Software Developer",
    "financial_domain_expert": "Financial Domain Expert",
}
ROLE_ORDER = tuple(ROLE_NAMES)


def _active_milestone() -> str:
    state = json.loads((ROOT / "project_state.json").read_text(encoding="utf-8"))
    return str(state["current_milestone"])


def _latest_cycle(milestone_id: str) -> Path:
    root = ROOT / "runs" / "triad" / milestone_id
    cycles = sorted(
        (path for path in root.glob(f"{milestone_id}-*") if (path / "request.json").is_file()),
        key=lambda path: path.name,
    )
    if not cycles:
        raise FileNotFoundError(f"no prepared Triad cycle for {milestone_id}; run prepare first")
    return cycles[-1]


def build_prompt(cycle: Path, role: str) -> str:
    role_name = ROLE_NAMES[role]
    packet = cycle / "packets" / f"{role}.md"
    template = cycle / "templates" / f"{role}.json"
    submission = cycle / "submissions" / f"{role}.json"
    if not packet.is_file() or not template.is_file():
        raise FileNotFoundError(f"incomplete review packet for {role_name}: {cycle}")

    relative = lambda path: path.relative_to(ROOT).as_posix()
    return f"""You are the Forex {role_name} Reviewer for one isolated Triad review.

You are strictly read-only. Do not edit code, state, evidence, contracts, Git
history, infrastructure, databases, or configuration. Do not commit, push,
deploy, sign off, run prove, or claim that the milestone is complete. Do not
read other reviewers' submissions or verdicts.

Read, in order:
- AGENTS.md
- docs/evidence_and_milestones.md
- docs/triad_review.md
- {relative(cycle / 'request.json')}
- {relative(packet)}
- the bound evidence and committed revision named in that packet
- {relative(template)}

Review only this role's assigned criteria and the exact bound evidence. Return
*only* a completed JSON object that conforms exactly to the supplied template.
Do not save it in the repository; put the JSON in your final reply. The Builder
will validate it separately and, if valid, save it at:
{relative(submission)}

In the JSON, attest that this was a fresh read-only context. Use FAIL or
ABSTAIN where the evidence cannot responsibly support PASS. Your verdict is a
review input only; it is not human approval or milestone completion.
"""


def _submission_path(cycle: Path, role: str) -> Path:
    return cycle / "submissions" / f"{role}.json"


def _validate(cycle: Path, review: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "forex_triad.py"),
            "validate-review",
            "--cycle",
            str(cycle.relative_to(ROOT)),
            "--review",
            str(review),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _run_role(cycle: Path, role: str, timeout_seconds: int) -> bool:
    if shutil.which("codex") is None:
        print("ERROR: Codex CLI is unavailable", file=sys.stderr)
        return False
    prompt = build_prompt(cycle, role)
    with tempfile.TemporaryDirectory(prefix="forex-ptr-") as temporary_directory:
        response = Path(temporary_directory) / f"{role}.json"
        command = [
            "codex",
            "exec",
            "--sandbox",
            "read-only",
            "--ephemeral",
            "--cd",
            str(ROOT),
            "--output-last-message",
            str(response),
            "-",
        ]
        print(f"PTR_REQUEST_SENT role={ROLE_NAMES[role]}", flush=True)
        try:
            result = subprocess.run(
                command,
                input=prompt,
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                check=False,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            print(f"PTR_TIMEOUT role={ROLE_NAMES[role]} after_seconds={timeout_seconds}", file=sys.stderr)
            return False
        if result.returncode or not response.is_file() or not response.read_text(encoding="utf-8").strip():
            detail = result.stderr.strip() if result.stderr else "no JSON response produced"
            print(f"PTR_NO_RESPONSE role={ROLE_NAMES[role]} detail={detail}", file=sys.stderr)
            return False
        validation = _validate(cycle, response)
        if validation.returncode:
            print(
                f"PTR_INVALID_RESPONSE role={ROLE_NAMES[role]} detail={validation.stderr.strip()}",
                file=sys.stderr,
            )
            return False
        target = _submission_path(cycle, role)
        target.parent.mkdir(exist_ok=True)
        target.write_text(response.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"PTR_RESPONSE_VALID role={ROLE_NAMES[role]} saved={target.relative_to(ROOT)}", flush=True)
    return True


def _submission_is_valid(cycle: Path, role: str) -> bool:
    submission = _submission_path(cycle, role)
    return submission.is_file() and _validate(cycle, submission).returncode == 0


def run_sequence(cycle: Path, timeout_seconds: int) -> int:
    for role in ROLE_ORDER:
        if _submission_is_valid(cycle, role):
            print(f"PTR_SKIP_VALID role={ROLE_NAMES[role]}")
            continue
        if not _run_role(cycle, role, timeout_seconds):
            print(f"PTR_STOPPED next_role={ROLE_NAMES[role]}", file=sys.stderr)
            return 1
    print(f"PTR_SEQUENCE_COMPLETE cycle={cycle.relative_to(ROOT)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="prepare one isolated Triad reviewer prompt")
    parser.add_argument("--id", help="milestone ID; defaults to the active milestone")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--role", choices=sorted(ROLE_NAMES))
    mode.add_argument("--sequence", action="store_true", help="request, validate, and record each missing role in order")
    parser.add_argument("--timeout-seconds", type=int, default=600)
    args = parser.parse_args(argv)
    if args.timeout_seconds < 1:
        parser.error("--timeout-seconds must be positive")
    milestone_id = args.id or _active_milestone()
    try:
        cycle = _latest_cycle(milestone_id)
        if args.sequence:
            return run_sequence(cycle, args.timeout_seconds)
        print(build_prompt(cycle, args.role))
    except (FileNotFoundError, KeyError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
