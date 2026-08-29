"""Human-invoked, one-shot Codex dispatcher for a bound review request."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from forex.review_handoff import ReviewHandoffError, load_request, record_result, reviewer_brief
from forex.milestones import MilestoneStore


def dispatch(root: Path, request_path: Path) -> Path:
    root = root.resolve()
    request = load_request(root, request_path)
    store = MilestoneStore(root)
    state = store.milestone_state(request["milestone_id"])
    workflow = state.get("review_workflow") or {}
    if workflow.get("latest_request_id") != request["request_id"] or workflow.get("outcome") != "REQUESTED":
        raise ReviewHandoffError("dispatcher requires the current pending review request")
    if shutil.which("codex") is None:
        raise ReviewHandoffError("Codex CLI is unavailable; use a separate human-operated Reviewer session")
    schema = root / "config/schemas/governance-review-result.schema.json"
    with tempfile.TemporaryDirectory(prefix="forex-review-dispatch-") as temporary:
        output = Path(temporary) / "review-result.json"
        command = [
            "codex", "exec", "--sandbox", "read-only", "--ephemeral", "--cd", str(root),
            "--output-schema", str(schema), "--output-last-message", str(output), "-",
        ]
        completed = subprocess.run(
            command,
            input=reviewer_brief(root, request_path),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if completed.returncode != 0:
            raise ReviewHandoffError(f"Reviewer Codex execution failed with exit code {completed.returncode}")
        if not output.is_file() or not output.read_text(encoding="utf-8").strip():
            raise ReviewHandoffError("Reviewer Codex execution produced no structured result")
        return record_result(root, request_path, output)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Dispatch one read-only Forex implementation review")
    result.add_argument("--root", type=Path, default=Path.cwd())
    result.add_argument("--request", type=Path, required=True)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        print(dispatch(args.root, args.request))
    except (ReviewHandoffError, OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0
