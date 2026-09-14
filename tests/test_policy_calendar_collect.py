from __future__ import annotations

import base64
from contextlib import redirect_stdout
from io import StringIO
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from forex import first_party_policy_capture as capture
from forex.first_party_policy_capture import (PolicyCalendarCaptureError, reserve_transport_capture,
                                              retain_transport_result, validate_successful_envelope)
from t480.first_party_policy_calendar_probe import PolicyCalendarFamily, SCHEMA_VERSION, requested_url


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/policy_calendar_collect.py"


def envelope(family=PolicyCalendarFamily.FOMC_POLICY_DECISION, **changes) -> bytes:
    body = b"<html>fixed publisher calendar</html>"
    value = {
        "schema_version": SCHEMA_VERSION,
        "requested_url": requested_url(family),
        "started_at_utc": "2026-09-13T00:00:00Z",
        "completed_at_utc": "2026-09-13T00:00:01Z",
        "status_code": 200,
        "content_type": "text/html",
        "body_base64": base64.b64encode(body).decode("ascii"),
        "body_complete": True,
        "outcome": "SUCCESS",
        "error_code": None,
        "execution_authority": False,
    }
    return json.dumps({**value, **changes}, sort_keys=True).encode("utf-8")


def observed(stdout: str, *, ok=True, exit_code=0) -> dict:
    return {"operation": "first_party_policy_calendar_probe", "ok": ok,
            "result": {"exit_code": exit_code, "stdout": stdout}}


def hashes() -> dict:
    return {"probe_sha256": "sha256:" + "1" * 64, "program_sha256": "sha256:" + "2" * 64}


def test_success_retains_raw_publisher_bytes_and_exact_transport_receipt(tmp_path):
    raw = envelope()
    result = retain_transport_result(tmp_path, capture_id="fed-1", family=PolicyCalendarFamily.FOMC_POLICY_DECISION,
                                     transport_observation=observed(raw.decode()), **hashes())
    directory = tmp_path / "policy-calendar-captures/fed-1"
    assert result["outcome"] == "SUCCESS"
    assert result["publisher_capture_retained"] is True
    assert (directory / "publisher.html").read_bytes() == b"<html>fixed publisher calendar</html>"
    assert (directory / "publisher.html.sha256").read_text().strip() == result["publisher_body_sha256"]
    observation = json.loads((directory / "transport-observation.json").read_text())
    assert observation == observed(raw.decode())
    receipt = json.loads((directory / "receipt.json").read_text())
    assert receipt["transport_observation_sha256"] == result["transport_observation_sha256"]
    assert receipt["execution_authority"] is False


def test_http_failure_is_retained_as_transport_receipt_only(tmp_path):
    result = retain_transport_result(tmp_path, capture_id="ecb-failure", family=PolicyCalendarFamily.ECB_POLICY_DECISION,
                                     transport_observation=observed(envelope(PolicyCalendarFamily.ECB_POLICY_DECISION,
                                                                             status_code=403, outcome="HTTP_ERROR", error_code="HTTP_STATUS").decode()),
                                     **hashes())
    directory = tmp_path / "policy-calendar-captures/ecb-failure"
    assert result["outcome"] == "PUBLISHER_CAPTURE_REJECTED"
    assert result["publisher_capture_retained"] is False
    assert (directory / "transport-observation.json").is_file()
    assert (directory / "receipt.json").is_file()
    assert not (directory / "publisher.html").exists()


@pytest.mark.parametrize("changes", [
    {"requested_url": "https://example.invalid/"}, {"body_complete": False},
    {"content_type": "application/json"}, {"execution_authority": True}, {"body_base64": "***"},
])
def test_invalid_success_envelope_refuses_raw_capture_but_preserves_receipt(tmp_path, changes):
    result = retain_transport_result(tmp_path, capture_id="invalid-" + str(len(changes)),
                                     family=PolicyCalendarFamily.FOMC_POLICY_DECISION,
                                     transport_observation=observed(envelope(**changes).decode()), **hashes())
    assert result["outcome"] == "PUBLISHER_CAPTURE_REJECTED"
    assert result["publisher_capture_retained"] is False
    directory = tmp_path / "policy-calendar-captures" / result["capture_id"]
    assert (directory / "receipt.json").is_file()
    assert not (directory / "publisher.html").exists()


def test_failed_transport_is_receipt_only_and_capture_id_refuses_remote_retry(tmp_path):
    first = retain_transport_result(tmp_path, capture_id="once", family=PolicyCalendarFamily.FOMC_POLICY_DECISION,
                                    transport_observation=observed("", ok=False, exit_code=1), **hashes())
    assert first["outcome"] == "TRANSPORT_FAILURE_RETAINED"
    with pytest.raises(PolicyCalendarCaptureError, match="remote retry"):
        retain_transport_result(tmp_path, capture_id="once", family=PolicyCalendarFamily.FOMC_POLICY_DECISION,
                                transport_observation=observed(envelope().decode()), **hashes())


def test_cli_uses_t480_with_fixed_program_and_35_second_deadline(tmp_path, monkeypatch, capsys):
    spec = importlib.util.spec_from_file_location("policy_collect_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    seen = []

    def execute(operation, **kwargs):
        seen.append(operation)
        return observed(envelope().decode())

    monkeypatch.setitem(sys.modules, "t480_adapter", SimpleNamespace(
        Operation=lambda *args, **kwargs: kwargs,
        execute_operation=execute,
        target=lambda: "test-no-network",
        TRANSPORT_SETTINGS=SimpleNamespace(wsl_distribution="Ubuntu"),
    ))
    assert module.main(["--family", "FOMC_POLICY_DECISION", "--capture-id", "cli", "--store", str(tmp_path)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["outcome"] == "SUCCESS"
    assert seen[0]["timeout_seconds"] == 35
    encoded = seen[0]["powershell_command"].split("; '")[1].split("'")[0]
    program = gzip.decompress(base64.b64decode(encoded))
    assert program == module.probe_program((ROOT / "t480/first_party_policy_calendar_probe.py").read_bytes(), "FOMC_POLICY_DECISION")
    compile(program, "shipped-policy-calendar-probe.py", "exec")
    assert b"import json" in program
    assert b"collect_policy_calendar(PolicyCalendarFamily.FOMC_POLICY_DECISION)" in program


def test_duplicate_capture_id_is_reserved_before_a_second_transport_call(tmp_path, monkeypatch, capsys):
    spec = importlib.util.spec_from_file_location("policy_collect_reservation_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    calls: list[object] = []

    def execute(operation, **kwargs):
        calls.append(operation)
        return observed(envelope().decode())

    monkeypatch.setitem(sys.modules, "t480_adapter", SimpleNamespace(
        Operation=lambda *args, **kwargs: kwargs,
        execute_operation=execute,
        target=lambda: "test-no-network",
        TRANSPORT_SETTINGS=SimpleNamespace(wsl_distribution="Ubuntu"),
    ))
    args = ["--family", "FOMC_POLICY_DECISION", "--capture-id", "reserved", "--store", str(tmp_path)]
    assert module.main(args) == 0
    capsys.readouterr()
    assert module.main(args) == 2
    assert len(calls) == 1
    assert "remote retry" in capsys.readouterr().err


def test_cli_help_works_with_src_only_pythonpath_without_transport_side_effect(tmp_path):
    import subprocess

    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    result = subprocess.run([sys.executable, str(SCRIPT), "--help"], cwd=ROOT,
                            env=env, text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stderr
    assert "--family" in result.stdout and "--capture-id" in result.stdout


def test_generated_program_executes_its_final_json_print_with_mocked_collector():
    source = (ROOT / "t480/first_party_policy_calendar_probe.py").read_bytes() + (
        b"\ncollect_policy_calendar = lambda family: {'family': family.value, 'mocked': True}\n"
    )
    spec = importlib.util.spec_from_file_location("policy_collect_program_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    program = module.probe_program(source, "ECB_POLICY_DECISION")
    output = StringIO()
    with redirect_stdout(output):
        exec(compile(program, "generated-policy-probe.py", "exec"), {"__name__": "generated_policy_probe"})
    assert json.loads(output.getvalue()) == {"family": "ECB_POLICY_DECISION", "mocked": True}


def test_symlinked_capture_root_is_refused_before_transport(tmp_path, monkeypatch, capsys):
    actual = tmp_path / "actual"
    actual.mkdir()
    link = tmp_path / "link"
    link.symlink_to(actual, target_is_directory=True)
    spec = importlib.util.spec_from_file_location("policy_collect_symlink_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    calls: list[object] = []
    monkeypatch.setitem(sys.modules, "t480_adapter", SimpleNamespace(
        Operation=lambda *args, **kwargs: kwargs,
        execute_operation=lambda *args, **kwargs: calls.append(args),
        target=lambda: "test-no-network",
        TRANSPORT_SETTINGS=SimpleNamespace(wsl_distribution="Ubuntu"),
    ))
    assert module.main(["--family", "FOMC_POLICY_DECISION", "--capture-id", "unsafe", "--store", str(link)]) == 2
    assert calls == []
    assert "unsafe" in capsys.readouterr().err


def test_supplied_reservation_revalidates_symlinked_root_before_writing(tmp_path):
    actual = tmp_path / "actual"
    actual.mkdir()
    link = tmp_path / "link"
    link.symlink_to(actual, target_is_directory=True)
    reservation = link / "policy-calendar-captures" / "reserved"
    reservation.mkdir(parents=True)
    with pytest.raises(PolicyCalendarCaptureError, match="unsafe"):
        retain_transport_result(link, capture_id="reserved", family=PolicyCalendarFamily.FOMC_POLICY_DECISION,
                                transport_observation=observed(envelope().decode()), reservation=reservation,
                                **hashes())
    assert not (reservation / "transport-observation.json").exists()


def test_durable_reservation_fsyncs_each_created_directory(tmp_path, monkeypatch):
    calls: list[int] = []
    monkeypatch.setattr(capture.os, "fsync", lambda fd: calls.append(fd))
    reserve_transport_capture(tmp_path / "one" / "two", capture_id="durable")
    # root/one, root/one/two, captures, and capture-id are each made durable;
    # every new directory fsyncs both itself and its parent.
    assert len(calls) >= 8
