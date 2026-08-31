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
