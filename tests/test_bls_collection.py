import base64
import json
from pathlib import Path
import subprocess
import sys

import pytest

from forex.bls_collection import retain_response, apply_retained_response, validate_response
from forex.event_capture_store import EventCaptureStoreError
from tests.test_bls_monthly_capture import RAW, URL


def response(**changes):
    record = {"schema_version": "forex.bls-http-observation.v1", "requested_url": URL,
        "started_at_utc": "2026-09-01T00:00:00Z", "completed_at_utc": "2026-09-01T00:00:01Z",
        "status_code": 200, "content_type": "text/html", "body_base64": base64.b64encode(RAW).decode(),
        "body_complete": True, "outcome": "SUCCESS", "error_code": None, "execution_authority": False}
    return json.dumps({**record, **changes}).encode()


def test_real_parser_receives_success_and_exact_response_is_retained(tmp_path):
    raw = response()
    first = retain_response(tmp_path, capture_id="one", raw=raw, year=2026, month=9)
    assert first["processing"] == "CAPTURE_RETAINED"
    assert first["coverage_status"] == "UNKNOWN"
    assert next((tmp_path / "acquisitions/one").glob("*.json")).read_bytes() == raw
    assert (tmp_path / "raw/one.html").read_bytes() == RAW
    assert apply_retained_response(tmp_path, capture_id="one", year=2026, month=9) == first
    assert retain_response(tmp_path, capture_id="one", raw=raw, year=2026, month=9) == first


def test_access_denial_retained_without_parsing_and_cli_resume_does_not_fetch(tmp_path):
    raw = response(status_code=403, outcome="HTTP_ERROR", error_code="HTTP_STATUS", body_base64=base64.b64encode(b"Access denied").decode())
    result = retain_response(tmp_path, capture_id="denied", raw=raw, year=2026, month=9)
    assert result["processing"] == "RETRIEVAL_FAILURE_RETAINED"
    assert list((tmp_path / "raw").iterdir()) == []
    command = Path(__file__).resolve().parents[1] / "scripts/bls_collect.py"
    resumed = subprocess.run([sys.executable, str(command), "--store", str(tmp_path),
        "--capture-id", "denied", "--year", "2026", "--month", "9", "--resume"],
        capture_output=True, text=True)
    assert resumed.returncode == 3, resumed.stderr
    assert json.loads(resumed.stdout) == result


@pytest.mark.parametrize("changes", [{"requested_url": "https://example.com"}, {"status_code": 403},
    {"body_complete": False}, {"execution_authority": True}, {"body_base64": "***"},
    {"completed_at_utc": "2026-08-01T00:00:00Z"}])
def test_invalid_observation_refused_before_writes(tmp_path, changes):
    with pytest.raises((ValueError, EventCaptureStoreError)):
        retain_response(tmp_path / "store", capture_id="one", raw=response(**changes), year=2026, month=9)
    assert not (tmp_path / "store").exists()


def test_identity_conflict_and_receipt_tampering_refuse(tmp_path):
    raw = response()
    retain_response(tmp_path, capture_id="one", raw=raw, year=2026, month=9)
    with pytest.raises(EventCaptureStoreError):
        retain_response(tmp_path, capture_id="one", raw=response(completed_at_utc="2026-09-01T00:00:02Z"), year=2026, month=9)
    path = next((tmp_path / "acquisitions/one").glob("*.json"))
    path.write_bytes(response(completed_at_utc="2026-09-01T00:00:03Z"))
    with pytest.raises(EventCaptureStoreError, match="hash mismatch"):
        apply_retained_response(tmp_path, capture_id="one", year=2026, month=9)


@pytest.mark.parametrize("success", [True, False])
def test_resume_after_transport_retention_never_needs_network(tmp_path, success):
    from forex.bls_collection import retain_transport_observation, resume_collection
    observed = {"ok": success, "result": {"exit_code": 0 if success else 1,
                "stdout": response().decode() if success else ""}}
    retain_transport_observation(tmp_path, capture_id="one", year=2026, month=9,
        observation=observed, probe_sha256="sha256:" + "1" * 64, source_declaration_sha256="sha256:" + "2" * 64)
    result = resume_collection(tmp_path, capture_id="one", year=2026, month=9)
    assert result["processing"] == ("CAPTURE_RETAINED" if success else "TRANSPORT_FAILURE_RETAINED")


def test_staging_only_acquisition_recovers_from_retained_transport(tmp_path):
    from forex.bls_collection import retain_transport_observation, resume_collection
    retain_transport_observation(tmp_path, capture_id="one", year=2026, month=9,
        observation={"ok": True, "result": {"exit_code": 0, "stdout": response().decode()}},
        probe_sha256="sha256:" + "1" * 64, source_declaration_sha256="sha256:" + "2" * 64)
    directory = tmp_path / "acquisitions/one"
    directory.mkdir(parents=True)
    pending = directory / ".pending-test"
    pending.write_bytes(b"incomplete")
    assert resume_collection(tmp_path, capture_id="one", year=2026, month=9)["processing"] == "CAPTURE_RETAINED"
    assert pending.read_bytes() == b"incomplete"


def test_cli_joins_shared_transport_wrapper_to_retention(tmp_path, monkeypatch, capsys):
    import importlib.util
    from types import SimpleNamespace
    path = Path(__file__).resolve().parents[1] / "scripts/bls_collect.py"
    spec = importlib.util.spec_from_file_location("bls_collect_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    seen = []
    def execute(operation, **kwargs):
        seen.append(operation)
        return {"operation": "bls_monthly_calendar_probe", "ok": True,
                "result": {"exit_code": 0, "stdout": response().decode()}}
    monkeypatch.setitem(sys.modules, "t480_adapter", SimpleNamespace(
        Operation=lambda *args, **kwargs: kwargs, execute_operation=execute,
        target=lambda: "test-no-network", TRANSPORT_SETTINGS=SimpleNamespace(wsl_distribution="Ubuntu")))
    monkeypatch.setattr(sys, "argv", [str(path), "--year", "2026", "--month", "9",
        "--capture-id", "cli", "--store", str(tmp_path)])
    assert module.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["processing"] == "CAPTURE_RETAINED"
    assert seen[0]["timeout_seconds"] == 35
    import gzip
    encoded = seen[0]["powershell_command"].split("; '")[1].split("'")[0]
    program = gzip.decompress(base64.b64decode(encoded))
    assert program == module.probe_program((path.parents[1] / "t480/bls_monthly_probe.py").read_bytes(), 2026, 9)
    assert b"collect_month(2026, 9)" in program
    assert len(list((tmp_path / "transport/cli").glob("*.json"))) == 1
