import json
from pathlib import Path
import subprocess
import sys

import pytest

from forex.m20_history_report import HistoryReportInputError, build_history_report


ROOT = Path(__file__).resolve().parents[1]


def source(*, deal_rows):
    inner = {"ok": True, "captured_at_utc": "2026-09-10T08:44:25Z", "server": "GOMarketsMU-Demo",
             "currency": "AUD", "broker_timestamp_offset_seconds": 10800, "deals": deal_rows,
             "orders": [], "error": None}
    return json.dumps({"operation": "m20_wave1_history", "approval_required": False, "approved": False,
                       "result": {"stdout": json.dumps(inner)}, "ok": True, "tool_id": "forex_t480",
                       "configuration_fingerprint": "sha256:" + "a" * 64,
                       "adapter_configuration_fingerprint": "sha256:" + "b" * 64}).encode()


def deal(*, ticket, entry, position_id, profit, reason=3, comment="forex-m20-demo"):
    return {"ticket": ticket, "order": ticket, "time": 1, "time_msc": ticket, "type": 0, "entry": entry,
            "magic": 20260020, "position_id": position_id, "reason": reason, "volume": .01, "price": 1.1,
            "commission": 0.0, "swap": 0.0, "profit": profit, "fee": 0.0, "symbol": "EURUSD", "comment": comment}


def test_history_summary_pairs_exact_positions_and_preserves_incomplete_ones():
    raw = source(deal_rows=[deal(ticket=1, entry=0, position_id=11, profit=0),
                             deal(ticket=2, entry=1, position_id=11, profit=-.3, reason=4, comment="[sl 1.1]"),
                             deal(ticket=3, entry=0, position_id=12, profit=0)])
    report = build_history_report(raw)
    assert report["closed_position_count"] == 1
    assert report["incomplete_positions"] == [{"position_id": 12, "entry_deal_count": 1, "exit_deal_count": 0}]
    assert report["net_realized_aud"] == -.3
    assert report["losses"] == 1
    assert report["stop_loss_like_exit_count"] == 1
    assert report["financial_conclusion"] == "NOT_EVALUATED_RETAINED_HISTORY_ONLY"
    assert report["execution_authority"] is False


def test_history_summary_refuses_duplicate_json_and_scope_drift():
    with pytest.raises(HistoryReportInputError, match="duplicate"):
        build_history_report(b'{"operation":"m20_wave1_history","operation":"other"}')
    wrong = json.loads(source(deal_rows=[]))
    wrong["result"]["stdout"] = json.dumps({"ok": True, "server": "GOMarketsMU-Live"})
    with pytest.raises(HistoryReportInputError, match="scope"):
        build_history_report(json.dumps(wrong).encode())


def test_complete_history_variant_accepts_only_its_named_schema_and_excludes_other_scopes():
    all_deal = {**deal(ticket=1, entry=0, position_id=11, profit=0), "external_id": ""}
    other_deal = {**deal(ticket=2, entry=0, position_id=0, profit=1), "symbol": "", "magic": 0,
                  "comment": "Demo Form Deposit", "external_id": ""}
    inner = {"ok": True, "complete": True, "captured_at_utc": "2026-09-12T00:00:00Z",
             "from_utc": "2000-01-01T00:00:00Z", "query_to_server_clock_utc": "2026-09-12T03:00:00Z",
             "server": "GOMarketsMU-Demo", "currency": "AUD", "account_scope_sha256": "a" * 64,
             "balance": 1.0, "equity": 1.0, "credit": 0.0, "broker_timestamp_offset_seconds": 10800,
             "deal_count": 2, "order_count": 2, "deals": [all_deal, other_deal], "orders": [], "error": None}
    outer = json.loads(source(deal_rows=[]))
    outer["operation"] = "m20_all_demo_history_export"
    outer["result"]["stdout"] = json.dumps(inner)
    report = build_history_report(json.dumps(outer).encode())
    assert report["history_operation"] == "m20_all_demo_history_export"
    assert report["source_deal_count"] == 2
    assert report["deal_count"] == 1
    assert report["excluded_non_m20_eurusd_deal_count"] == 1


def test_history_cli_is_read_only(tmp_path):
    path = tmp_path / "history.json"
    raw = source(deal_rows=[])
    path.write_bytes(raw)
    process = subprocess.run([sys.executable, "scripts/m20_history_report.py", str(path)], cwd=ROOT,
                             text=True, capture_output=True, check=False)
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout)["deal_count"] == 0
    assert path.read_bytes() == raw
