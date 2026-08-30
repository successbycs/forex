#!/usr/bin/env python3
"""Launch one fresh, read-only Codex review of the current Builder diff."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]

PROMPT = """You are the Forex Reviewer.

Remain read-only. Do not modify code, state, evidence, contracts, Git history,
infrastructure, databases, or configuration. Do not commit, push, deploy, sign
off, run prove, or claim that a milestone is complete.

Review the current Builder worktree diff against HEAD in this repository. Read:
- AGENTS.md
- docs/governance/builder.md
- docs/governance/reviewer.md
- docs/governance/review-workflow.md
- docs/evidence_and_milestones.md
- docs/triad_review.md
- git status and the current diff

Assess only the change currently under review. Check authority boundaries,
maintainability, evidence/trading safety, and whether it duplicates the
existing Triad, human sign-off, or prove workflow.

Return a concise review with exactly:
- Outcome: READY, CHANGES_REQUIRED, or BLOCKED
- Required findings, if any, with IDs and recommended actions
- Optional observations
- Limitations
- Confirmation that you remained read-only and used a fresh context

Your answer is advice only. The human decides remediation, commits, sign-off,
and completion.
"""


def main() -> int:
    if shutil.which("codex") is None:
        print("ERROR: Codex CLI is unavailable", file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory(prefix="forex-ptr-") as temporary_directory:
        result_path = Path(temporary_directory) / "review.md"
        command = [
            "codex",
            "exec",
            "--sandbox",
            "read-only",
            "--ephemeral",
            "--cd",
            str(ROOT),
            "--output-last-message",
            str(result_path),
            "-",
        ]
        result = subprocess.run(
            command,
            input=PROMPT,
            text=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            check=False,
        )
        if result.returncode:
            if result.stderr:
                print(result.stderr.strip(), file=sys.stderr)
            return result.returncode
        if not result_path.is_file():
            print("ERROR: Codex did not produce a review response", file=sys.stderr)
            return 1
        print(result_path.read_text(encoding="utf-8").strip())
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
