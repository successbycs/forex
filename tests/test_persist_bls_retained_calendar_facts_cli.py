from __future__ import annotations

import hashlib
from pathlib import Path
from unittest import mock

import pytest

from forex.event_capture_store import retain_bls_capture
from scripts import persist_bls_retained_calendar_facts as command


def _raw_html() -> bytes:
    return ("<html><p>All release times are Eastern Time.</p><table>"
            "<tr><th>Reference Month</th><th>Release Date</th><th>Release Time</th></tr>"
            "<tr><td>November 2025</td><td>Dec. 18, 2025</td><td>08:30 AM</td></tr>"
            "</table></html>").encode()


def _retained_store(root: Path) -> Path:
    retain_bls_capture(root, capture_id="verified-cpi", raw=_raw_html(), source_family="CPI",
                       capture_completed_at_utc="2026-01-01T00:00:00Z")
    return root


def test_builds_only_existing_validated_retained_projection_payload(tmp_path):
    payload, raw, digest = command.build_payload(_retained_store(tmp_path))
    assert payload["schema_version"] == "forex.bls-calendar-fact-persistence-payload.v1"
    assert payload["execution_authority"] is False
    assert payload["facts"] and all(fact["fact_sha256"].startswith("sha256:") for fact in payload["facts"])
    assert digest == "sha256:" + hashlib.sha256(raw).hexdigest()


def test_missing_or_symlinked_store_refuses_before_transport(tmp_path):
    with pytest.raises(ValueError, match="unavailable"):
        command.build_payload(tmp_path / "missing")
    real = _retained_store(tmp_path / "real")
    linked = tmp_path / "linked"
    linked.symlink_to(real, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        command.build_payload(linked)


def test_stage_uses_only_fixed_windows_target_and_hash_checked_payload(monkeypatch):
    calls = []

    def fake_run(argv, **kwargs):
        calls.append(argv)
        if argv[0] == "wslpath":
            return mock.Mock(returncode=0, stdout=r"C:\temp\payload.json\n")
        return mock.Mock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(command.subprocess, "run", fake_run)
    raw = b'{"fixed":true}'
    command._stage_payload(raw, "sha256:" + hashlib.sha256(raw).hexdigest())
    assert any(call[0] == "wslpath" for call in calls)
    transfers = [call for call in calls if call[0] == "powershell.exe" and "-EncodedCommand" in call]
    assert len(transfers) == 1
    assert transfers[0][:4] == ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand"]


def test_remote_wrapper_has_fixed_sql_and_returns_only_bound_counts(tmp_path, monkeypatch):
    payload, _raw, digest = command.build_payload(_retained_store(tmp_path))
    stdout = (f"FOREX_BLS_CALENDAR_FACTS_PERSISTED journal_sha256:{payload['journal_sha256']} "
              f"created:2 existing:1 payload_sha256:{digest}\n")
    with mock.patch.object(command, "remote", return_value={"ok": True, "stdout": stdout, "stderr": ""}) as remote:
        result = command._remote_persist(payload, digest)
    assert result == {"journal_sha256": payload["journal_sha256"], "created_count": 2,
                      "existing_count": 1, "execution_authority": False}
    body = remote.call_args.args[0]
    assert command._STAGE_WSL_FILE in body and "sha256sum \"$source\"" in body
    assert "docker cp" in body and "base64 --decode" in body
    assert 'docker compose exec -T postgres chmod 0644 "/tmp/forex_bls_calendar_persistence_payload.json"' in body
    assert "curl" not in body and "mt5" not in body.lower() and "--sql" not in body


def test_persist_store_projects_before_stage_or_remote_write(tmp_path, monkeypatch):
    payload, raw, digest = command.build_payload(_retained_store(tmp_path))
    calls = []
    monkeypatch.setattr(command, "load_local_env", lambda: calls.append("env") or {})
    monkeypatch.setattr(command, "_stage_payload", lambda received, received_digest: calls.append((received, received_digest)))
    expected = {"journal_sha256": payload["journal_sha256"], "created_count": 1,
                "existing_count": 0, "execution_authority": False}
    monkeypatch.setattr(command, "_remote_persist", lambda received, received_digest: calls.append("remote") or expected)
    assert command.persist_store(tmp_path) == expected
    assert calls == ["env", (raw, digest), "remote"]


def test_cli_has_no_sql_or_broker_input_surface(tmp_path):
    with pytest.raises(SystemExit, match="2"):
        command.main(["--store", str(tmp_path), "--sql", "SELECT 1"])
