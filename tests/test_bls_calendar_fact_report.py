from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from forex.bls_calendar_fact_report import BLSCalendarFactReportError, build_bls_calendar_fact_report
from forex.calendar_fact_persistence import canonical_fact
from scripts import postgres_admin_adapter


ROOT = Path(__file__).resolve().parents[1]


def _fact(**changes):
    capture = {
        "capture_id": "capture-1",
        "capture_completed_at_utc": "2026-09-13T00:00:00Z",
        "payload_sha256": "sha256:" + "1" * 64,
        "content_sha256": "sha256:" + "3" * 64,
        "source_family": "CPI",
        "source_url": "https://www.bls.gov/schedule/2026/09_sched_list.htm",
        "parser_version": "bls.monthly.v1",
        "receipt_sha256": "sha256:" + "2" * 64,
    }
    value = {
        "source_family": "CPI",
        "source_url": capture["source_url"],
        "capture_completed_at_utc": capture["capture_completed_at_utc"],
        "raw_sha256": capture["payload_sha256"],
        "receipt_sha256": capture["receipt_sha256"],
        "event_identifier": "cpi-2026-10",
        "scheduled_at_utc": "2026-10-01T12:30:00Z",
        "event_title": "Consumer Price Index",
        "country_code": "US",
        "currency_code": "USD",
        "impact": "UNKNOWN",
        "qualification_state": "QUALIFIED",
        "qualification_reason": None,
        "source_revision": 1,
        "event_payload": {
            "event_revision": {
                "event_id": "cpi-2026-10", "event_name": "Consumer Price Index",
                "source_url": capture["source_url"], "payload_sha256": capture["payload_sha256"],
                "available_at_utc": capture["capture_completed_at_utc"], "origin_capture_id": capture["capture_id"],
                "revision": 1,
            },
            "capture_provenance": capture,
        },
    }
    return {**value, **changes}


def _row(**changes):
    fact = _fact(**changes)
    return {"fact_sha256": canonical_fact(fact)["fact_sha256"], **fact}


def _rehash(row):
    fact = {key: value for key, value in row.items() if key != "fact_sha256"}
    row["fact_sha256"] = canonical_fact(fact)["fact_sha256"]
    return row


def test_reports_only_recomputed_lineaged_bls_facts():
    report = build_bls_calendar_fact_report({"schema_present": True, "rows": [_row()]})
    assert report["status"] == "BLS_FACTS_RETRIEVED"
    assert report["execution_authority"] is False
    assert report["facts"] == [{
        "fact_sha256": _row()["fact_sha256"], "source_family": "CPI",
        "source_url": "https://www.bls.gov/schedule/2026/09_sched_list.htm",
        "capture_completed_at_utc": "2026-09-13T00:00:00Z", "raw_sha256": "sha256:" + "1" * 64,
        "receipt_sha256": "sha256:" + "2" * 64, "event_identifier": "cpi-2026-10",
        "scheduled_at_utc": "2026-10-01T12:30:00Z", "event_title": "Consumer Price Index",
        "qualification_state": "QUALIFIED", "qualification_reason": None, "source_revision": 1,
    }]


def test_missing_schema_and_empty_table_are_distinct_non_authorising_results():
    missing = build_bls_calendar_fact_report({"schema_present": False, "rows": []})
    empty = build_bls_calendar_fact_report({"schema_present": True, "rows": []})
    assert (missing["status"], empty["status"]) == ("CALENDAR_FACT_SCHEMA_UNAVAILABLE", "NO_STORED_BLS_FACTS")
    assert missing["execution_authority"] is empty["execution_authority"] is False


@pytest.mark.parametrize("change", [
    {"fact_sha256": "sha256:" + "0" * 64},
    {"source_url": "https://example.invalid/calendar"},
    {"event_payload": {"capture_provenance": {}}},
])
def test_refuses_tampered_or_unbound_database_rows(change):
    row = _row()
    row.update(change)
    with pytest.raises(BLSCalendarFactReportError):
        build_bls_calendar_fact_report({"schema_present": True, "rows": [row]})


@pytest.mark.parametrize("path,value", [
    (("capture_provenance", "capture_id"), ""),
    (("capture_provenance", "parser_version"), 1),
    (("capture_provenance", "content_sha256"), "sha256:bad"),
    (("event_revision", "event_id"), "other-event"),
    (("event_revision", "event_name"), "Other event"),
    (("event_revision", "source_url"), "https://www.bls.gov/schedule/other.htm"),
    (("event_revision", "payload_sha256"), "sha256:" + "9" * 64),
    (("event_revision", "available_at_utc"), "2026-09-14T00:00:00Z"),
    (("event_revision", "origin_capture_id"), "other-capture"),
    (("event_revision", "revision"), 2),
])
def test_rehashed_row_cannot_substitute_nested_capture_or_event_revision_lineage(path, value):
    row = _row()
    row["event_payload"][path[0]][path[1]] = value
    with pytest.raises(BLSCalendarFactReportError):
        build_bls_calendar_fact_report({"schema_present": True, "rows": [_rehash(row)]})


def test_fixed_database_adapter_checks_schema_then_uses_only_bls_query(monkeypatch):
    monkeypatch.setattr(postgres_admin_adapter, "load_local_env", lambda: {})
    calls: list[str] = []
    responses = iter([
        {"ok": True, "stdout": "t\n", "stderr": ""},
        {"ok": True, "stdout": "[]", "stderr": ""},
    ])
    monkeypatch.setattr(postgres_admin_adapter, "_psql", lambda query: (calls.append(query), next(responses))[1])
    assert postgres_admin_adapter.read_bls_calendar_facts() == {"schema_present": True, "rows": []}
    assert "to_regclass('forex.economic_calendar_event_fact')" in calls[0]
    assert "FROM forex.economic_calendar_event_fact" in calls[1]
    assert "source_family IN ('CPI','EMPLOYMENT_SITUATION','BLS_MONTHLY')" in calls[1]
    assert "LIMIT 100" in calls[1]


def test_fixed_database_adapter_reports_absent_schema_without_fact_query(monkeypatch):
    monkeypatch.setattr(postgres_admin_adapter, "load_local_env", lambda: {})
    calls: list[str] = []
    monkeypatch.setattr(postgres_admin_adapter, "_psql", lambda query: (calls.append(query), {"ok": True, "stdout": "f\n", "stderr": ""})[1])
    assert postgres_admin_adapter.read_bls_calendar_facts() == {"schema_present": False, "rows": []}
    assert len(calls) == 1


def test_command_has_no_input_surface_and_emits_validated_report(monkeypatch, capsys):
    path = ROOT / "scripts" / "report_bls_calendar_facts.py"
    spec = importlib.util.spec_from_file_location("report_bls_calendar_facts_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "read_bls_calendar_facts", lambda: {"schema_present": True, "rows": [_row()]})
    assert module.main([]) == 0
    assert json.loads(capsys.readouterr().out)["fact_count"] == 1
    assert module.main(["--anything"]) == 2
