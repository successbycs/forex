"""Bound implementation-readiness review handoff.

This is intentionally separate from the evidence-bound completion Triad.  It
can send an implementation back for fixes or allow it to proceed to evidence;
it cannot approve or prove a milestone.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from forex.milestones import (
    GovernanceError,
    MilestoneStore,
    _safe_relative,
    configuration_fingerprint,
    git_revision,
    material_worktree_changes,
    parse_utc,
    sha256_file,
    utc_now,
)


MAX_REVIEW_CYCLES = 3
REQUEST_SCHEMA = "config/schemas/governance-review-request.schema.json"
RESULT_SCHEMA = "config/schemas/governance-review-result.schema.json"


class ReviewHandoffError(GovernanceError):
    """A review handoff request or result is invalid."""


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _validate(value: dict[str, Any], root: Path, schema: str, label: str) -> None:
    definition = json.loads((root / schema).read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(definition, format_checker=FormatChecker()).iter_errors(value),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        detail = "; ".join(
            f"{'.'.join(map(str, error.absolute_path)) or '<root>'}: {error.message}" for error in errors
        )
        raise ReviewHandoffError(f"{label} failed schema validation: {detail}")


def request_root(root: Path, milestone_id: str) -> Path:
    return root.resolve() / "runs" / "review_requests" / milestone_id


def _requests(root: Path, milestone_id: str) -> list[tuple[Path, dict[str, Any]]]:
    records: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(request_root(root, milestone_id).glob("*.request.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            _validate(value, root, REQUEST_SCHEMA, "review request")
            records.append((path, value))
        except (OSError, json.JSONDecodeError, ReviewHandoffError) as exc:
            raise ReviewHandoffError(f"invalid retained review request: {path}: {exc}") from exc
    return records


def _require_requestable(store: MilestoneStore, milestone_id: str) -> tuple[dict[str, Any], dict[str, Any], str, str]:
    store.validate()
    if store.state.get("current_milestone") != milestone_id:
        raise ReviewHandoffError("implementation review requires the current active milestone")
    milestone = store.milestone(milestone_id)
    state = store.milestone_state(milestone_id)
    if state["status"] != "AWAITING_REAL_WORLD_PROOF" or not state.get("implementation_finished_at"):
        raise ReviewHandoffError("implementation review requires finished implementation awaiting real-world proof")
    verification = state.get("verification")
    revision = git_revision(store.root)
    fingerprint = configuration_fingerprint(store.root, store.state)
    if revision == "UNBORN" or material_worktree_changes(store.root):
        raise ReviewHandoffError("implementation review requires a clean committed worktree")
    if not verification or not verification.get("passed"):
        raise ReviewHandoffError("implementation review requires current passing verification")
    if verification.get("git_revision") != revision or verification.get("configuration_fingerprint") != fingerprint:
        raise ReviewHandoffError("implementation verification is stale")
    if state.get("blockers"):
        raise ReviewHandoffError("implementation review cannot start with unresolved blockers")
    return milestone, state, revision, fingerprint


def create_request(root: Path, milestone_id: str, builder_report: Path) -> Path:
    store = MilestoneStore(root.resolve())
    milestone, state, revision, fingerprint = _require_requestable(store, milestone_id)
    report_path = builder_report.resolve()
    report_relative = _safe_relative(store.root, report_path, "Builder report")
    if not report_path.is_file() or report_path.stat().st_size == 0:
        raise ReviewHandoffError("Builder report must be a non-empty repository file")
    prior = _requests(store.root, milestone_id)
    if len(prior) >= MAX_REVIEW_CYCLES:
        raise ReviewHandoffError(f"review cycle cap reached ({MAX_REVIEW_CYCLES})")
    if any(record["git_revision"] == revision and record["configuration_fingerprint"] == fingerprint for _, record in prior):
        raise ReviewHandoffError("a review request already exists for this revision and configuration")
    cycle = len(prior) + 1
    created_at = utc_now()
    request_id = f"{milestone_id}-{created_at.replace(':', '').replace('-', '')}-{revision[:8]}-R{cycle}"
    request = {
        "schema_version": "forex.governance-review-request.v1",
        "request_id": request_id,
        "milestone_id": milestone_id,
        "purpose": "IMPLEMENTATION_READINESS",
        "created_at": created_at,
        "git_revision": revision,
        "configuration_fingerprint": fingerprint,
        "milestone_contract_sha256": canonical_sha256(milestone),
        "verification_recorded_at": state["verification"]["recorded_at"],
        "builder_report_path": report_relative,
        "builder_report_sha256": sha256_file(report_path),
        "review_cycle": cycle,
    }
    _validate(request, store.root, REQUEST_SCHEMA, "review request")
    destination = request_root(store.root, milestone_id) / f"{request_id}.request.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(request, indent=2) + "\n", encoding="utf-8")
    state["review_workflow"] = {
        "cycle": cycle,
        "latest_request_id": request_id,
        "latest_request_path": destination.relative_to(store.root).as_posix(),
        "latest_request_sha256": sha256_file(destination),
        "outcome": "REQUESTED",
    }
    store.event(milestone_id, "IMPLEMENTATION_REVIEW_REQUESTED", {"request_id": request_id, "cycle": cycle})
    store.save()
    return destination


def load_request(root: Path, request_path: Path) -> dict[str, Any]:
    path = request_path.resolve()
    expected = (root.resolve() / "runs" / "review_requests").resolve()
    if not path.is_relative_to(expected) or not path.name.endswith(".request.json"):
        raise ReviewHandoffError("review request must be beneath runs/review_requests")
    value = json.loads(path.read_text(encoding="utf-8"))
    _validate(value, root.resolve(), REQUEST_SCHEMA, "review request")
    return value


def validate_result(root: Path, request_path: Path, result_path: Path) -> dict[str, Any]:
    root = root.resolve()
    request = load_request(root, request_path)
    result = json.loads(result_path.read_text(encoding="utf-8"))
    _validate(result, root, RESULT_SCHEMA, "review result")
    expected = {
        "request_id": request["request_id"],
        "milestone_id": request["milestone_id"],
        "request_sha256": sha256_file(request_path.resolve()),
        "git_revision": request["git_revision"],
        "configuration_fingerprint": request["configuration_fingerprint"],
        "milestone_contract_sha256": request["milestone_contract_sha256"],
        "review_cycle": request["review_cycle"],
    }
    for field, value in expected.items():
        if result.get(field) != value:
            raise ReviewHandoffError(f"review result binding mismatch: {field}")
    parse_utc(result["reviewed_at"])
    if result["outcome"] in {"CHANGES_REQUIRED", "BLOCKED"} and not result["required_findings"]:
        raise ReviewHandoffError(f"{result['outcome']} requires at least one required finding")
    if result["outcome"] == "READY_FOR_EVIDENCE" and result["required_findings"]:
        raise ReviewHandoffError("READY_FOR_EVIDENCE cannot contain required findings")
    return result


def reviewer_brief(root: Path, request_path: Path) -> str:
    request = load_request(root.resolve(), request_path)
    return "\n".join(
        [
            "You are the Forex implementation-readiness Reviewer.",
            "Remain read-only. Do not modify repository files, state, evidence, Git, infrastructure, or databases.",
            "Read docs/governance/reviewer.md, AGENTS.md, and this bound request:",
            str(request_path.resolve()),
            "Return only JSON matching config/schemas/governance-review-result.schema.json.",
            "Use the exact request binding values and one outcome: CHANGES_REQUIRED, BLOCKED, or READY_FOR_EVIDENCE.",
            "READY_FOR_EVIDENCE is not completion or a Triad RECOMMEND_COMPLETE.",
            f"Review request ID: {request['request_id']}",
        ]
    )


def record_result(root: Path, request_path: Path, result_path: Path) -> Path:
    store = MilestoneStore(root.resolve())
    store.validate()
    request = load_request(store.root, request_path)
    result = validate_result(store.root, request_path, result_path)
    milestone_id = request["milestone_id"]
    state = store.milestone_state(milestone_id)
    if store.state.get("current_milestone") != milestone_id or state["status"] != "AWAITING_REAL_WORLD_PROOF":
        raise ReviewHandoffError("review result requires the current milestone awaiting real-world proof")
    if git_revision(store.root) != request["git_revision"] or configuration_fingerprint(store.root, store.state) != request["configuration_fingerprint"]:
        raise ReviewHandoffError("review result is stale against the current revision or configuration")
    if material_worktree_changes(store.root):
        raise ReviewHandoffError("review result cannot be recorded with material worktree changes")
    workflow = state.get("review_workflow") or {}
    if workflow.get("latest_request_id") != request["request_id"] or workflow.get("outcome") != "REQUESTED":
        raise ReviewHandoffError("review result is not for the current pending request")
    destination = request_root(store.root, milestone_id) / f"{request['request_id']}.result.json"
    if destination.exists():
        raise ReviewHandoffError("review result is already recorded")
    destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    finding_ids = [finding["finding_id"] for finding in result["required_findings"]]
    workflow.update({"outcome": result["outcome"], "result_path": destination.relative_to(store.root).as_posix(), "result_sha256": sha256_file(destination)})
    state["review_workflow"] = workflow
    detail = {"request_id": request["request_id"], "outcome": result["outcome"], "finding_ids": finding_ids}
    if result["outcome"] == "CHANGES_REQUIRED":
        state["blockers"].append({"reason": f"Implementation review {request['request_id']} requires fixes: {', '.join(finding_ids)}", "recorded_at": utc_now()})
        store.transition(milestone_id, "NEEDS_FIX", "IMPLEMENTATION_REVIEW_CHANGES_REQUIRED", detail)
    elif result["outcome"] == "BLOCKED":
        state["blockers"].append({"reason": f"Implementation review {request['request_id']} is blocked: {', '.join(finding_ids)}", "recorded_at": utc_now()})
        store.transition(milestone_id, "BLOCKED", "IMPLEMENTATION_REVIEW_BLOCKED", detail)
    else:
        store.event(milestone_id, "IMPLEMENTATION_REVIEW_READY_FOR_EVIDENCE", detail)
        store.save()
    return destination


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Forex implementation-readiness review handoff")
    result.add_argument("--root", type=Path, default=Path.cwd())
    commands = result.add_subparsers(dest="command", required=True)
    request = commands.add_parser("request")
    request.add_argument("--id", required=True)
    request.add_argument("--builder-report", type=Path, required=True)
    record = commands.add_parser("record")
    record.add_argument("--request", type=Path, required=True)
    record.add_argument("--result", type=Path, required=True)
    validate = commands.add_parser("validate-result")
    validate.add_argument("--request", type=Path, required=True)
    validate.add_argument("--result", type=Path, required=True)
    brief = commands.add_parser("brief")
    brief.add_argument("--request", type=Path, required=True)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "request":
            print(create_request(args.root, args.id, args.builder_report))
        elif args.command == "record":
            print(record_result(args.root, args.request, args.result))
        elif args.command == "brief":
            print(reviewer_brief(args.root, args.request))
        else:
            result = validate_result(args.root, args.request, args.result)
            print(f"review result valid: {result['outcome']}")
    except (ReviewHandoffError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0
