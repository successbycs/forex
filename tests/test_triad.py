from __future__ import annotations

import json
from pathlib import Path
import shutil

from forex.milestones import configuration_fingerprint, sha256_file, utc_now
from forex.triad import (
    _request_binding,
    canonical_sha256,
    load_policy,
    render_review_summary,
    review_summary_drift,
    synthesize,
    validate_review,
)
from forex.triad import TriadError


ROOT = Path(__file__).resolve().parents[1]


def _root(tmp_path: Path) -> Path:
    for relative in ("milestone_registry.json", "project_state.json", "runs/run_history.json"):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    state_path = tmp_path / "project_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    for relative in state["governed_configuration_paths"]:
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    shutil.copytree(ROOT / "config" / "schemas", tmp_path / "config" / "schemas")
    shutil.copytree(ROOT / "reviews", tmp_path / "reviews")
    state["configuration_fingerprint"] = configuration_fingerprint(tmp_path, state)
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    return tmp_path


def _cycle(root: Path) -> tuple[Path, dict, dict]:
    policy = load_policy(root)
    registry = json.loads((root / "milestone_registry.json").read_text(encoding="utf-8"))
    milestone = next(item for item in registry["milestones"] if item["milestone_id"] == "M0")
    cycle = root / "runs" / "triad" / "M0" / "fixture"
    (cycle / "submissions").mkdir(parents=True)
    request = {
        "schema_version": "forex.triad-request.v1",
        "review_cycle_id": "fixture",
        "milestone_id": "M0",
        "created_at": utc_now(),
        "git_revision": "a" * 40,
        "configuration_fingerprint": "sha256:" + "b" * 64,
        "evidence_manifest_path": "runs/evidence/M0/fixture/manifest.json",
        "evidence_manifest_sha256": "c" * 64,
        "verification_recorded_at": utc_now(),
        "verifier_paths": ["src/forex/milestones.py"],
        "verifier_fingerprint": "sha256:" + "d" * 64,
        "milestone_contract_sha256": canonical_sha256(milestone),
        "required_roles": [item["role"] for item in policy["reviewers"]],
        "role_packets": {item["role"]: f"packets/{item['role'].lower()}.md" for item in policy["reviewers"]},
    }
    (cycle / "request.json").write_text(json.dumps(request, indent=2) + "\n", encoding="utf-8")
    return cycle, request, policy


def _review(root: Path, request: dict, reviewer_policy: dict, *, verdict: str = "PASS", session: str | None = None) -> dict:
    role = reviewer_policy["role"]
    binding = _request_binding(
        request,
        request_sha256=sha256_file(
            root / "runs" / "triad" / "M0" / request["review_cycle_id"] / "request.json"
        ),
    )
    binding["role_prompt_sha256"] = sha256_file(root / reviewer_policy["prompt_path"])
    result = "FAIL" if verdict == "FAIL" else "PASS"
    return {
        "schema_version": "forex.triad-review.v1",
        "review_cycle_id": request["review_cycle_id"],
        "milestone_id": request["milestone_id"],
        "role": role,
        "reviewer": {
            "kind": "AI",
            "provider": "fixture-provider",
            "model": "fixture-model",
            "session_id": session or f"session-{role.lower()}",
        },
        "binding": binding,
        "verdict": verdict,
        "summary": f"{role} fixture verdict",
        "criteria_assessments": [
            {
                "criterion_id": criterion,
                "result": result,
                "rationale": "Fixture assessment with an explicit evidence reference.",
                "evidence_refs": ["milestone_registry.json"],
            }
            for criterion in reviewer_policy["m0_criteria"]
        ],
        "findings": [],
        "limitations": ["Synthetic unit-test review; not milestone evidence."],
        "attestations": {
            "read_only": True,
            "independent_context": True,
            "raw_evidence_reviewed": True,
            "did_not_modify_repository": True,
            "no_other_review_seen_before_verdict": True,
        },
        "reviewed_at": utc_now(),
    }


def _write_reviews(root: Path, cycle: Path, request: dict, policy: dict) -> None:
    for reviewer in policy["reviewers"]:
        review = _review(root, request, reviewer)
        (cycle / "submissions" / f"{reviewer['role'].lower()}.json").write_text(
            json.dumps(review, indent=2) + "\n", encoding="utf-8"
        )


def test_four_bound_passing_reviews_recommend_completion(tmp_path: Path) -> None:
    root = _root(tmp_path)
    cycle, request, policy = _cycle(root)
    _write_reviews(root, cycle, request, policy)
    result = json.loads(synthesize(root, cycle).read_text(encoding="utf-8"))
    assert result["recommendation"] == "RECOMMEND_COMPLETE"
    assert result["blocking_reasons"] == []
    assert result["human_decision_required"] is True
    summary = (cycle / "review-summary.md").read_text(encoding="utf-8")
    assert "SUPPORTED BY TRIAD — eligible for human approval" in summary
    assert "Final human decision required: `YES`" in summary
    result["recommendation"] = "DO_NOT_COMPLETE"
    assert "NOT SUPPORTED BY TRIAD" in render_review_summary(result)


def test_missing_or_modified_human_summary_is_drift(tmp_path: Path) -> None:
    root = _root(tmp_path)
    cycle, request, policy = _cycle(root)
    _write_reviews(root, cycle, request, policy)
    result = json.loads(synthesize(root, cycle).read_text(encoding="utf-8"))
    filename = policy["gate"]["human_summary_filename"]
    summary_path = cycle / filename
    assert review_summary_drift(cycle, result, filename) == []
    summary_path.write_text("modified\n", encoding="utf-8")
    assert review_summary_drift(cycle, result, filename) == [
        "human-readable Triad summary is stale or modified"
    ]
    summary_path.unlink()
    assert review_summary_drift(cycle, result, filename) == [
        "required human-readable Triad summary is missing"
    ]


def test_missing_review_blocks_completion(tmp_path: Path) -> None:
    root = _root(tmp_path)
    cycle, request, policy = _cycle(root)
    _write_reviews(root, cycle, request, policy)
    (cycle / "submissions" / "financial_domain_expert.json").unlink()
    result = json.loads(synthesize(root, cycle).read_text(encoding="utf-8"))
    assert result["recommendation"] == "DO_NOT_COMPLETE"
    assert any("missing required review" in reason for reason in result["blocking_reasons"])


def test_review_identity_must_match_the_request(tmp_path: Path) -> None:
    root = _root(tmp_path)
    cycle, request, policy = _cycle(root)
    review = _review(root, request, policy["reviewers"][0])
    review["review_cycle_id"] = "other-cycle"
    review_path = cycle / "submissions" / "ai_engineer.json"
    review_path.write_text(json.dumps(review), encoding="utf-8")
    try:
        validate_review(root, cycle, review_path)
    except TriadError as exc:
        assert "cycle identifier" in str(exc)
    else:
        raise AssertionError("mismatched review cycle identifier was accepted")
    review["review_cycle_id"] = request["review_cycle_id"]
    review["milestone_id"] = "M1"
    review_path.write_text(json.dumps(review), encoding="utf-8")
    try:
        validate_review(root, cycle, review_path)
    except TriadError as exc:
        assert "milestone identifier" in str(exc)
    else:
        raise AssertionError("mismatched review milestone identifier was accepted")


def test_one_failed_role_blocks_completion(tmp_path: Path) -> None:
    root = _root(tmp_path)
    cycle, request, policy = _cycle(root)
    _write_reviews(root, cycle, request, policy)
    reviewer = policy["reviewers"][0]
    failed = _review(root, request, reviewer, verdict="FAIL")
    (cycle / "submissions" / "ai_engineer.json").write_text(
        json.dumps(failed, indent=2) + "\n", encoding="utf-8"
    )
    result = json.loads(synthesize(root, cycle).read_text(encoding="utf-8"))
    assert result["recommendation"] == "DO_NOT_COMPLETE"
    assert any("verdict is FAIL" in reason for reason in result["blocking_reasons"])
    summary = (cycle / "review-summary.md").read_text(encoding="utf-8")
    assert "NOT SUPPORTED BY TRIAD — human approval is blocked" in summary
    assert "DOES NOT SUPPORT COMPLETION" in summary


def test_reused_reviewer_session_blocks_claimed_independence(tmp_path: Path) -> None:
    root = _root(tmp_path)
    cycle, request, policy = _cycle(root)
    for reviewer in policy["reviewers"]:
        review = _review(root, request, reviewer, session="same-session")
        (cycle / "submissions" / f"{reviewer['role'].lower()}.json").write_text(
            json.dumps(review, indent=2) + "\n", encoding="utf-8"
        )
    result = json.loads(synthesize(root, cycle).read_text(encoding="utf-8"))
    assert result["recommendation"] == "DO_NOT_COMPLETE"
    assert any("session reused" in reason for reason in result["blocking_reasons"])


def test_open_high_finding_blocks_completion(tmp_path: Path) -> None:
    root = _root(tmp_path)
    cycle, request, policy = _cycle(root)
    _write_reviews(root, cycle, request, policy)
    reviewer = policy["reviewers"][0]
    review = _review(root, request, reviewer, verdict="PASS_WITH_FINDINGS")
    review["findings"] = [
        {
            "finding_id": "AI-001",
            "severity": "HIGH",
            "status": "OPEN",
            "title": "Evidence binding concern",
            "detail": "Fixture blocking issue.",
            "evidence_refs": ["milestone_registry.json"],
            "recommended_action": "Resolve before closeout.",
        }
    ]
    (cycle / "submissions" / "ai_engineer.json").write_text(
        json.dumps(review, indent=2) + "\n", encoding="utf-8"
    )
    result = json.loads(synthesize(root, cycle).read_text(encoding="utf-8"))
    assert result["recommendation"] == "DO_NOT_COMPLETE"
    assert any("open HIGH" in reason for reason in result["blocking_reasons"])
