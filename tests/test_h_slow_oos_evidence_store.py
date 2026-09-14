import hashlib
import json

import pytest

from forex.h_slow_oos_evidence_store import (
    HSlowOOSEvidenceError,
    RECEIPT_SCHEMA,
    retain_oos_record,
    verify_oos_record,
)


def record(**changes):
    value = {"schema_version": "forex.h-slow.forward-oos-evidence.v1", "record_id": "oos-2026-10",
             "research_decision_sha256": "sha256:" + "a" * 64,
             "strategy_policy_version": "forex.h-slow.tsmom-12m.v1",
             "decision_at_utc": "2026-10-01T00:00:00Z",
             "metrics": {"sample_count": 40, "net_after_cost_return": ".04", "max_drawdown": ".1"},
             "source_snapshot_sha256": "sha256:" + "b" * 64, "execution_authority": False}
    value.update(changes)
    return value


def test_retain_then_read_only_verify_is_canonical_and_idempotent(tmp_path):
    retained = retain_oos_record(tmp_path / "oos", record())
    verified = verify_oos_record(tmp_path / "oos", "oos-2026-10")
    assert retained == verified
    assert verified["schema_version"] == RECEIPT_SCHEMA
    assert verified["execution_authority"] is False
    assert retain_oos_record(tmp_path / "oos", record()) == retained


def test_verification_of_missing_root_never_creates_it(tmp_path):
    root = tmp_path / "missing"
    with pytest.raises(HSlowOOSEvidenceError, match="root"):
        verify_oos_record(root, "oos-2026-10")
    assert not root.exists()


def test_verification_does_not_retain_or_repair_noncanonical_record(tmp_path):
    root = tmp_path / "oos"
    root.mkdir()
    path = root / "oos-2026-10.json"
    path.write_text(json.dumps(record(), indent=2))
    before = path.read_bytes()
    with pytest.raises(HSlowOOSEvidenceError, match="canonical"):
        verify_oos_record(root, "oos-2026-10")
    assert path.read_bytes() == before


@pytest.mark.parametrize("changed", [
    {"record_id": "../escape"},
    {"research_decision_sha256": "sha256:not-a-digest"},
    {"metrics": {"sample_count": 1, "net_after_cost_return": 0, "max_drawdown": "-1e-999"}},
    {"metrics": {"sample_count": 1, "net_after_cost_return": 0, "max_drawdown": "1.01"}},
    {"decision_at_utc": "not-a-time"},
])
def test_retention_rejects_bad_provenance_or_metrics_without_writing(tmp_path, changed):
    with pytest.raises(HSlowOOSEvidenceError):
        retain_oos_record(tmp_path / "oos", record(**changed))
    assert not (tmp_path / "oos").exists()


def test_verifier_detects_byte_tampering(tmp_path):
    root = tmp_path / "oos"
    retain_oos_record(root, record())
    path = root / "oos-2026-10.json"
    body = json.loads(path.read_text())
    body["metrics"]["sample_count"] = 41
    path.write_bytes(json.dumps(body, sort_keys=True, separators=(",", ":")).encode())
    expected = "sha256:" + hashlib.sha256(json.dumps(record(), sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    with pytest.raises(HSlowOOSEvidenceError, match="digest"):
        verify_oos_record(root, "oos-2026-10", expected_record_sha256=expected)


def test_verifier_refuses_a_renamed_record_even_when_its_digest_matches(tmp_path):
    root = tmp_path / "oos"
    receipt = retain_oos_record(root, record())
    (root / "oos-2026-10.json").rename(root / "alias.json")
    with pytest.raises(HSlowOOSEvidenceError, match="requested ID"):
        verify_oos_record(root, "alias", expected_record_sha256=receipt["record_sha256"])


def test_publish_failure_preserves_staging_and_retry_never_discards_it(tmp_path, monkeypatch):
    import forex.h_slow_oos_evidence_store as store
    root = tmp_path / "oos"
    original_link = store.os.link
    monkeypatch.setattr(store.os, "link", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("injected")))
    with pytest.raises(OSError, match="injected"):
        retain_oos_record(root, record())
    staging = list(root.glob(".oos-2026-10.*.staging"))
    assert len(staging) == 1 and staging[0].read_bytes()
    monkeypatch.setattr(store.os, "link", original_link)
    with pytest.raises(HSlowOOSEvidenceError, match="unfinished"):
        retain_oos_record(root, record())


def test_existing_identical_final_is_idempotent_even_if_crash_left_staging(tmp_path):
    root = tmp_path / "oos"
    retained = retain_oos_record(root, record())
    (root / ".oos-2026-10.crash.staging").write_bytes(b"preserved crash artifact")
    assert retain_oos_record(root, record()) == retained
