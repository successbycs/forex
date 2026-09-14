from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone

import pytest

from forex.event_annotations import event_annotation
from forex.event_quality import qualify_events
from forex.m1_event_sidecar import M1EventSidecarError, build_m1_event_context_sidecar
from tests.test_m20_retained_export import operation_export as unqualified_operation_export
from tests.test_m20_policy_kernel import bound_snapshot


SOURCE_SHA = "sha256:" + "1" * 64
DECISION = "2026-09-11T01:00:02Z"
START = "2026-09-11T00:00:00Z"
END = "2026-09-11T02:00:00Z"


def operation_export():
    source = unqualified_operation_export()
    payload = json.loads(source["result"]["stdout"])
    snapshot = bound_snapshot(observed=datetime(2026, 9, 11, 1, tzinfo=timezone.utc),
                              decision=datetime(2026, 9, 11, 1, 0, 1, tzinfo=timezone.utc))
    payload["decision_snapshot"] = snapshot
    payload["proposal"]["decision_snapshot_sha256"] = snapshot["payload_sha256"]
    source["result"]["stdout"] = json.dumps(payload)
    return source


def context(*, decision=DECISION, start=START, end=END):
    qualification = qualify_events([], decision)
    annotation = event_annotation(qualification, decision_at_utc=decision,
                                  window_start_utc=start, window_end_utc=end)
    return {"schema_version": "forex.event-store-context-report.v1",
            "journal_sha256": "sha256:" + "2" * 64,
            "qualification": qualification, "annotation": annotation,
            "execution_authority": False}


def test_binds_full_retained_assessment_and_verified_context_without_action_mutation():
    assessment = operation_export()
    original = copy.deepcopy(assessment)
    supplied_context = context()
    original_context = copy.deepcopy(supplied_context)
    sidecar = build_m1_event_context_sidecar(assessment, source_raw_sha256=SOURCE_SHA,
                                             event_context=supplied_context,
                                             window_start_utc=START, window_end_utc=END)
    assert assessment == original
    assert supplied_context == original_context
    assert sidecar["schema_version"] == "forex.m1.event-context-sidecar.v1"
    assert sidecar["annotation_type"] == "EVENT_CONTEXT_ONLY"
    assert sidecar["execution_authority"] is False
    assert sidecar["proposal_id"] == "proposal-1"
    assert sidecar["snapshot_id"] == "snapshot-1"
    assert sidecar["snapshot_payload_sha256"] == json.loads(assessment["result"]["stdout"])["decision_snapshot"]["payload_sha256"]
    assert sidecar["event_context_journal_sha256"] == "sha256:" + "2" * 64
    assert sidecar["event_qualification_sha256"] == supplied_context["qualification"]["result_sha256"]
    assert sidecar["event_annotation_sha256"] == supplied_context["annotation"]["annotation_sha256"]
    assert "action" not in sidecar
    content = {key: value for key, value in sidecar.items() if key != "sidecar_sha256"}
    assert sidecar["sidecar_sha256"] == "sha256:" + hashlib.sha256(
        json.dumps(content, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@pytest.mark.parametrize("mutate", [
    lambda value: value["result"].update({"stdout": json.dumps([{"proposal_id": "p"}])}),
    lambda value: value["result"].update({"stdout": json.dumps({"lineage": [{"proposal_id": "p"}]})}),
])
def test_coverage_only_exports_are_refused_not_synthesized(mutate):
    assessment = operation_export()
    mutate(assessment)
    with pytest.raises(M1EventSidecarError, match="lifecycle or lineage"):
        build_m1_event_context_sidecar(assessment, source_raw_sha256=SOURCE_SHA, event_context=context(),
                                       window_start_utc=START, window_end_utc=END)


def test_snapshot_identity_hash_and_time_mismatches_refuse():
    for change, message in (
        (("proposal", "snapshot_id", "other"), "snapshot_id"),
        (("proposal", "decision_snapshot_sha256", "sha256:" + "b" * 64), "decision_snapshot_sha256"),
        (("snapshot", "captured_at_utc", "2026-09-11T00:59:59Z"), "retained body"),
    ):
        assessment = operation_export()
        payload = json.loads(assessment["result"]["stdout"])
        payload["decision_snapshot" if change[0] == "snapshot" else "proposal"][change[1]] = change[2]
        assessment["result"]["stdout"] = json.dumps(payload)
        with pytest.raises(M1EventSidecarError, match=message):
            build_m1_event_context_sidecar(assessment, source_raw_sha256=SOURCE_SHA, event_context=context(),
                                           window_start_utc=START, window_end_utc=END)


def test_context_digest_decision_window_and_missing_annotation_refuse():
    broken = context()
    broken["annotation"]["events"].append({"tampered": True})
    with pytest.raises(M1EventSidecarError, match="does not bind"):
        build_m1_event_context_sidecar(operation_export(), source_raw_sha256=SOURCE_SHA, event_context=broken,
                                       window_start_utc=START, window_end_utc=END)
    with pytest.raises(M1EventSidecarError, match="verified event-context"):
        build_m1_event_context_sidecar(operation_export(), source_raw_sha256=SOURCE_SHA, event_context=None,
                                       window_start_utc=START, window_end_utc=END)
    with pytest.raises(M1EventSidecarError, match="event context cannot be verified"):
        build_m1_event_context_sidecar(operation_export(), source_raw_sha256=SOURCE_SHA,
                                       event_context=context(decision="2026-09-11T01:00:03Z"),
                                       window_start_utc=START, window_end_utc=END)


def test_source_raw_digest_must_be_exact_sha256_format():
    with pytest.raises(M1EventSidecarError, match="source_raw_sha256"):
        build_m1_event_context_sidecar(operation_export(), source_raw_sha256="sha256:nope", event_context=context(),
                                       window_start_utc=START, window_end_utc=END)


@pytest.mark.parametrize("mutation", ["price", "missing_field"])
def test_repeated_hash_labels_do_not_prove_snapshot_integrity(mutation):
    source = operation_export()
    payload = json.loads(source["result"]["stdout"])
    if mutation == "price":
        payload["decision_snapshot"]["bid"] = 999
    else:
        del payload["decision_snapshot"]["market_context"]
    source["result"]["stdout"] = json.dumps(payload)
    with pytest.raises(M1EventSidecarError, match="snapshot"):
        build_m1_event_context_sidecar(source, source_raw_sha256=SOURCE_SHA, event_context=context(),
                                       window_start_utc=START, window_end_utc=END)
