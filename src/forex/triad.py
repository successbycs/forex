"""Read-only Triad-plus-domain review packets and deterministic synthesis."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
import yaml

from forex.milestones import (
    GovernanceError,
    MilestoneStore,
    atomic_write_json,
    configuration_fingerprint,
    git_revision,
    material_worktree_changes,
    sha256_file,
    parse_utc,
    utc_now,
    validate_evidence_bundle,
)


class TriadError(GovernanceError):
    """A review packet, review, binding, or recommendation is invalid."""


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _schema_validate(value: dict[str, Any], schema_path: Path, label: str) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(value),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        detail = "; ".join(
            f"{'.'.join(map(str, error.absolute_path)) or '<root>'}: {error.message}" for error in errors
        )
        raise TriadError(f"{label} failed schema validation: {detail}")


def load_policy(root: Path) -> dict[str, Any]:
    path = root / "config" / "triad.yaml"
    try:
        policy = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise TriadError(f"cannot load Triad policy: {exc}") from exc
    if not isinstance(policy, dict):
        raise TriadError("Triad policy must be a mapping")
    _schema_validate(policy, root / "config" / "schemas" / "triad.schema.json", "Triad policy")
    roles = [reviewer["role"] for reviewer in policy["reviewers"]]
    if len(roles) != len(set(roles)):
        raise TriadError("Triad reviewer roles must be unique")
    for reviewer in policy["reviewers"]:
        prompt = (root / reviewer["prompt_path"]).resolve()
        if not prompt.is_relative_to(root) or not prompt.is_file():
            raise TriadError(f"missing or unsafe role prompt: {reviewer['prompt_path']}")
    return policy


def _verifier_paths(root: Path, milestone: dict[str, Any]) -> list[str]:
    candidates = {
        "src/forex/milestones.py",
        "src/forex/t480_dependency.py",
        "src/forex/triad.py",
        "config/schemas/evidence-manifest.schema.json",
        "config/schemas/triad-review.schema.json",
        "config/schemas/triad-recommendation.schema.json",
    }
    commands = milestone["verification_commands"] + [
        {"argv": milestone["real_world_proof"]["verifier_command"]}
    ]
    for command in commands:
        for argument in command["argv"]:
            if argument == "{bundle}":
                continue
            path = root / argument
            if path.is_file():
                candidates.add(argument)
    result = sorted(candidates)
    for relative in result:
        if not (root / relative).is_file():
            raise TriadError(f"verifier input is missing: {relative}")
    return result


def verifier_fingerprint(root: Path, paths: list[str]) -> str:
    digest = hashlib.sha256()
    for relative in paths:
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update((root / relative).read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def _request_binding(request: dict[str, Any], *, request_sha256: str | None = None) -> dict[str, str]:
    return {
        "request_sha256": request_sha256 or canonical_sha256(request),
        "git_revision": request["git_revision"],
        "configuration_fingerprint": request["configuration_fingerprint"],
        "evidence_manifest_sha256": request["evidence_manifest_sha256"],
        "verifier_fingerprint": request["verifier_fingerprint"],
        "milestone_contract_sha256": request["milestone_contract_sha256"],
    }


def prepare_review(root: Path, milestone_id: str) -> Path:
    root = root.resolve()
    store = MilestoneStore(root)
    store.validate()
    policy = load_policy(root)
    milestone = store.milestone(milestone_id)
    state = store.milestone_state(milestone_id)
    verification = state.get("verification")
    if not verification or not verification.get("passed"):
        raise TriadError("current milestone verification must pass before review preparation")
    if not state["evidence"]:
        raise TriadError("current real-world evidence is required before review preparation")
    evidence_record = state["evidence"][-1]
    evidence_path = root / evidence_record["manifest_path"]
    manifest = validate_evidence_bundle(root, store.state, milestone, evidence_path)
    revision = git_revision(root)
    fingerprint = configuration_fingerprint(root, store.state)
    if revision == "UNBORN" or manifest["dirty_worktree"]:
        raise TriadError("Triad review requires evidence from a clean immutable revision")
    changes = material_worktree_changes(root)
    if changes:
        raise TriadError(f"Triad review requires a materially clean worktree: {changes}")
    if verification.get("git_revision") != revision or manifest["git_revision"] != revision:
        raise TriadError("verification, evidence, and current Git revision do not match")
    if verification.get("configuration_fingerprint") != fingerprint:
        raise TriadError("verification configuration fingerprint is stale")
    paths = _verifier_paths(root, milestone)
    created_at = utc_now()
    cycle_id = f"{milestone_id}-{created_at.replace(':', '').replace('-', '')}-{revision[:8]}"
    cycle = root / "runs" / "triad" / milestone_id / cycle_id
    (cycle / "packets").mkdir(parents=True, exist_ok=False)
    (cycle / "templates").mkdir()
    (cycle / "submissions").mkdir()
    required_roles = [reviewer["role"] for reviewer in policy["reviewers"] if reviewer["required"]]
    request = {
        "schema_version": "forex.triad-request.v1",
        "review_cycle_id": cycle_id,
        "milestone_id": milestone_id,
        "created_at": created_at,
        "git_revision": revision,
        "configuration_fingerprint": fingerprint,
        "evidence_manifest_path": evidence_record["manifest_path"],
        "evidence_manifest_sha256": sha256_file(evidence_path),
        "verification_recorded_at": verification["recorded_at"],
        "verifier_paths": paths,
        "verifier_fingerprint": verifier_fingerprint(root, paths),
        "milestone_contract_sha256": canonical_sha256(milestone),
        "required_roles": required_roles,
        "role_packets": {role: f"packets/{role.lower()}.md" for role in required_roles},
    }
    _schema_validate(
        request, root / "config" / "schemas" / "triad-review-request.schema.json", "Triad request"
    )
    atomic_write_json(cycle / "request.json", request)
    binding = _request_binding(request, request_sha256=sha256_file(cycle / "request.json"))
    criterion_by_id = {criterion["id"]: criterion for criterion in milestone["acceptance_criteria"]}
    for reviewer in policy["reviewers"]:
        role = reviewer["role"]
        assigned = reviewer["m0_criteria"] if milestone_id == "M0" else list(criterion_by_id)
        unknown = set(assigned) - criterion_by_id.keys()
        if unknown:
            raise TriadError(f"{role} has unknown assigned criteria: {sorted(unknown)}")
        prompt_path = root / reviewer["prompt_path"]
        role_prompt_sha = sha256_file(prompt_path)
        packet = "\n".join(
            [
                f"# {reviewer['display_name']} — {milestone_id} independent review packet",
                "",
                prompt_path.read_text(encoding="utf-8"),
                "",
                "## Immutable binding",
                "",
                f"- Review cycle: `{cycle_id}`",
                f"- Request SHA-256: `{binding['request_sha256']}`",
                f"- Git revision: `{revision}`",
                f"- Configuration fingerprint: `{fingerprint}`",
                f"- Evidence manifest: `{evidence_record['manifest_path']}`",
                f"- Evidence manifest SHA-256: `{binding['evidence_manifest_sha256']}`",
                f"- Verifier fingerprint: `{binding['verifier_fingerprint']}`",
                f"- Milestone contract SHA-256: `{binding['milestone_contract_sha256']}`",
                f"- Role prompt SHA-256: `{role_prompt_sha}`",
                "",
                "## Assigned acceptance criteria",
                "",
                *[f"- `{criterion_id}` — {criterion_by_id[criterion_id]['description']}" for criterion_id in assigned],
                "",
                "Inspect the committed repository and raw evidence directly. Fill the generated JSON template and save it under `submissions/` without reading another review.",
                "",
            ]
        )
        (cycle / request["role_packets"][role]).write_text(packet, encoding="utf-8")
        template = {
            "schema_version": "forex.triad-review.v1",
            "review_cycle_id": cycle_id,
            "milestone_id": milestone_id,
            "role": role,
            "reviewer": {"kind": "AI", "provider": "FILL_ME", "model": "FILL_ME", "session_id": "FILL_ME"},
            "binding": {**binding, "role_prompt_sha256": role_prompt_sha},
            "verdict": "ABSTAIN",
            "summary": "FILL_ME",
            "criteria_assessments": [
                {
                    "criterion_id": criterion_id,
                    "result": "NOT_REVIEWED",
                    "rationale": "FILL_ME",
                    "evidence_refs": ["FILL_ME"],
                }
                for criterion_id in assigned
            ],
            "findings": [],
            "limitations": [],
            "attestations": {
                "read_only": True,
                "independent_context": True,
                "raw_evidence_reviewed": True,
                "did_not_modify_repository": True,
                "no_other_review_seen_before_verdict": True,
            },
            "reviewed_at": created_at,
        }
        atomic_write_json(cycle / "templates" / f"{role.lower()}.json", template)
    return cycle


def load_request(root: Path, cycle: Path) -> dict[str, Any]:
    request = json.loads((cycle / "request.json").read_text(encoding="utf-8"))
    _schema_validate(
        request, root / "config" / "schemas" / "triad-review-request.schema.json", "Triad request"
    )
    return request


def validate_review(root: Path, cycle: Path, review_path: Path) -> dict[str, Any]:
    root = root.resolve()
    cycle = cycle.resolve()
    request = load_request(root, cycle)
    policy = load_policy(root)
    review = json.loads(review_path.read_text(encoding="utf-8"))
    _schema_validate(review, root / "config" / "schemas" / "triad-review.schema.json", "Triad review")
    if "FILL_ME" in json.dumps(review, sort_keys=True):
        raise TriadError("review contains unfilled template values")
    if review["review_cycle_id"] != request["review_cycle_id"]:
        raise TriadError("review cycle identifier does not match the request")
    if review["milestone_id"] != request["milestone_id"]:
        raise TriadError("review milestone identifier does not match the request")
    policies = {item["role"]: item for item in policy["reviewers"]}
    role = review["role"]
    if role not in policies or role not in request["required_roles"]:
        raise TriadError(f"unexpected reviewer role: {role}")
    expected_binding = _request_binding(request, request_sha256=sha256_file(cycle / "request.json"))
    for field, expected in expected_binding.items():
        if review["binding"].get(field) != expected:
            raise TriadError(f"{role}: binding mismatch for {field}")
    prompt_path = root / policies[role]["prompt_path"]
    if review["binding"]["role_prompt_sha256"] != sha256_file(prompt_path):
        raise TriadError(f"{role}: role prompt fingerprint mismatch")
    milestone = MilestoneStore(root).milestone(request["milestone_id"])
    expected_criteria = set(
        policies[role]["m0_criteria"] if request["milestone_id"] == "M0" else [c["id"] for c in milestone["acceptance_criteria"]]
    )
    assessments = review["criteria_assessments"]
    actual_criteria = [assessment["criterion_id"] for assessment in assessments]
    if len(actual_criteria) != len(set(actual_criteria)) or set(actual_criteria) != expected_criteria:
        raise TriadError(f"{role}: criteria assessments must exactly match assigned criteria")
    if review["verdict"] in {"PASS", "PASS_WITH_FINDINGS"} and any(
        assessment["result"] != "PASS" for assessment in assessments
    ):
        raise TriadError(f"{role}: passing verdict requires all assigned criteria to PASS")
    if review["verdict"] == "PASS_WITH_FINDINGS" and not review["findings"]:
        raise TriadError(f"{role}: PASS_WITH_FINDINGS requires at least one finding")
    if any(assessment["result"] == "FAIL" for assessment in assessments) and review["verdict"] != "FAIL":
        raise TriadError(f"{role}: a failed criterion requires FAIL verdict")
    created_at = parse_utc(request["created_at"])
    reviewed_at = parse_utc(review["reviewed_at"])
    if reviewed_at < created_at:
        raise TriadError(f"{role}: review timestamp predates its request")
    for assessment in assessments:
        for reference in assessment["evidence_refs"]:
            candidate = (root / reference.split("#", 1)[0]).resolve()
            if not candidate.is_relative_to(root) or not candidate.exists():
                raise TriadError(f"{role}: missing or unsafe evidence reference: {reference}")
    for finding in review["findings"]:
        for reference in finding["evidence_refs"]:
            candidate = (root / reference.split("#", 1)[0]).resolve()
            if not candidate.is_relative_to(root) or not candidate.exists():
                raise TriadError(f"{role}: missing or unsafe finding reference: {reference}")
    return review


def render_review_summary(recommendation: dict[str, Any]) -> str:
    """Render the canonical human-facing form of a recommendation."""
    supports_completion = recommendation["recommendation"] == "RECOMMEND_COMPLETE"
    decision = (
        "SUPPORTED BY TRIAD — eligible for human approval"
        if supports_completion
        else "NOT SUPPORTED BY TRIAD — human approval is blocked"
    )
    role_positions = {
        "PASS": "SUPPORTS COMPLETION",
        "PASS_WITH_FINDINGS": "SUPPORTS WITH FINDINGS",
        "FAIL": "DOES NOT SUPPORT COMPLETION",
        "ABSTAIN": "NO RECOMMENDATION",
    }
    role_labels = {
        "AI_ENGINEER": "AI Engineer",
        "SOLUTION_ARCHITECT": "Solution Architect",
        "SENIOR_SOFTWARE_DEVELOPER": "Senior Software Developer",
        "FINANCIAL_DOMAIN_EXPERT": "Financial Domain Expert",
    }
    lines = [
        f"# {recommendation['milestone_id']} Triad plus domain review summary",
        "",
        "## Approval recommendation",
        "",
        f"**Overall status: {decision}**",
        "",
        f"- Triad recommendation: `{recommendation['recommendation']}`",
        f"- Review cycle: `{recommendation['review_cycle_id']}`",
        f"- Generated at: `{recommendation['generated_at']}`",
        "- Final human decision required: `YES`",
        "",
        "The reviewers recommend whether the evidence supports completion; they do not approve or close the milestone. Only the human operator can make the final decision.",
        "",
        "## Reviewer positions",
        "",
    ]
    for review in recommendation["reviews"]:
        role = review["role"]
        verdict = review["verdict"]
        submission = f"submissions/{role.lower()}.json"
        lines.extend(
            [
                f"### {role_labels.get(role, role.replace('_', ' ').title())}",
                "",
                f"- Position: **{role_positions.get(verdict, verdict)}**",
                f"- Verdict: `{verdict}`",
                f"- Detailed submission: [{submission}]({submission})",
                f"- Summary: {review['summary']}",
                "",
            ]
        )
    lines.extend(["## Blocking reasons", ""])
    if recommendation["blocking_reasons"]:
        lines.extend(f"- {reason}" for reason in recommendation["blocking_reasons"])
    else:
        lines.append("- None.")
    lines.extend(["", "## Non-blocking observations", ""])
    if recommendation["observations"]:
        lines.extend(f"- {observation}" for observation in recommendation["observations"])
    else:
        lines.append("- None.")
    lines.extend(["", "## Human decision guidance", ""])
    if supports_completion:
        lines.append(
            "The Triad supports completion. The human operator must still inspect the evidence, findings and limitations before explicitly approving or rejecting the milestone."
        )
    else:
        lines.append(
            "Do not approve or close this milestone. Resolve every blocking reason, capture fresh bound evidence where required, and run a new isolated Triad plus domain review cycle."
        )
    lines.extend(
        [
            "",
            "## Immutable binding",
            "",
            f"- Git revision: `{recommendation['binding']['git_revision']}`",
            f"- Configuration fingerprint: `{recommendation['binding']['configuration_fingerprint']}`",
            f"- Evidence manifest SHA-256: `{recommendation['binding']['evidence_manifest_sha256']}`",
            f"- Verifier fingerprint: `{recommendation['binding']['verifier_fingerprint']}`",
            f"- Milestone contract SHA-256: `{recommendation['binding']['milestone_contract_sha256']}`",
            "",
            "Machine-readable source: [recommendation.json](recommendation.json)",
            "",
        ]
    )
    return "\n".join(lines)


def write_review_summary(
    cycle: Path, recommendation: dict[str, Any], filename: str = "review-summary.md"
) -> Path:
    """Write the human-facing Triad decision without changing the signed JSON result."""
    cycle = cycle.resolve()
    path = cycle / filename
    if path.parent != cycle or path.suffix != ".md":
        raise TriadError(f"unsafe human summary filename: {filename}")
    path.write_text(render_review_summary(recommendation), encoding="utf-8")
    return path


def review_summary_drift(
    cycle: Path, recommendation: dict[str, Any], filename: str
) -> list[str]:
    summary_path = cycle.resolve() / filename
    if not summary_path.is_file():
        return ["required human-readable Triad summary is missing"]
    if summary_path.read_text(encoding="utf-8") != render_review_summary(recommendation):
        return ["human-readable Triad summary is stale or modified"]
    return []


def synthesize(root: Path, cycle: Path) -> Path:
    root = root.resolve()
    cycle = cycle.resolve()
    request = load_request(root, cycle)
    policy = load_policy(root)
    blocking: list[str] = []
    observations: list[str] = []
    review_summaries: list[dict[str, Any]] = []
    sessions: set[str] = set()
    for role in request["required_roles"]:
        review_path = cycle / "submissions" / f"{role.lower()}.json"
        if not review_path.is_file():
            blocking.append(f"missing required review: {role}")
            continue
        try:
            review = validate_review(root, cycle, review_path)
        except (TriadError, json.JSONDecodeError) as exc:
            blocking.append(f"invalid {role} review: {exc}")
            continue
        session = review["reviewer"]["session_id"]
        if session in sessions:
            blocking.append(f"reviewer session reused across roles: {session}")
        sessions.add(session)
        if review["verdict"] in policy["gate"]["blocking_verdicts"]:
            blocking.append(f"{role} verdict is {review['verdict']}")
        if review["verdict"] == "PASS_WITH_FINDINGS":
            observations.append(f"{role}: {review['summary']}")
        for finding in review["findings"]:
            if finding["status"] == "OPEN" and finding["severity"] in policy["gate"]["blocking_open_severities"]:
                blocking.append(f"{role} open {finding['severity']} finding {finding['finding_id']}: {finding['title']}")
            elif finding["status"] != "RESOLVED":
                observations.append(f"{role} {finding['severity']} {finding['finding_id']}: {finding['title']}")
        review_summaries.append(
            {
                "role": role,
                "verdict": review["verdict"],
                "reviewer": review["reviewer"],
                "review_sha256": sha256_file(review_path),
                "summary": review["summary"],
            }
        )
    binding = _request_binding(request)
    recommendation = {
        "schema_version": "forex.triad-recommendation.v1",
        "review_cycle_id": request["review_cycle_id"],
        "milestone_id": request["milestone_id"],
        "generated_at": utc_now(),
        "binding": binding,
        "reviews": review_summaries,
        "recommendation": "DO_NOT_COMPLETE" if blocking else policy["gate"]["completion_recommendation"],
        "blocking_reasons": blocking,
        "observations": observations,
        "human_decision_required": True,
    }
    _schema_validate(
        recommendation,
        root / "config" / "schemas" / "triad-recommendation.schema.json",
        "Triad recommendation",
    )
    path = cycle / "recommendation.json"
    atomic_write_json(path, recommendation)
    write_review_summary(cycle, recommendation, policy["gate"]["human_summary_filename"])
    return path


def assess_recommendation(root: Path, recommendation_path: Path) -> list[str]:
    root = root.resolve()
    recommendation_path = recommendation_path.resolve()
    recommendation = json.loads(recommendation_path.read_text(encoding="utf-8"))
    _schema_validate(
        recommendation,
        root / "config" / "schemas" / "triad-recommendation.schema.json",
        "Triad recommendation",
    )
    cycle = recommendation_path.parent
    request = load_request(root, cycle)
    policy = load_policy(root)
    expected = _request_binding(request)
    drift: list[str] = []
    for field, value in expected.items():
        if recommendation["binding"].get(field) != value:
            drift.append(f"recommendation binding mismatch: {field}")
    store = MilestoneStore(root)
    milestone = store.milestone(recommendation["milestone_id"])
    state = store.milestone_state(recommendation["milestone_id"])
    current_evidence_sha = state["evidence"][-1]["manifest_sha256"] if state["evidence"] else None
    paths = _verifier_paths(root, milestone)
    current = {
        "git_revision": git_revision(root),
        "configuration_fingerprint": configuration_fingerprint(root, store.state),
        "evidence_manifest_sha256": current_evidence_sha,
        "verifier_fingerprint": verifier_fingerprint(root, paths),
        "milestone_contract_sha256": canonical_sha256(milestone),
    }
    for field, value in current.items():
        if recommendation["binding"].get(field) != value:
            drift.append(f"current milestone drift: {field}")
    changes = material_worktree_changes(root)
    if changes:
        drift.append(f"material worktree drift: {changes}")
    for summary in recommendation["reviews"]:
        review_path = cycle / "submissions" / f"{summary.get('role', '').lower()}.json"
        if not review_path.is_file() or sha256_file(review_path) != summary.get("review_sha256"):
            drift.append(f"review artifact drift: {summary.get('role', '<unknown>')}")
    drift.extend(
        review_summary_drift(
            cycle, recommendation, policy["gate"]["human_summary_filename"]
        )
    )
    if recommendation["recommendation"] != "RECOMMEND_COMPLETE":
        drift.append("Triad does not recommend completion")
    return drift


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Forex Triad plus domain review gate")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate-policy")
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--id", required=True)
    validate = commands.add_parser("validate-review")
    validate.add_argument("--cycle", type=Path, required=True)
    validate.add_argument("--review", type=Path, required=True)
    recommend = commands.add_parser("recommend")
    recommend.add_argument("--cycle", type=Path, required=True)
    summary = commands.add_parser("summary")
    summary.add_argument("--recommendation", type=Path, required=True)
    assess = commands.add_parser("assess")
    assess.add_argument("--recommendation", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = args.root.resolve()
    try:
        if args.command == "validate-policy":
            policy = load_policy(root)
            print(f"Triad policy valid: {len(policy['reviewers'])} required roles")
        elif args.command == "prepare":
            print(prepare_review(root, args.id))
        elif args.command == "validate-review":
            review = validate_review(root, args.cycle, args.review)
            print(f"{review['role']} review valid: {review['verdict']}")
        elif args.command == "recommend":
            path = synthesize(root, args.cycle)
            recommendation = json.loads(path.read_text(encoding="utf-8"))
            print(json.dumps({"path": str(path), **recommendation}, indent=2))
            return 0 if recommendation["recommendation"] == "RECOMMEND_COMPLETE" else 3
        elif args.command == "summary":
            recommendation_path = args.recommendation.resolve()
            recommendation = json.loads(recommendation_path.read_text(encoding="utf-8"))
            _schema_validate(
                recommendation,
                root / "config" / "schemas" / "triad-recommendation.schema.json",
                "Triad recommendation",
            )
            policy = load_policy(root)
            print(
                write_review_summary(
                    recommendation_path.parent,
                    recommendation,
                    policy["gate"]["human_summary_filename"],
                )
            )
        elif args.command == "assess":
            drift = assess_recommendation(root, args.recommendation)
            print(json.dumps({"status": "HEALTHY" if not drift else "DRIFTED", "reasons": drift}, indent=2))
            return 0 if not drift else 3
    except (TriadError, GovernanceError, json.JSONDecodeError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
