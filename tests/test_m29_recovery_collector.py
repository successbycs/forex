import base64
import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from forex.m29_recovery_collector import RecoveryCollectorError, collect, inspect, verify


ROOT = Path(__file__).resolve().parents[1]


def _envelope(operation, stdout):
    return json.dumps({"operation": operation, "ok": True,
                       "result": {"ok": True, "exit_code": 0, "stdout": json.dumps(stdout)}}).encode()


def _page(release, after, sequences):
    records = []
    for sequence in sequences:
        raw = json.dumps({"listener_release_id": release, "assessment_sequence": sequence}).encode()
        records.append({"assessment_sequence": sequence,
                        "raw_sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
                        "raw_base64": base64.b64encode(raw).decode()})
    return {"observation": "AVAILABLE", "listener_release_id": release,
            "after_assessment_sequence": after, "records": records}


def envelopes():
    release = "a" * 16
    fingerprint = "sha256:" + "b" * 64
    listener = {"running": True, "state": "MAINTENANCE_HOLD", "release_id": release,
                "heartbeat_at_utc": "2026-09-15T00:00:00Z", "monitor": {"state": "IDLE"}}
    diagnostics = {"maintenance_hold_present": True, "logon_type": "S4U",
                   "deployment_binding": {"observation": "VALID", "configuration_fingerprint": fingerprint,
                                          "application_revision": "deadbeef",
                                          "lease": {"server": "GOMarketsMU-Demo", "symbol": "EURUSD"}}}
    continuity = {"observation": "AVAILABLE", "event_log_sha256": "sha256:" + "c" * 64,
                  "logon_type": "S4U", "record": {"schema_version": "forex.m20.continuity-protocol.v1",
                  "run_id": "run-1", "release_id": release, "state": "PASS",
                  "handoff": {"state": "RECOVERED"}, "broker_mutation": "NONE"}}
    return {
        "preflight-listener": _envelope("m20_listener_status", listener),
        "preflight-diagnostics": _envelope("m20_listener_diagnostics", diagnostics),
        "preflight-spool-page": _envelope("m20_listener_spool_page", _page(release, 0, [9, 10])),
        "continuity-status": _envelope("m20_listener_continuity_status", continuity),
        "postflight-listener": _envelope("m20_listener_status", {**listener, "heartbeat_at_utc": "2026-09-15T00:00:20Z"}),
        "postflight-diagnostics": _envelope("m20_listener_diagnostics", diagnostics),
        "postflight-spool-page": _envelope("m20_listener_spool_page", _page(release, 10, [11, 12])),
    }


def test_inspect_accepts_only_a_bounded_no_order_recovery_observation():
    result = inspect(envelopes())
    assert result["state"] == "RECOVERY_DRILL_CAPTURED_NOT_M29_PROVEN"
    assert result["execution_authority"] is False
    assert [item["assessment_sequence"] for item in result["receipt_identities"]] == [9, 10, 11, 12]
    assert any("Not M29 proof" in limitation for limitation in result["limitations"])


def test_inspect_requires_a_strictly_later_postflight_heartbeat():
    raw = envelopes()
    outer = json.loads(raw["postflight-listener"])
    listener = json.loads(outer["result"]["stdout"])
    listener["heartbeat_at_utc"] = "2026-09-15T00:00:00Z"
    outer["result"]["stdout"] = json.dumps(listener)
    raw["postflight-listener"] = json.dumps(outer).encode()
    with pytest.raises(RecoveryCollectorError, match="postflight heartbeat is not later"):
        inspect(raw)


@pytest.mark.parametrize("mutation, message", [
    ("cursor", "postflight-spool-page spool does not continue its cursor"),
    ("duplicate", "postflight-spool-page spool does not continue its cursor"),
    ("hold", "does not show a running maintenance-held listener"),
    ("continuity", "does not show a bounded recovered no-order handoff"),
])
def test_inspect_fails_closed_for_partial_or_ambiguous_recovery_evidence(mutation, message):
    raw = envelopes()
    if mutation == "cursor":
        outer = json.loads(raw["postflight-spool-page"])
        page = json.loads(outer["result"]["stdout"]); page["after_assessment_sequence"] = 9
        outer["result"]["stdout"] = json.dumps(page); raw["postflight-spool-page"] = json.dumps(outer).encode()
    elif mutation == "duplicate":
        outer = json.loads(raw["postflight-spool-page"])
        page = json.loads(outer["result"]["stdout"]); page["records"][0]["assessment_sequence"] = 10
        outer["result"]["stdout"] = json.dumps(page); raw["postflight-spool-page"] = json.dumps(outer).encode()
    elif mutation == "hold":
        outer = json.loads(raw["preflight-listener"])
        listener = json.loads(outer["result"]["stdout"]); listener["state"] = "RUNNING"
        outer["result"]["stdout"] = json.dumps(listener); raw["preflight-listener"] = json.dumps(outer).encode()
    else:
        outer = json.loads(raw["continuity-status"])
        status = json.loads(outer["result"]["stdout"]); status["record"]["handoff"]["state"] = "FAILED"
        outer["result"]["stdout"] = json.dumps(status); raw["continuity-status"] = json.dumps(outer).encode()
    with pytest.raises(RecoveryCollectorError, match=message):
        inspect(raw)


def test_collect_is_append_only_and_verify_replays_only_retained_bytes(tmp_path):
    bundle = collect(evidence_root=tmp_path, run_id="fresh-demo-1", envelopes=envelopes())
    assert Path(bundle["bundle"]).is_dir()
    assert verify(bundle=Path(bundle["bundle"]))["verified"] is True
    with pytest.raises(RecoveryCollectorError, match="already exists"):
        collect(evidence_root=tmp_path, run_id="fresh-demo-1", envelopes=envelopes())
    result = Path(bundle["bundle"]) / "collector-result.json"
    result.write_text("{}")
    with pytest.raises(RecoveryCollectorError, match="artifact hash mismatch"):
        verify(bundle=Path(bundle["bundle"]))


def test_verify_refuses_a_duplicate_manifest_artifact_entry(tmp_path):
    result = collect(evidence_root=tmp_path, run_id="fresh-demo-2", envelopes=envelopes())
    bundle = Path(result["bundle"])
    manifest = json.loads((bundle / "manifest.json").read_text())
    manifest["artifacts"].append(dict(manifest["artifacts"][0]))
    (bundle / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(RecoveryCollectorError, match="artifact set is invalid"):
        verify(bundle=bundle)


def test_cli_captures_raw_files_without_any_transport_or_order_route(tmp_path):
    inputs = tmp_path / "inputs"; inputs.mkdir()
    args = []
    for role, raw in envelopes().items():
        path = inputs / (role + ".json"); path.write_bytes(raw)
        args.extend(["--" + role, str(path)])
    result = subprocess.run(["python3", "scripts/m29_recovery_collector.py", "capture", "--evidence-root", str(tmp_path),
                             "--run-id", "capture-1", *args], cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["execution_authority"] is False
    source = (ROOT / "scripts/m29_recovery_collector.py").read_text()
    assert "t480_adapter.py" not in source and "order_send" not in source and "subprocess" not in source
