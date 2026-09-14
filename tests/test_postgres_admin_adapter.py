import base64
from unittest import mock

import pytest

from scripts import postgres_admin_adapter


def test_adapter_limits_access_to_the_forex_table_catalog(monkeypatch):
    monkeypatch.setattr(postgres_admin_adapter, "load_local_env", lambda: {})
    with mock.patch.object(postgres_admin_adapter, "remote", return_value={"ok": True, "stdout": "[]", "stderr": ""}) as remote:
        assert postgres_admin_adapter.run("preview", "price_bar", 20)["result"] == []
    query = remote.call_args.args[0]
    assert "forex.price_bar" in query
    assert "LIMIT 20" in query


def test_source_registry_write_is_an_explicit_upsert(monkeypatch):
    monkeypatch.setattr(postgres_admin_adapter, "load_local_env", lambda: {})
    payload = {column: ([] if column == "endpoint_allowlist" else "value") for column in postgres_admin_adapter.WRITE_COLUMNS["source_registry"]}
    with mock.patch.object(postgres_admin_adapter, "remote", return_value={"ok": True, "stdout": '{"written": true}', "stderr": ""}) as remote:
        assert postgres_admin_adapter.run("write", "source_registry", 20, payload)["result"]["written"] is True
    query = remote.call_args.args[0]
    assert "INSERT INTO forex.source_registry" in query
    assert "ON CONFLICT (source_id) DO UPDATE" in query


def test_write_rejects_unknown_columns():
    with pytest.raises(RuntimeError, match="exactly match"):
        postgres_admin_adapter._write_sql("price_bar", {"unknown": "value"})


def test_export_html_writes_all_table_sections(tmp_path, monkeypatch):
    monkeypatch.setattr(postgres_admin_adapter, "ROOT", tmp_path)
    monkeypatch.setattr(postgres_admin_adapter, "load_local_env", lambda: {})
    def run(command, table, limit):
        if command == "tables":
            return {"result": list(postgres_admin_adapter.TABLES)}
        return {"result": [{"id": table}]}
    monkeypatch.setattr(postgres_admin_adapter, "run", run)
    output = postgres_admin_adapter.export_html(tmp_path / "reports" / "export.html")
    content = output.read_text(encoding="utf-8")
    assert "Forex research data view" in content
    assert "Read-only research summary" in content
    assert "EUR/USD H1 coverage" in content
    assert "GDELT H1 context" in content
    assert "Alignment coverage" in content
    assert "DEMO_ONLY historical research data" in content
    assert all(table in content for table in postgres_admin_adapter.TABLES)


def test_adapter_rejects_unknown_table_from_the_cli():
    with pytest.raises(SystemExit, match="2"):
        postgres_admin_adapter.main(["preview", "--table", "not_a_table"])


def test_calendar_fact_schema_apply_is_fixed_and_hash_pinned(monkeypatch):
    monkeypatch.setattr(postgres_admin_adapter, "load_local_env", lambda: {})
    monkeypatch.setattr(postgres_admin_adapter, "_stage_calendar_fact_schema", lambda: None)
    marker = "FOREX_CALENDAR_FACT_SCHEMA_APPLIED sha256:" + postgres_admin_adapter._CALENDAR_FACT_SCHEMA_SHA256
    with mock.patch.object(postgres_admin_adapter, "remote", return_value={"ok": True, "stdout": marker + "\n", "stderr": ""}) as remote:
        result = postgres_admin_adapter.apply_calendar_fact_schema()
    assert result == {
        "operation": "forex-calendar-fact-schema-apply",
        "schema_sha256": "sha256:" + postgres_admin_adapter._CALENDAR_FACT_SCHEMA_SHA256,
        "status": "APPLIED",
        "execution_authority": False,
    }
    command = remote.call_args.args[0]
    assert "wrapper=/mnt/c/Users/chris/Documents/Code/forex-calendar-schema/t480_apply_calendar_fact_schema.sh" in command
    assert "[ -f \"$wrapper\" ] && [ ! -L \"$wrapper\" ]" in command
    assert postgres_admin_adapter._CALENDAR_FACT_WRAPPER_SHA256 in command
    assert "sha256sum \"$wrapper\"" in command
    assert "bash \"$wrapper\"" in command


def test_calendar_fact_schema_apply_uses_no_caller_controlled_remote_body(monkeypatch):
    monkeypatch.setattr(postgres_admin_adapter, "load_local_env", lambda: {})
    monkeypatch.setattr(postgres_admin_adapter, "_stage_calendar_fact_schema", lambda: None)
    digest = postgres_admin_adapter._CALENDAR_FACT_SCHEMA_SHA256
    stdout = f"FOREX_CALENDAR_FACT_SCHEMA_APPLIED sha256:{digest}\n"
    with mock.patch.object(postgres_admin_adapter, "remote", return_value={"ok": True, "stdout": stdout, "stderr": ""}) as remote:
        postgres_admin_adapter.apply_calendar_fact_schema()
    command = remote.call_args.args[0]
    assert "bash \"$wrapper\"" in command
    assert "INSERT INTO" not in command and "curl" not in command and "mt5" not in command.lower()


def test_calendar_fact_schema_stage_uses_only_the_fixed_file_and_t480_path(monkeypatch):
    calls = []

    def fake_run(argv, **kwargs):
        calls.append(argv)
        if argv[0] == "wslpath":
            return mock.Mock(returncode=0, stdout=r"C:\repo\sql\economic_calendar_facts.sql\n")
        return mock.Mock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(postgres_admin_adapter.subprocess, "run", fake_run)
    postgres_admin_adapter._stage_calendar_fact_schema()
    wslpaths = [call for call in calls if call[0] == "wslpath"]
    assert wslpaths == [
        ["wslpath", "-w", str(postgres_admin_adapter.ROOT / "sql/economic_calendar_facts.sql")],
        ["wslpath", "-w", str(postgres_admin_adapter.ROOT / "scripts/t480_apply_calendar_fact_schema.sh")],
    ]
    transfers = [call for call in calls if call[0] == "powershell.exe" and "-EncodedCommand" in call]
    assert len(transfers) == 2
    assert all(call[:4] == ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand"] for call in transfers)
    assert all(isinstance(call[4], str) and call[4] for call in transfers)


def test_calendar_fact_schema_stage_rejects_hash_drift_before_any_transfer(monkeypatch):
    monkeypatch.setattr(postgres_admin_adapter, "_CALENDAR_FACT_SCHEMA_SHA256", "0" * 64)
    with mock.patch.object(postgres_admin_adapter.subprocess, "run") as run:
        with pytest.raises(RuntimeError, match="hash"):
            postgres_admin_adapter._stage_calendar_fact_schema()
    run.assert_not_called()


def test_calendar_fact_schema_apply_accepts_an_already_staged_identical_file(monkeypatch):
    monkeypatch.setattr(postgres_admin_adapter, "load_local_env", lambda: {})
    monkeypatch.setattr(postgres_admin_adapter, "_stage_calendar_fact_schema", lambda: None)
    digest = postgres_admin_adapter._CALENDAR_FACT_SCHEMA_SHA256
    stdout = f"FOREX_CALENDAR_FACT_SCHEMA_APPLIED sha256:{digest}\n"
    with mock.patch.object(postgres_admin_adapter, "remote", return_value={"ok": True, "stdout": stdout, "stderr": ""}):
        assert postgres_admin_adapter.apply_calendar_fact_schema()["status"] == "APPLIED"


def test_calendar_fact_schema_apply_refuses_local_hash_drift_before_transport(monkeypatch):
    monkeypatch.setattr(postgres_admin_adapter, "_CALENDAR_FACT_SCHEMA_SHA256", "0" * 64)
    with mock.patch.object(postgres_admin_adapter, "remote") as remote:
        with pytest.raises(RuntimeError, match="hash"):
            postgres_admin_adapter.apply_calendar_fact_schema()
    remote.assert_not_called()


def test_calendar_fact_schema_apply_refuses_missing_remote_success_marker(monkeypatch):
    monkeypatch.setattr(postgres_admin_adapter, "load_local_env", lambda: {})
    monkeypatch.setattr(postgres_admin_adapter, "_stage_calendar_fact_schema", lambda: None)
    with mock.patch.object(postgres_admin_adapter, "remote", return_value={"ok": True, "stdout": "unexpected", "stderr": ""}):
        with pytest.raises(RuntimeError, match="invalid result"):
            postgres_admin_adapter.apply_calendar_fact_schema()


def test_calendar_fact_schema_cli_accepts_no_options(monkeypatch):
    monkeypatch.setattr(postgres_admin_adapter, "apply_calendar_fact_schema", lambda: {"status": "APPLIED"})
    assert postgres_admin_adapter.main(["apply-calendar-fact-schema"]) == 0
    with pytest.raises(SystemExit, match="2"):
        postgres_admin_adapter.main(["apply-calendar-fact-schema", "--limit", "1"])
