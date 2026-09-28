import json
from pathlib import Path

import pytest

from t480.m20_decision_trace import (
    COMPLETE_SCHEMA_VERSION, SCHEMA_VERSION, DecisionTraceError, DecisionTraceWriter,
)


def writer(tmp_path: Path) -> DecisionTraceWriter:
    return DecisionTraceWriter(tmp_path, run_id="run-1", listener_release_id="release-a",
                               configuration_fingerprint="sha256:" + "a" * 64)


def test_atomic_trace_records_are_ordered_redacted_and_bound(tmp_path):
    trace = writer(tmp_path)
    first = trace.emit("QUOTE_READ", {"server": "GOMarketsMU-Demo", "symbol": "EURUSD",
                                      "bid": 1.1, "ask": 1.1001, "spread_points": 10.0})
    second = trace.emit("PROPOSAL_PERSISTED", {"action": "NO_TRADE", "rationale": "no setup"},
                        proposal_id="p", snapshot_id="s", decision_key="demo|M1|1")
    complete = trace.complete(assessment_sequence=9, assessment_sha256="sha256:" + "b" * 64,
                              proposal_id="p", snapshot_id="s", state="TRACE_COMPLETE")
    root = tmp_path / "release-a" / "run-1"
    rows = [json.loads((root / f"{item:020d}.json").read_text()) for item in (1, 2)]
    assert [row["schema_version"] for row in rows] == [SCHEMA_VERSION, SCHEMA_VERSION]
    assert [row["sequence"] for row in rows] == [1, 2]
    assert rows[1]["proposal_id"] == "p" and rows[1]["facts"]["action"] == "NO_TRADE"
    manifest = json.loads((root / "complete.json").read_text())
    assert manifest["schema_version"] == COMPLETE_SCHEMA_VERSION
    assert manifest["event_hashes"] == [first["event_sha256"], second["event_sha256"]]
    assert complete["state"] == "TRACE_COMPLETE"


def test_trace_refuses_unsafe_facts_and_never_overwrites(tmp_path):
    trace = writer(tmp_path)
    with pytest.raises(DecisionTraceError, match="allowlisted"):
        trace.emit("QUOTE_READ", {"password": "no"})
    trace.emit("QUOTE_READ", {"bid": 1.1, "ask": 1.2})
    root = tmp_path / "release-a" / "run-1"
    original = (root / "00000000000000000001.json").read_bytes()
    with pytest.raises(OSError, match="conflicts"):
        trace._publish("00000000000000000001.json", b"different")
    assert (root / "00000000000000000001.json").read_bytes() == original
    assert not list(root.glob("*.pending"))
