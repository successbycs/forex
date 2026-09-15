from __future__ import annotations

import base64
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from forex.bls_n8n_envelope import build_observation
from forex.bls_n8n_projection import BLSN8nProjectionError, project_verified_n8n_bls_store
from forex.bls_n8n_retention import retain
from scripts.persist_bls_retained_calendar_facts import build_payload

ROOT = Path(__file__).resolve().parents[1]
from tests.test_bls_monthly_capture import RAW


def handoff() -> dict:
    return {"capture_id":"projection-1","year":2026,"month":9,
            "started_at_utc":"2026-09-14T00:00:00Z","completed_at_utc":"2026-09-14T00:00:01Z",
            "status_code":200,"content_type":"text/html","body_base64":base64.b64encode(RAW).decode(),"body_complete":True}


def retained(root: Path) -> None:
    value = handoff(); capture_id, observation = build_observation(value)
    retain(root, capture_id=capture_id, observation=observation, year=value["year"], month=value["month"],
           workflow_id="fixed", workflow_sha256="sha256:" + "a" * 64)


def test_verifies_n8n_receipt_to_acquisition_to_raw_before_projection(tmp_path):
    retained(tmp_path)
    projection = project_verified_n8n_bls_store(tmp_path, expected_workflow_id="fixed", expected_workflow_sha256="sha256:" + "a" * 64)
    assert projection["facts"] and all(fact["receipt_sha256"].startswith("sha256:") for fact in projection["facts"])
    payload, raw, digest = build_payload(tmp_path, projector=lambda root: project_verified_n8n_bls_store(root, expected_workflow_id="fixed", expected_workflow_sha256="sha256:" + "a" * 64))
    assert payload["facts"] and digest.startswith("sha256:") and raw


def test_missing_or_tampered_n8n_receipt_refuses_projection(tmp_path):
    retained(tmp_path)
    receipt = next((tmp_path / "n8n-receipts" / "projection-1").glob("*.json"))
    receipt.unlink()
    with pytest.raises(BLSN8nProjectionError, match="receipt"):
        project_verified_n8n_bls_store(tmp_path, expected_workflow_id="fixed", expected_workflow_sha256="sha256:" + "a" * 64)


def test_projection_accepts_exact_acquisition_timestamp_before_journal_normalisation(tmp_path):
    value = handoff(); value["completed_at_utc"] = "2026-09-14T00:00:01.123Z"
    capture_id, observation = build_observation(value)
    retain(tmp_path, capture_id=capture_id, observation=observation, year=value["year"], month=value["month"],
           workflow_id="fixed", workflow_sha256="sha256:" + "a" * 64)
    assert project_verified_n8n_bls_store(tmp_path, expected_workflow_id="fixed", expected_workflow_sha256="sha256:" + "a" * 64)["facts"]


def test_recomputed_receipt_cannot_substitute_bound_workflow_or_claimed_start(tmp_path):
    retained(tmp_path)
    directory = tmp_path / "n8n-receipts" / "projection-1"
    receipt = next(directory.glob("*.json"))
    value = json.loads(receipt.read_text()); value["configured_workflow_id"] = "other"
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    receipt.unlink(); (directory / (hashlib.sha256(raw).hexdigest() + ".json")).write_bytes(raw)
    with pytest.raises(BLSN8nProjectionError, match="bind"):
        project_verified_n8n_bls_store(tmp_path, expected_workflow_id="fixed", expected_workflow_sha256="sha256:" + "a" * 64)


def test_read_only_projector_cli_requires_bound_workflow_and_emits_projection(tmp_path):
    retained(tmp_path)
    command = [sys.executable, "scripts/project_n8n_bls_retained_calendar_facts.py", "--store", str(tmp_path),
               "--workflow-id", "fixed", "--workflow-sha256", "sha256:" + "a" * 64]
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 0 and json.loads(result.stdout)["facts"]
