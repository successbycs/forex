import json
from pathlib import Path

import pytest

from forex.m20_history_capture import HistoryCaptureError, retain_history_response


def raw_history() -> bytes:
    deal = {"ticket": 1, "order": 1, "time": 1, "time_msc": 1, "type": 0, "entry": 0,
            "magic": 20260020, "position_id": 1, "reason": 3, "volume": .01, "price": 1.1,
            "commission": 0.0, "swap": 0.0, "profit": 0.0, "fee": 0.0, "symbol": "EURUSD",
            "comment": "forex-m20-demo", "external_id": ""}
    inner = {"ok": True, "complete": True, "captured_at_utc": "2026-09-12T00:00:00Z",
             "from_utc": "2000-01-01T00:00:00Z", "query_to_server_clock_utc": "2026-09-12T03:00:00Z",
             "server": "GOMarketsMU-Demo", "currency": "AUD", "account_scope_sha256": "a" * 64,
             "balance": 1.0, "equity": 1.0, "credit": 0.0, "broker_timestamp_offset_seconds": 10800,
             "deal_count": 1, "order_count": 1, "deals": [deal], "orders": [], "error": None}
    return json.dumps({"operation": "m20_all_demo_history_export", "approval_required": False, "approved": False,
                       "result": {"stdout": json.dumps(inner)}, "ok": True, "tool_id": "forex_t480",
                       "configuration_fingerprint": "sha256:" + "a" * 64,
                       "adapter_configuration_fingerprint": "sha256:" + "b" * 64}).encode()


def test_capture_retains_exact_response_report_and_receipt_idempotently(tmp_path):
    raw = raw_history()
    path, publication, report = retain_history_response(root=tmp_path, adapter_response_raw=raw)
    assert publication == "CREATED"
    assert (path / "adapter-response.json").read_bytes() == raw
    assert json.loads((path / "history-report.json").read_text())["source_sha256"] == report["source_sha256"]
    assert set(item.name for item in path.iterdir()) == {"adapter-response.json", "history-report.json", "receipt.json"}
    assert retain_history_response(root=tmp_path, adapter_response_raw=raw)[:2] == (path, "EXISTING")


def test_capture_refuses_conflict_or_untrusted_root(tmp_path):
    raw = raw_history()
    path, _, _ = retain_history_response(root=tmp_path, adapter_response_raw=raw)
    (path / "history-report.json").write_text("different")
    with pytest.raises(HistoryCaptureError, match="conflicts"):
        retain_history_response(root=tmp_path, adapter_response_raw=raw)
    outside = tmp_path / "outside"
    outside.mkdir()
    link = tmp_path / "link"
    link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(HistoryCaptureError, match="trusted"):
        retain_history_response(root=link, adapter_response_raw=raw)
