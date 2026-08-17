"""Evidence-gated milestone registry and execution state machine.

The registry describes what must be proven.  ``project_state.json`` records
mutable execution state.  Raw evidence remains on disk and is referenced by
hash; this module never treats a narrative assertion as proof.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from typing import Any, Iterable

from jsonschema import Draft202012Validator, FormatChecker


STATUSES = {
    "PLANNED",
    "READY",
    "IN_PROGRESS",
    "BLOCKED",
    "NEEDS_FIX",
    "AWAITING_REAL_WORLD_PROOF",
    "AWAITING_HUMAN_SIGNOFF",
    "PROVEN",
    "NEEDS_REVALIDATION",
    "SUPERSEDED",
}
DELIVERY_TYPES = {
    "FOUNDATION_ENABLING",
    "CAPABILITY_DELIVERING",
    "RESEARCH_EVALUATION",
    "OPERATIONAL_SAFETY",
}
PROOF_TYPES = {
    "REPOSITORY_EXECUTION",
    "REAL_SYSTEM_INTEGRATION",
    "OPERATIONAL_DRILL",
    "EMPIRICAL_RESEARCH",
}
REQUIRED_CONTRACT_FIELDS = {
    "milestone_id",
    "title",
    "objective",
    "delivery_type",
    "proof_type",
    "dependencies",
    "entry_conditions",
    "from_state",
    "to_state",
    "scope",
    "out_of_scope",
    "operator_config_affected",
    "expected_artifacts",
    "acceptance_criteria",
    "verification_commands",
    "real_world_proof",
    "evidence_requirements",
    "human_review_required",
    "proof_invalidated_by",
    "target_date",
    "target_date_owner",
    "notes",
}
TIMESTAMP_FIELDS = (
    "started_at",
    "implementation_finished_at",
    "verification_passed_at",
    "real_world_proof_captured_at",
    "human_signed_off_at",
    "first_proven_at",
    "proven_at",
    "last_validated_at",
)


class GovernanceError(RuntimeError):
    """A milestone contract, state, transition, or proof is invalid."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise GovernanceError(f"invalid UTC timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        raise GovernanceError(f"timestamp must include a timezone: {value!r}")
    return parsed.astimezone(timezone.utc)


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise GovernanceError(f"required file is missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise GovernanceError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise GovernanceError(f"top-level JSON value must be an object: {path}")
    return value


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def validate_against_schema(value: dict[str, Any], schema_path: Path, label: str) -> None:
    schema = load_json(schema_path)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(value), key=lambda error: list(error.absolute_path))
    if errors:
        details = "; ".join(
            f"{'.'.join(map(str, error.absolute_path)) or '<root>'}: {error.message}" for error in errors
        )
        raise GovernanceError(f"{label} failed JSON Schema validation: {details}")


@contextmanager
def repository_lock(root: Path, *, exclusive: bool):
    root.mkdir(parents=True, exist_ok=True)
    lock_path = root / ".milestone-state.lock"
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def recover_transaction(root: Path) -> None:
    journal_path = root / "runs" / ".governance-transaction.json"
    if not journal_path.exists():
        return
    journal = load_json(journal_path)
    if journal.get("schema_version") != "1.0.0" or not isinstance(journal.get("state"), dict) or not isinstance(journal.get("history"), dict):
        raise GovernanceError("invalid governance recovery journal")
    atomic_write_json(root / "project_state.json", journal["state"])
    atomic_write_json(root / "runs" / "run_history.json", journal["history"])
    journal_path.unlink()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_revision(root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else "UNBORN"


def material_worktree_changes(root: Path) -> list[str]:
    """Return current changes that can alter implementation or proof semantics."""
    result = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise GovernanceError("cannot inspect current Git worktree state")
    permitted = {"project_state.json", "runs/run_history.json"}
    return [line[3:] for line in result.stdout.splitlines() if line[3:] not in permitted]


def configuration_fingerprint(root: Path, state: dict[str, Any]) -> str:
    digest = hashlib.sha256()
    paths = state.get("governed_configuration_paths", [])
    if not isinstance(paths, list) or not paths:
        raise GovernanceError("project state must declare governed_configuration_paths")
    for relative in sorted(paths):
        if not isinstance(relative, str):
            raise GovernanceError("governed configuration paths must be strings")
        path = (root / relative).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            raise GovernanceError(f"governed configuration file is missing or unsafe: {relative}")
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def _require_string_list(value: Any, label: str, *, nonempty: bool = False) -> None:
    if not isinstance(value, list) or (nonempty and not value):
        raise GovernanceError(f"{label} must be {'a non-empty ' if nonempty else 'a '}list")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise GovernanceError(f"{label} must contain non-empty strings")


def validate_registry(registry: dict[str, Any]) -> None:
    if registry.get("schema_version") != "1.0.0":
        raise GovernanceError("unsupported milestone registry schema_version")
    if registry.get("triad_review_required") is not True:
        raise GovernanceError("the registry must require Triad-plus-domain review")
    milestones = registry.get("milestones")
    if not isinstance(milestones, list) or not milestones:
        raise GovernanceError("registry milestones must be a non-empty list")

    ids: list[str] = []
    for index, milestone in enumerate(milestones):
        if not isinstance(milestone, dict):
            raise GovernanceError(f"milestone {index} must be an object")
        missing = REQUIRED_CONTRACT_FIELDS - milestone.keys()
        if missing:
            raise GovernanceError(
                f"milestone {milestone.get('milestone_id', index)} missing fields: {sorted(missing)}"
            )
        milestone_id = milestone["milestone_id"]
        if not isinstance(milestone_id, str) or not milestone_id.startswith("M"):
            raise GovernanceError(f"invalid milestone_id: {milestone_id!r}")
        if "status" in milestone:
            raise GovernanceError(f"{milestone_id}: mutable status belongs in project_state.json")
        if milestone["delivery_type"] not in DELIVERY_TYPES:
            raise GovernanceError(f"{milestone_id}: invalid delivery_type")
        if milestone["proof_type"] not in PROOF_TYPES:
            raise GovernanceError(f"{milestone_id}: invalid proof_type")
        for field in (
            "dependencies",
            "entry_conditions",
            "scope",
            "out_of_scope",
            "operator_config_affected",
            "expected_artifacts",
            "evidence_requirements",
            "proof_invalidated_by",
        ):
            _require_string_list(milestone[field], f"{milestone_id}.{field}")
        _require_string_list(milestone["entry_conditions"], f"{milestone_id}.entry_conditions", nonempty=True)
        _require_string_list(milestone["scope"], f"{milestone_id}.scope", nonempty=True)
        _require_string_list(
            milestone["evidence_requirements"], f"{milestone_id}.evidence_requirements", nonempty=True
        )

        criteria = milestone["acceptance_criteria"]
        if not isinstance(criteria, list) or not criteria:
            raise GovernanceError(f"{milestone_id}: acceptance_criteria must be non-empty")
        criterion_ids: set[str] = set()
        for criterion in criteria:
            if not isinstance(criterion, dict) or set(criterion) != {"id", "description", "kind"}:
                raise GovernanceError(f"{milestone_id}: malformed acceptance criterion")
            if criterion["id"] in criterion_ids:
                raise GovernanceError(f"{milestone_id}: duplicate criterion {criterion['id']}")
            criterion_ids.add(criterion["id"])

        commands = milestone["verification_commands"]
        if not isinstance(commands, list) or not commands:
            raise GovernanceError(f"{milestone_id}: verification_commands must be non-empty")
        for command in commands:
            if not isinstance(command, dict) or set(command) != {"id", "argv"}:
                raise GovernanceError(f"{milestone_id}: malformed verification command")
            _require_string_list(command["argv"], f"{milestone_id}.{command['id']}.argv", nonempty=True)

        proof = milestone["real_world_proof"]
        if not isinstance(proof, dict):
            raise GovernanceError(f"{milestone_id}: real_world_proof must be an object")
        required_proof = {
            "real_world_execution",
            "surface",
            "capture_command",
            "verifier_command",
            "freshness_hours",
            "success_markers",
        }
        if set(proof) != required_proof or proof["real_world_execution"] is not True:
            raise GovernanceError(f"{milestone_id}: real-world execution contract is incomplete")
        _require_string_list(proof["capture_command"], f"{milestone_id}.capture_command", nonempty=True)
        _require_string_list(proof["verifier_command"], f"{milestone_id}.verifier_command", nonempty=True)
        _require_string_list(proof["success_markers"], f"{milestone_id}.success_markers", nonempty=True)
        if not isinstance(proof["freshness_hours"], int) or proof["freshness_hours"] <= 0:
            raise GovernanceError(f"{milestone_id}: freshness_hours must be a positive integer")
        if milestone["target_date"] is not None:
            try:
                datetime.strptime(milestone["target_date"], "%Y-%m-%d")
            except (TypeError, ValueError) as exc:
                raise GovernanceError(f"{milestone_id}: target_date must be YYYY-MM-DD or null") from exc
        work_packages = milestone.get("work_packages", [])
        package_ids = {package.get("work_package_id") for package in work_packages if isinstance(package, dict)}
        for package in work_packages:
            if not isinstance(package, dict) or set(package) != {
                "work_package_id", "title", "dependencies", "acceptance_criteria"
            }:
                raise GovernanceError(f"{milestone_id}: malformed work package")
            if set(package["dependencies"]) - package_ids:
                raise GovernanceError(f"{package['work_package_id']}: unknown work-package dependency")
            if set(package["acceptance_criteria"]) - criterion_ids:
                raise GovernanceError(f"{package['work_package_id']}: unknown acceptance criterion")
        ids.append(milestone_id)

    if len(ids) != len(set(ids)):
        raise GovernanceError("milestone IDs must be unique")
    known = set(ids)
    for milestone in milestones:
        unknown = set(milestone["dependencies"]) - known
        if unknown:
            raise GovernanceError(f"{milestone['milestone_id']}: unknown dependencies {sorted(unknown)}")
    for expected, actual in enumerate(ids):
        if actual != f"M{expected}":
            raise GovernanceError(f"registry sequence must be contiguous; expected M{expected}, found {actual}")


def validate_state(state: dict[str, Any], registry: dict[str, Any]) -> None:
    if state.get("schema_version") != "1.0.0":
        raise GovernanceError("unsupported project state schema_version")
    milestone_states = state.get("milestones")
    if not isinstance(milestone_states, dict):
        raise GovernanceError("project state milestones must be an object")
    registry_ids = [item["milestone_id"] for item in registry["milestones"]]
    if set(milestone_states) != set(registry_ids):
        raise GovernanceError("project state milestone IDs must exactly match the registry")
    for milestone_id, item in milestone_states.items():
        if not isinstance(item, dict) or item.get("status") not in STATUSES:
            raise GovernanceError(f"{milestone_id}: invalid state")
        for field in TIMESTAMP_FIELDS:
            value = item.get(field)
            if value is not None:
                parse_utc(value)
        if item["status"] == "PROVEN" and not item.get("proven_at"):
            raise GovernanceError(f"{milestone_id}: PROVEN requires proven_at")
        if item["status"] != "PROVEN" and item.get("proven_at") and item["status"] != "NEEDS_REVALIDATION":
            raise GovernanceError(f"{milestone_id}: active proven_at is invalid for {item['status']}")
        if not isinstance(item.get("checks"), dict):
            raise GovernanceError(f"{milestone_id}: checks must be an object")
        if not isinstance(item.get("evidence"), list):
            raise GovernanceError(f"{milestone_id}: evidence must be a list")
        packages = next(
            contract.get("work_packages", [])
            for contract in registry["milestones"]
            if contract["milestone_id"] == milestone_id
        )
        if packages:
            package_states = item.get("work_packages")
            if not isinstance(package_states, dict) or set(package_states) != {
                package["work_package_id"] for package in packages
            }:
                raise GovernanceError(f"{milestone_id}: work-package state must match the registry")
            for package_id, package_state in package_states.items():
                if package_state.get("status") not in {"PLANNED", "IN_PROGRESS", "VERIFIED", "NEEDS_FIX"}:
                    raise GovernanceError(f"{package_id}: invalid work-package status")
    parse_utc(state["last_updated_at"])


def validate_run_history(history: dict[str, Any]) -> None:
    if history.get("schema_version") != "1.0.0" or not isinstance(history.get("events"), list):
        raise GovernanceError("invalid run history")
    for event in history["events"]:
        if not isinstance(event, dict) or not {"event_id", "timestamp", "milestone_id", "action", "detail"} <= set(event):
            raise GovernanceError("malformed run-history event")
        parse_utc(event["timestamp"])


class MilestoneStore:
    def __init__(self, root: Path):
        self.root = root.resolve()
        recover_transaction(self.root)
        self.registry_path = self.root / "milestone_registry.json"
        self.state_path = self.root / "project_state.json"
        self.history_path = self.root / "runs" / "run_history.json"
        self.registry = load_json(self.registry_path)
        self.state = load_json(self.state_path)
        self.history = load_json(self.history_path)

    def validate(self) -> None:
        validate_registry(self.registry)
        validate_state(self.state, self.registry)
        validate_run_history(self.history)
        validate_against_schema(
            self.registry, self.root / "config/schemas/milestone-registry.schema.json", "milestone registry"
        )
        validate_against_schema(
            self.state, self.root / "config/schemas/project-state.schema.json", "project state"
        )
        validate_against_schema(
            self.history, self.root / "config/schemas/run-history.schema.json", "run history"
        )
        fingerprint = configuration_fingerprint(self.root, self.state)
        recorded = self.state.get("configuration_fingerprint")
        if recorded not in (None, fingerprint):
            # Drift is reported, not silently repaired or rewritten.
            raise GovernanceError(
                "configuration fingerprint drift; run 'forex-milestones refresh-fingerprint' "
                "and revalidate affected proof"
            )

    def milestone(self, milestone_id: str) -> dict[str, Any]:
        for item in self.registry["milestones"]:
            if item["milestone_id"] == milestone_id:
                return item
        raise GovernanceError(f"unknown milestone: {milestone_id}")

    def milestone_state(self, milestone_id: str) -> dict[str, Any]:
        self.milestone(milestone_id)
        return self.state["milestones"][milestone_id]

    def event(self, milestone_id: str, action: str, detail: dict[str, Any]) -> None:
        timestamp = utc_now()
        sequence = len(self.history["events"]) + 1
        self.history["events"].append(
            {
                "event_id": f"E{sequence:06d}",
                "timestamp": timestamp,
                "milestone_id": milestone_id,
                "action": action,
                "detail": detail,
            }
        )
        self.state["last_updated_at"] = timestamp

    def save(self) -> None:
        validate_state(self.state, self.registry)
        validate_run_history(self.history)
        journal_path = self.root / "runs" / ".governance-transaction.json"
        atomic_write_json(
            journal_path,
            {
                "schema_version": "1.0.0",
                "created_at": utc_now(),
                "state": self.state,
                "history": self.history,
            },
        )
        atomic_write_json(self.state_path, self.state)
        atomic_write_json(self.history_path, self.history)
        journal_path.unlink()

    def dependencies_proven(self, milestone: dict[str, Any]) -> list[str]:
        return [
            dependency
            for dependency in milestone["dependencies"]
            if self.milestone_state(dependency)["status"] != "PROVEN"
        ]

    def transition(self, milestone_id: str, new_status: str, action: str, detail: dict[str, Any]) -> None:
        if new_status not in STATUSES:
            raise GovernanceError(f"invalid transition target: {new_status}")
        item = self.milestone_state(milestone_id)
        previous = item["status"]
        item["status"] = new_status
        self.state["implementation_status"] = new_status
        self.event(milestone_id, action, {"from": previous, "to": new_status, **detail})
        self.save()


def _safe_relative(root: Path, path: Path, label: str) -> str:
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise GovernanceError(f"{label} must remain inside the repository: {path}")
    return resolved.relative_to(root.resolve()).as_posix()


def _replace_bundle(argv: Iterable[str], bundle: Path) -> list[str]:
    return [part.replace("{bundle}", str(bundle)) for part in argv]


def validate_evidence_bundle(
    root: Path,
    state: dict[str, Any],
    milestone: dict[str, Any],
    manifest_path: Path,
    *,
    run_external_verifier: bool = True,
) -> dict[str, Any]:
    manifest_path = manifest_path.resolve()
    evidence_root = (root / "runs" / "evidence").resolve()
    if not manifest_path.is_relative_to(evidence_root) or manifest_path.name != "manifest.json":
        raise GovernanceError("evidence manifest must be runs/evidence/.../manifest.json")
    manifest = load_json(manifest_path)
    validate_against_schema(
        manifest, root / "config" / "schemas" / "evidence-manifest.schema.json", "evidence manifest"
    )
    required = {
        "schema_version",
        "milestone_id",
        "captured_at",
        "git_revision",
        "dirty_worktree",
        "configuration_fingerprint",
        "surface",
        "operation",
        "expected_result",
        "observed_result",
        "exit_code",
        "redactions",
        "summary",
        "artifacts",
    }
    missing = required - manifest.keys()
    if missing:
        raise GovernanceError(f"evidence manifest missing fields: {sorted(missing)}")
    if manifest["schema_version"] != "1.0.0" or manifest["milestone_id"] != milestone["milestone_id"]:
        raise GovernanceError("evidence schema or milestone mismatch")
    captured_at = parse_utc(manifest["captured_at"])
    age_hours = (datetime.now(timezone.utc) - captured_at).total_seconds() / 3600
    if age_hours < -0.1 or age_hours > milestone["real_world_proof"]["freshness_hours"]:
        raise GovernanceError(f"evidence is outside the freshness window ({age_hours:.1f} hours old)")
    if manifest["configuration_fingerprint"] != configuration_fingerprint(root, state):
        raise GovernanceError("evidence configuration fingerprint does not match current configuration")
    if manifest["git_revision"] != git_revision(root):
        raise GovernanceError("evidence Git revision does not match the current revision")
    if manifest["surface"] != milestone["real_world_proof"]["surface"]:
        raise GovernanceError("evidence execution surface does not match the milestone contract")
    if manifest["exit_code"] != 0:
        raise GovernanceError("evidence operation did not exit successfully")
    if not isinstance(manifest["summary"], str) or not manifest["summary"].strip():
        raise GovernanceError("evidence requires a human-observable summary")
    artifacts = manifest["artifacts"]
    if not isinstance(artifacts, list) or not artifacts:
        raise GovernanceError("evidence manifest must list raw artifacts")
    bundle = manifest_path.parent
    combined_text = ""
    for artifact in artifacts:
        if not isinstance(artifact, dict) or set(artifact) != {"path", "sha256"}:
            raise GovernanceError("malformed evidence artifact entry")
        artifact_path = (bundle / artifact["path"]).resolve()
        if not artifact_path.is_relative_to(bundle) or not artifact_path.is_file():
            raise GovernanceError(f"missing or unsafe evidence artifact: {artifact['path']}")
        if sha256_file(artifact_path) != artifact["sha256"]:
            raise GovernanceError(f"evidence hash mismatch: {artifact['path']}")
        if artifact_path.stat().st_size <= 1_000_000:
            combined_text += artifact_path.read_text(encoding="utf-8", errors="replace")
    for marker in milestone["real_world_proof"]["success_markers"]:
        if marker not in combined_text:
            raise GovernanceError(f"evidence success marker is missing: {marker}")
    if run_external_verifier:
        command = _replace_bundle(milestone["real_world_proof"]["verifier_command"], bundle)
        result = subprocess.run(command, cwd=root, text=True, capture_output=True, check=False)
        if result.returncode:
            message = (result.stderr or result.stdout).strip()
            raise GovernanceError(f"independent evidence verifier failed: {message}")
    return manifest


def _run_commands(root: Path, milestone_id: str, commands: list[dict[str, Any]]) -> tuple[bool, list[dict[str, Any]]]:
    run_id = utc_now().replace(":", "").replace("-", "")
    output_dir = root / "runs" / "verification" / milestone_id / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    all_passed = True
    child_environment = dict(os.environ)
    child_environment["FOREX_GOVERNANCE_LOCK_HELD"] = "1"
    for command in commands:
        result = subprocess.run(
            command["argv"],
            cwd=root,
            env=child_environment,
            text=True,
            capture_output=True,
            check=False,
        )
        stdout_path = output_dir / f"{command['id']}.stdout.txt"
        stderr_path = output_dir / f"{command['id']}.stderr.txt"
        stdout_path.write_text(result.stdout, encoding="utf-8")
        stderr_path.write_text(result.stderr, encoding="utf-8")
        passed = result.returncode == 0
        all_passed = all_passed and passed
        results.append(
            {
                "id": command["id"],
                "argv": command["argv"],
                "exit_code": result.returncode,
                "passed": passed,
                "stdout": _safe_relative(root, stdout_path, "verification output"),
                "stderr": _safe_relative(root, stderr_path, "verification output"),
            }
        )
        if not passed:
            break
    return all_passed, results


def _gate_errors(store: MilestoneStore, milestone_id: str) -> list[str]:
    milestone = store.milestone(milestone_id)
    item = store.milestone_state(milestone_id)
    errors: list[str] = []
    try:
        changes = material_worktree_changes(store.root)
        if changes:
            errors.append(f"current worktree has material changes: {changes}")
    except GovernanceError as exc:
        errors.append(str(exc))
    for dependency in store.dependencies_proven(milestone):
        errors.append(f"dependency is not PROVEN: {dependency}")
    for package_id, package_state in item.get("work_packages", {}).items():
        if package_state["status"] != "VERIFIED":
            errors.append(f"work package is not VERIFIED: {package_id}")
    passed_checks = item["checks"]
    for criterion in milestone["acceptance_criteria"]:
        check = passed_checks.get(criterion["id"])
        if not check or check.get("result") != "PASS":
            errors.append(f"acceptance criterion has no passing result: {criterion['id']}")
    for relative in milestone["expected_artifacts"]:
        path = store.root / relative
        if not path.is_file() or path.stat().st_size == 0:
            errors.append(f"required artifact is missing or empty: {relative}")
    verification = item.get("verification")
    current_fingerprint = configuration_fingerprint(store.root, store.state)
    if not verification or not verification.get("passed"):
        errors.append("milestone verification has not passed")
    elif verification.get("configuration_fingerprint") != current_fingerprint:
        errors.append("verification configuration fingerprint is stale")
    elif verification.get("git_revision") != git_revision(store.root):
        errors.append("verification Git revision is stale")
    if not item["evidence"]:
        errors.append("no real-world evidence is recorded")
    else:
        evidence_record = item["evidence"][-1]
        evidence_path = store.root / evidence_record["manifest_path"]
        try:
            manifest = validate_evidence_bundle(store.root, store.state, milestone, evidence_path)
            if sha256_file(evidence_path) != evidence_record.get("manifest_sha256"):
                errors.append("recorded evidence-manifest hash does not match")
            if manifest.get("dirty_worktree"):
                errors.append("completion proof must be recaptured from a clean worktree")
            if manifest.get("git_revision") == "UNBORN":
                errors.append("completion proof requires an immutable Git revision")
        except GovernanceError as exc:
            errors.append(str(exc))
    if milestone["human_review_required"]:
        signoff = item.get("human_signoff")
        if not signoff or signoff.get("decision") != "APPROVE":
            errors.append("explicit human approval is required")
        elif not signoff.get("inputs_reviewed") or not signoff.get("outputs_reviewed"):
            errors.append("human sign-off must confirm both inputs and outputs were reviewed")
        elif signoff.get("configuration_fingerprint") != current_fingerprint:
            errors.append("human sign-off configuration fingerprint is stale")
        elif signoff.get("git_revision") != git_revision(store.root):
            errors.append("human sign-off Git revision is stale")
        elif not item["evidence"] or signoff.get("evidence_manifest_sha256") != item["evidence"][-1].get("manifest_sha256"):
            errors.append("human sign-off is not tied to the current evidence bundle")
        elif not verification or signoff.get("verification_recorded_at") != verification.get("recorded_at"):
            errors.append("human sign-off is not tied to the current verification result")
    if item.get("blockers"):
        errors.append("unresolved blockers remain")
    errors.extend(_triad_gate_errors(store, milestone_id))
    return errors


def _triad_gate_errors(store: MilestoneStore, milestone_id: str) -> list[str]:
    if store.registry.get("triad_review_required") is not True:
        return []
    record = store.milestone_state(milestone_id).get("triad_recommendation")
    if not record:
        return ["current Triad-plus-domain completion recommendation is required"]
    recommendation_path = store.root / record.get("path", "")
    if not recommendation_path.is_file():
        return ["recorded Triad recommendation is missing"]
    if sha256_file(recommendation_path) != record.get("sha256"):
        return ["recorded Triad recommendation hash mismatch"]
    summary_path = store.root / record.get("summary_path", "")
    if not summary_path.is_file():
        return ["recorded human-readable Triad summary is missing"]
    if sha256_file(summary_path) != record.get("summary_sha256"):
        return ["recorded human-readable Triad summary hash mismatch"]
    try:
        from forex.triad import assess_recommendation

        drift = assess_recommendation(store.root, recommendation_path)
    except (GovernanceError, OSError, ValueError) as exc:
        return [f"Triad recommendation validation failed: {exc}"]
    return [f"Triad recommendation invalid: {reason}" for reason in drift]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Forex evidence-gated milestone governance")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Forex repository root")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate", help="validate registry, state, history, schemas, and fingerprint")
    status = subparsers.add_parser("status", help="show milestone status")
    status.add_argument("--json", action="store_true")
    show = subparsers.add_parser("show", help="show the effective milestone contract and state")
    show.add_argument("--id", required=True)
    packages = subparsers.add_parser("work-packages", help="show controlled work packages")
    packages.add_argument("--id", required=True)
    for name in ("start-package", "verify-package"):
        package = subparsers.add_parser(name)
        package.add_argument("--id", required=True, help="work package ID such as M0.1")
    for name in ("ready", "start", "finish-implementation", "prove"):
        command = subparsers.add_parser(name)
        command.add_argument("--id", required=True)
    check = subparsers.add_parser("record-check")
    check.add_argument("--id", required=True)
    check.add_argument("--criterion", required=True)
    check.add_argument("--result", required=True, choices=("PASS", "FAIL"))
    check.add_argument("--evidence", help="repository-relative inspectable evidence path")
    check.add_argument("--note", required=True)
    evidence = subparsers.add_parser("record-evidence")
    evidence.add_argument("--id", required=True)
    evidence.add_argument("--manifest", required=True, type=Path)
    triad = subparsers.add_parser("record-triad-recommendation")
    triad.add_argument("--id", required=True)
    triad.add_argument("--recommendation", required=True, type=Path)
    export = subparsers.add_parser("export-evidence")
    export.add_argument("--id", required=True)
    export.add_argument("--destination", required=True, type=Path)
    verify = subparsers.add_parser("verify")
    verify.add_argument("--id", required=True)
    signoff = subparsers.add_parser("signoff")
    signoff.add_argument("--id", required=True)
    signoff.add_argument("--operator", required=True)
    signoff.add_argument("--decision", required=True, choices=("approve", "reject"))
    signoff.add_argument("--note", required=True)
    signoff.add_argument("--confirm-inputs-reviewed", action="store_true")
    signoff.add_argument("--confirm-outputs-reviewed", action="store_true")
    for name in ("block", "needs-fix", "invalidate"):
        command = subparsers.add_parser(name)
        command.add_argument("--id", required=True)
        command.add_argument("--reason", required=True)
    subparsers.add_parser("refresh-fingerprint", help="record current config fingerprint without proving anything")
    return parser


def _status_payload(store: MilestoneStore) -> dict[str, Any]:
    return {
        "project": store.state["project"],
        "phase": store.state["phase"],
        "last_proven_milestone": store.state["last_proven_milestone"],
        "current_milestone": store.state["current_milestone"],
        "next_milestone": store.state["next_milestone"],
        "configuration_fingerprint": store.state["configuration_fingerprint"],
        "milestones": {
            item["milestone_id"]: store.state["milestones"][item["milestone_id"]]["status"]
            for item in store.registry["milestones"]
        },
    }


def run_cli(args: argparse.Namespace) -> int:
    store = MilestoneStore(args.root)
    if args.command == "refresh-fingerprint":
        old = store.state.get("configuration_fingerprint")
        new = configuration_fingerprint(store.root, store.state)
        store.state["configuration_fingerprint"] = new
        invalidated: list[str] = []
        if old is not None and old != new:
            for milestone_id, item in store.state["milestones"].items():
                if item["status"] == "PROVEN":
                    item["status"] = "NEEDS_REVALIDATION"
                    item["blockers"].append(
                        {"reason": "Governed configuration fingerprint changed.", "recorded_at": utc_now()}
                    )
                    invalidated.append(milestone_id)
        store.event(
            "M0",
            "CONFIGURATION_FINGERPRINT_REFRESHED",
            {"previous": old, "current": new, "invalidated_milestones": invalidated},
        )
        store.save()
        print(new)
        return 0

    store.validate()
    if args.command == "validate":
        print("milestone governance valid")
        return 0
    if args.command == "status":
        payload = _status_payload(store)
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(f"Forex phase={payload['phase']} current={payload['current_milestone']} next={payload['next_milestone']}")
            for milestone_id, status in payload["milestones"].items():
                print(f"{milestone_id:>3}  {status}")
        return 0
    if args.command == "show":
        print(json.dumps({"contract": store.milestone(args.id), "state": store.milestone_state(args.id)}, indent=2))
        return 0
    if args.command == "work-packages":
        milestone = store.milestone(args.id)
        states = store.milestone_state(args.id).get("work_packages", {})
        print(json.dumps({"milestone_id": args.id, "contracts": milestone.get("work_packages", []), "states": states}, indent=2))
        return 0
    if args.command in {"start-package", "verify-package"}:
        parent_id = args.id.split(".", 1)[0]
        milestone = store.milestone(parent_id)
        item = store.milestone_state(parent_id)
        contracts = {package["work_package_id"]: package for package in milestone.get("work_packages", [])}
        if args.id not in contracts:
            raise GovernanceError(f"unknown work package: {args.id}")
        package = contracts[args.id]
        package_state = item["work_packages"][args.id]
        if args.command == "start-package":
            if item["status"] != "IN_PROGRESS" or package_state["status"] not in {"PLANNED", "NEEDS_FIX"}:
                raise GovernanceError(f"cannot start {args.id} from {package_state['status']}")
            unmet = [dep for dep in package["dependencies"] if item["work_packages"][dep]["status"] != "VERIFIED"]
            if unmet:
                raise GovernanceError(f"work-package dependencies are not VERIFIED: {', '.join(unmet)}")
            package_state["status"] = "IN_PROGRESS"
            package_state["started_at"] = utc_now()
            store.event(parent_id, "WORK_PACKAGE_STARTED", {"work_package_id": args.id})
            store.save()
        else:
            if package_state["status"] != "IN_PROGRESS":
                raise GovernanceError(f"cannot verify {args.id} from {package_state['status']}")
            missing = [criterion for criterion in package["acceptance_criteria"] if item["checks"].get(criterion, {}).get("result") != "PASS"]
            if missing:
                raise GovernanceError(f"work package has criteria without PASS results: {', '.join(missing)}")
            package_state["status"] = "VERIFIED"
            package_state["verified_at"] = utc_now()
            store.event(parent_id, "WORK_PACKAGE_VERIFIED", {"work_package_id": args.id})
            store.save()
        return 0

    milestone = store.milestone(args.id)
    item = store.milestone_state(args.id)
    if args.command == "ready":
        if item["status"] not in {"PLANNED", "BLOCKED", "NEEDS_FIX"}:
            raise GovernanceError(f"cannot mark {args.id} READY from {item['status']}")
        unmet = store.dependencies_proven(milestone)
        if unmet:
            raise GovernanceError(f"dependencies are not PROVEN: {', '.join(unmet)}")
        item["blockers"] = []
        store.transition(args.id, "READY", "MILESTONE_READY", {})
    elif args.command == "start":
        if item["status"] not in {"READY", "NEEDS_REVALIDATION"}:
            raise GovernanceError(f"cannot start {args.id} from {item['status']}")
        unmet = store.dependencies_proven(milestone)
        if unmet:
            raise GovernanceError(f"dependencies are not PROVEN: {', '.join(unmet)}")
        item["started_at"] = utc_now()
        if item["status"] == "NEEDS_REVALIDATION":
            item["proven_at"] = None
        store.state["current_milestone"] = args.id
        store.state["next_milestone"] = f"M{int(args.id[1:]) + 1}" if args.id != "M32" else None
        store.transition(args.id, "IN_PROGRESS", "MILESTONE_STARTED", {})
    elif args.command == "finish-implementation":
        if item["status"] not in {"IN_PROGRESS", "NEEDS_FIX"}:
            raise GovernanceError(f"cannot finish implementation from {item['status']}")
        item["implementation_finished_at"] = utc_now()
        store.transition(args.id, "AWAITING_REAL_WORLD_PROOF", "IMPLEMENTATION_FINISHED", {})
    elif args.command == "record-check":
        criterion_ids = {criterion["id"] for criterion in milestone["acceptance_criteria"]}
        if args.criterion not in criterion_ids:
            raise GovernanceError(f"unknown acceptance criterion: {args.criterion}")
        evidence_path = None
        if args.evidence:
            evidence_path = _safe_relative(store.root, store.root / args.evidence, "criterion evidence")
            if not (store.root / evidence_path).exists():
                raise GovernanceError(f"criterion evidence does not exist: {evidence_path}")
        timestamp = utc_now()
        item["checks"][args.criterion] = {
            "result": args.result,
            "recorded_at": timestamp,
            "evidence": evidence_path,
            "note": args.note,
        }
        store.event(args.id, "CHECK_RECORDED", {"criterion": args.criterion, "result": args.result})
        store.save()
    elif args.command == "record-evidence":
        manifest = validate_evidence_bundle(store.root, store.state, milestone, args.manifest)
        relative = _safe_relative(store.root, args.manifest, "evidence manifest")
        record = {
            "manifest_path": relative,
            "manifest_sha256": sha256_file(args.manifest.resolve()),
            "captured_at": manifest["captured_at"],
            "recorded_at": utc_now(),
            "configuration_fingerprint": manifest["configuration_fingerprint"],
            "git_revision": manifest["git_revision"],
            "summary": manifest["summary"],
        }
        item["evidence"].append(record)
        item["real_world_proof_captured_at"] = manifest["captured_at"]
        store.event(args.id, "REAL_WORLD_EVIDENCE_RECORDED", {"manifest_path": relative})
        store.save()
    elif args.command == "record-triad-recommendation":
        from forex.triad import assess_recommendation, load_policy

        recommendation_path = args.recommendation.resolve()
        relative = _safe_relative(store.root, recommendation_path, "Triad recommendation")
        expected_root = (store.root / "runs" / "triad" / args.id).resolve()
        if not recommendation_path.is_relative_to(expected_root):
            raise GovernanceError("Triad recommendation must be beneath runs/triad/<milestone_id>")
        drift = assess_recommendation(store.root, recommendation_path)
        if drift:
            raise GovernanceError("Triad recommendation cannot be recorded:\n- " + "\n- ".join(drift))
        recommendation = load_json(recommendation_path)
        summary_path = recommendation_path.parent / load_policy(store.root)["gate"]["human_summary_filename"]
        summary_relative = _safe_relative(store.root, summary_path, "Triad human-readable summary")
        item["triad_recommendation"] = {
            "path": relative,
            "sha256": sha256_file(recommendation_path),
            "summary_path": summary_relative,
            "summary_sha256": sha256_file(summary_path),
            "review_cycle_id": recommendation["review_cycle_id"],
            "recommendation": recommendation["recommendation"],
            "binding": recommendation["binding"],
            "recorded_at": utc_now(),
        }
        if args.id == "M0" and "M0-C21" in {criterion["id"] for criterion in milestone["acceptance_criteria"]}:
            item["checks"]["M0-C21"] = {
                "result": "PASS",
                "recorded_at": utc_now(),
                "evidence": relative,
                "note": "A current bound Triad-plus-domain recommendation supports completion.",
            }
        store.event(
            args.id,
            "TRIAD_RECOMMENDATION_RECORDED",
            {"path": relative, "recommendation": recommendation["recommendation"]},
        )
        store.save()
    elif args.command == "export-evidence":
        if not item["evidence"]:
            raise GovernanceError("no evidence is available to export")
        manifest_path = store.root / item["evidence"][-1]["manifest_path"]
        validate_evidence_bundle(store.root, store.state, milestone, manifest_path)
        destination = args.destination.expanduser().resolve()
        destination.mkdir(parents=True, exist_ok=True)
        timestamp = utc_now().replace(":", "").replace("-", "")
        archive = destination / f"forex-{args.id}-evidence-{timestamp}.tar.gz"
        with tarfile.open(archive, "w:gz", format=tarfile.PAX_FORMAT) as handle:
            handle.add(manifest_path.parent, arcname=f"{args.id}/{manifest_path.parent.name}")
            triad_record = item.get("triad_recommendation")
            if triad_record:
                triad_path = store.root / triad_record["path"]
                if triad_path.is_file() and sha256_file(triad_path) == triad_record.get("sha256"):
                    handle.add(
                        triad_path.parent,
                        arcname=f"triad/{args.id}/{triad_record['review_cycle_id']}",
                    )
            handle.add(store.state_path, arcname="governance/project_state.json")
            handle.add(store.history_path, arcname="governance/run_history.json")
            handle.add(store.registry_path, arcname="governance/milestone_registry.json")
        checksum_path = archive.with_suffix(archive.suffix + ".sha256")
        checksum_path.write_text(f"{sha256_file(archive)}  {archive.name}\n", encoding="utf-8")
        print(archive)
    elif args.command == "verify":
        passed, results = _run_commands(store.root, args.id, milestone["verification_commands"])
        timestamp = utc_now()
        item["verification"] = {
            "passed": passed,
            "recorded_at": timestamp,
            "git_revision": git_revision(store.root),
            "configuration_fingerprint": configuration_fingerprint(store.root, store.state),
            "commands": results,
        }
        if passed:
            item["verification_passed_at"] = timestamp
        else:
            item["verification_passed_at"] = None
            item["status"] = "NEEDS_FIX"
        store.event(args.id, "VERIFICATION_RECORDED", {"passed": passed, "commands": results})
        store.save()
        if not passed:
            raise GovernanceError("one or more verification commands failed")
        print("verification passed")
    elif args.command == "signoff":
        if not args.confirm_inputs_reviewed or not args.confirm_outputs_reviewed:
            raise GovernanceError("sign-off requires explicit confirmation that inputs and outputs were reviewed")
        if not item["evidence"] or not item.get("verification") or not item["verification"].get("passed"):
            raise GovernanceError("sign-off requires current recorded evidence and passing verification")
        triad_errors = _triad_gate_errors(store, args.id)
        if triad_errors:
            raise GovernanceError("sign-off requires a current completion recommendation:\n- " + "\n- ".join(triad_errors))
        timestamp = utc_now()
        decision = args.decision.upper()
        item["human_signoff"] = {
            "operator": args.operator,
            "decision": decision,
            "note": args.note,
            "inputs_reviewed": True,
            "outputs_reviewed": True,
            "git_revision": git_revision(store.root),
            "configuration_fingerprint": configuration_fingerprint(store.root, store.state),
            "evidence_manifest_sha256": item["evidence"][-1]["manifest_sha256"],
            "verification_recorded_at": item["verification"]["recorded_at"],
            "recorded_at": timestamp,
        }
        item["human_signed_off_at"] = timestamp if decision == "APPROVE" else None
        if decision == "REJECT":
            item["status"] = "NEEDS_FIX"
        store.event(args.id, "HUMAN_SIGNOFF_RECORDED", {"operator": args.operator, "decision": decision})
        store.save()
    elif args.command == "prove":
        if item["status"] in {"PLANNED", "READY", "SUPERSEDED"}:
            raise GovernanceError(f"cannot prove {args.id} from {item['status']}")
        errors = _gate_errors(store, args.id)
        if errors:
            if errors == ["explicit human approval is required"]:
                item["status"] = "AWAITING_HUMAN_SIGNOFF"
                store.event(args.id, "AWAITING_HUMAN_SIGNOFF", {"gate_errors": errors})
                store.save()
            raise GovernanceError("closeout refused:\n- " + "\n- ".join(errors))
        timestamp = utc_now()
        if item.get("first_proven_at") is None:
            item["first_proven_at"] = timestamp
        item["proven_at"] = timestamp
        item["last_validated_at"] = timestamp
        item["status"] = "PROVEN"
        store.state["last_proven_milestone"] = args.id
        store.state["current_milestone"] = None
        next_id = f"M{int(args.id[1:]) + 1}" if args.id != "M32" else None
        store.state["next_milestone"] = next_id
        store.state["implementation_status"] = "PROVEN"
        if next_id and store.milestone_state(next_id)["status"] == "PLANNED":
            store.milestone_state(next_id)["status"] = "READY"
        store.event(args.id, "MILESTONE_PROVEN", {"proven_at": timestamp, "next_milestone": next_id})
        store.save()
        print(f"{args.id} PROVEN at {timestamp}")
    elif args.command in {"block", "needs-fix", "invalidate"}:
        target = {"block": "BLOCKED", "needs-fix": "NEEDS_FIX", "invalidate": "NEEDS_REVALIDATION"}[args.command]
        if args.command == "invalidate" and item["status"] != "PROVEN":
            raise GovernanceError("only a PROVEN milestone can be invalidated")
        item["blockers"].append({"reason": args.reason, "recorded_at": utc_now()})
        store.transition(args.id, target, args.command.upper().replace("-", "_"), {"reason": args.reason})
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if os.environ.get("FOREX_GOVERNANCE_LOCK_HELD") == "1":
            return run_cli(args)
        # Use one repository lock even for reads because startup may need to
        # replay an interrupted two-file transaction before loading state.
        with repository_lock(args.root.resolve(), exclusive=True):
            return run_cli(args)
    except GovernanceError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
