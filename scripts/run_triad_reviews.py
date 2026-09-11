#!/usr/bin/env python3
"""Run a fresh, read-only four-role Triad review with bounded retries.

This is a delivery helper, not a completion authority.  It never signs off,
proves a milestone, edits evidence, or changes a reviewer response.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TRIAD = [sys.executable, str(ROOT / "scripts" / "forex_triad.py")]
MILESTONES = [sys.executable, str(ROOT / "scripts" / "forex_milestones.py")]
ROLES = ("SOLUTION_ARCHITECT", "SENIOR_SOFTWARE_DEVELOPER", "AI_ENGINEER", "FINANCIAL_DOMAIN_EXPERT")
# Reviewers must not inherit desktop-only MCP connectors.  In particular, an
# unavailable optional connector must not prevent an evidence review that only
# needs this repository.  Codex authentication still uses CODEX_HOME.
# A reviewer receives a deliberately bounded, revision-only snapshot.  Five
# minutes leaves enough time to inspect the evidence without encouraging the
# runner to accept an unbounded live-worktree review.
REVIEW_TIMEOUT_SECONDS = 300


def run(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=ROOT, text=True, capture_output=True, check=False)


def packet_dir(milestone_id: str) -> Path:
    prepared = run([*TRIAD, "prepare", "--id", milestone_id])
    if prepared.returncode:
        raise RuntimeError(prepared.stderr.strip() or prepared.stdout.strip())
    return Path(prepared.stdout.strip())


def role_filename(role: str) -> str:
    return role.lower() + ".json"


def _relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def _write_raw(path: Path, content: str | bytes | None) -> dict[str, Any] | None:
    """Retain process output separately from compact attempt metadata."""
    if content is None:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    data = content.encode("utf-8") if isinstance(content, str) else content
    path.write_bytes(data)
    return {
        "path": _relative(path),
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
    }


def _safe_extract(archive: bytes, destination: Path) -> None:
    """Extract a Git archive without permitting paths outside its snapshot."""
    with tarfile.open(fileobj=io.BytesIO(archive)) as source:
        for member in source.getmembers():
            target = (destination / member.name).resolve()
            if not target.is_relative_to(destination.resolve()):
                raise RuntimeError("unsafe path in Git archive")
        source.extractall(destination, filter="data")


def create_review_workspace(cycle: Path, role: str) -> Path:
    """Make a minimal, clean snapshot bound to this cycle's Git revision.

    It intentionally is not a worktree: no `.git`, mutable run state, prior
    submissions, or desktop configuration can leak into an independent role.
    """
    request = json.loads((cycle / "request.json").read_text(encoding="utf-8"))
    workspace = cycle / "review-workspaces" / role.lower()
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True)
    archive = subprocess.run(
        ["git", "archive", "--format=tar", request["git_revision"]],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    if archive.returncode:
        raise RuntimeError(archive.stderr.decode("utf-8", errors="replace").strip() or "cannot archive bound revision")
    _safe_extract(archive.stdout, workspace)

    live_manifest = ROOT / request["evidence_manifest_path"]
    if not live_manifest.is_file():
        raise RuntimeError("bound evidence manifest is missing")
    if hashlib.sha256(live_manifest.read_bytes()).hexdigest() != request["evidence_manifest_sha256"]:
        raise RuntimeError("bound evidence manifest hash does not match the review request")
    evidence_destination = workspace / request["evidence_manifest_path"]
    evidence_destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(live_manifest.parent, evidence_destination.parent, dirs_exist_ok=True)
    if hashlib.sha256(evidence_destination.read_bytes()).hexdigest() != request["evidence_manifest_sha256"]:
        raise RuntimeError("copied evidence manifest hash does not match the review request")

    handoff = workspace / ".triad-review"
    handoff.mkdir()
    for relative in (
        "request.json",
        f"packets/{role.lower()}.md",
        f"templates/{role.lower()}.json",
    ):
        source = cycle / relative
        destination = handoff / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    return workspace


def prompt(workspace: Path, role: str) -> str:
    packet = workspace / ".triad-review" / "packets" / f"{role.lower()}.md"
    template = workspace / ".triad-review" / "templates" / f"{role.lower()}.json"
    request = workspace / ".triad-review" / "request.json"
    # Avoid shell interpolation: paths are supplied as plain model input.
    return (
        f"You are the independent read-only {role} reviewer. This is a clean snapshot of the exact bound revision. "
        f"Read {packet}, {template}, and {request}. Inspect only the bound evidence directory, milestone_registry.json, "
        "project_state.json, and the verifier files named by the request. Do not run git diff, search historical runs, inspect the "
        "parent repository, edit, commit, deploy, sign off, prove, or read another review. Return only a completed "
        "JSON object that exactly follows the supplied template and output schema."
    )


def review_role(cycle: Path, role: str, attempts: int) -> tuple[bool, list[dict[str, Any]]]:
    submissions = cycle / "submissions"; submissions.mkdir(exist_ok=True)
    events: list[dict[str, Any]] = []
    try:
        workspace = create_review_workspace(cycle, role)
    except (OSError, RuntimeError, json.JSONDecodeError) as error:
        return False, [{
            "role": role,
            "attempt": 0,
            "exit_code": "SNAPSHOT_FAILURE",
            "error": str(error),
        }]
    schema = workspace / "config" / "schemas" / "triad-review.schema.json"
    for number in range(1, attempts + 1):
        raw = submissions / f"{role.lower()}.attempt-{number}.raw.json"
        attempt_dir = cycle / "attempt-output" / role.lower()
        command = [
            "codex", "exec", "--ignore-user-config", "--ephemeral", "-m", "gpt-5.6-luna", "-s", "read-only", "-C", str(workspace),
            "--output-schema", str(schema), "-o", str(raw), prompt(workspace, role),
        ]
        try:
            result = subprocess.run(command, cwd=workspace, text=True, capture_output=True, check=False, timeout=REVIEW_TIMEOUT_SECONDS)
            event: dict[str, Any] = {
                "role": role,
                "attempt": number,
                "exit_code": result.returncode,
                "workspace": _relative(workspace),
                "raw": _relative(raw) if raw.is_file() else None,
                "raw_sha256": hashlib.sha256(raw.read_bytes()).hexdigest() if raw.is_file() else None,
                "stdout": _write_raw(attempt_dir / f"attempt-{number}.stdout.txt", result.stdout),
                "stderr": _write_raw(attempt_dir / f"attempt-{number}.stderr.txt", result.stderr),
            }
        except subprocess.TimeoutExpired as error:
            event = {
                "role": role,
                "attempt": number,
                "exit_code": 124,
                "workspace": _relative(workspace),
                "raw": _relative(raw) if raw.is_file() else None,
                "raw_sha256": hashlib.sha256(raw.read_bytes()).hexdigest() if raw.is_file() else None,
                "stdout": _write_raw(attempt_dir / f"attempt-{number}.stdout.txt", error.stdout),
                "stderr": _write_raw(attempt_dir / f"attempt-{number}.stderr.txt", error.stderr),
                "error": f"Codex reviewer timed out after {REVIEW_TIMEOUT_SECONDS}s",
            }
            events.append(event)
            continue
        if result.returncode == 0 and raw.is_file():
            # The schema validator deliberately accepts only the role's
            # canonical submission path.  Stage the untrusted raw response
            # there only for validation, then remove it again on any failure.
            candidate = submissions / role_filename(role)
            shutil.copyfile(raw, candidate)
            validation = run([*TRIAD, "validate-review", "--cycle", str(cycle), "--review", str(candidate)])
            event["validation"] = validation.stdout.strip() or validation.stderr.strip()
            if validation.returncode == 0:
                events.append(event)
                shutil.rmtree(workspace)
                return True, events
            candidate.unlink(missing_ok=True)
        events.append(event)
    shutil.rmtree(workspace)
    return False, events


def write_attempts(cycle: Path, events: list[dict[str, Any]]) -> None:
    (cycle / "review-runner-attempts.json").write_text(json.dumps(events, indent=2) + "\n")


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
        events.extend(role_events); write_attempts(cycle, events)
        if not ok:
            passed = False
            break
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
