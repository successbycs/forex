"""Strict, read-only summary of a fixed M20 Demo history export."""
from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "forex.m20.history-report.v1"
_OUTER_KEYS = {"operation", "approval_required", "approved", "result", "ok", "tool_id", "configuration_fingerprint", "adapter_configuration_fingerprint"}
_WAVE1_INNER_KEYS = {"ok", "captured_at_utc", "server", "currency", "broker_timestamp_offset_seconds", "deals", "orders", "error"}
_ALL_HISTORY_INNER_KEYS = {"ok", "complete", "captured_at_utc", "from_utc", "query_to_server_clock_utc", "server", "currency", "account_scope_sha256", "balance", "equity", "credit", "broker_timestamp_offset_seconds", "deal_count", "order_count", "deals", "orders", "error"}
_WAVE1_DEAL_KEYS = {"ticket", "order", "time", "time_msc", "type", "entry", "magic", "position_id", "reason", "volume", "price", "commission", "swap", "profit", "fee", "symbol", "comment"}
_ALL_HISTORY_DEAL_KEYS = _WAVE1_DEAL_KEYS | {"external_id"}


class HistoryReportInputError(ValueError):
    """A fixed M20 history export is malformed or out of its declared scope."""


def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in items:
        if key in value:
            raise HistoryReportInputError("duplicate JSON field")
        value[key] = item
    return value


def _json(raw: bytes | str) -> Any:
    try:
        return json.loads(raw, object_pairs_hook=_pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(HistoryReportInputError("nonfinite JSON value")))
    except (TypeError, json.JSONDecodeError) as exc:
        raise HistoryReportInputError("history export is not valid JSON") from exc


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise HistoryReportInputError(f"{label} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise HistoryReportInputError(f"{label} must be finite")
    return number


def _history(value: Any) -> tuple[dict[str, Any], list[dict[str, Any]], int]:
    if not isinstance(value, dict) or set(value) != _OUTER_KEYS or value.get("operation") not in {"m20_wave1_history", "m20_all_demo_history_export"}:
        raise HistoryReportInputError("history export outer binding is invalid")
    all_history = value["operation"] == "m20_all_demo_history_export"
    result = value.get("result")
    if not isinstance(result, dict) or not isinstance(result.get("stdout"), str):
        raise HistoryReportInputError("history export has no fixed stdout")
    inner = _json(result["stdout"])
    expected_inner = _ALL_HISTORY_INNER_KEYS if all_history else _WAVE1_INNER_KEYS
    if (not isinstance(inner, dict) or set(inner) != expected_inner or inner.get("ok") is not True
            or inner.get("server") != "GOMarketsMU-Demo" or inner.get("currency") != "AUD"
            or not isinstance(inner.get("deals"), list)):
        raise HistoryReportInputError("history export scope is invalid")
    if all_history and (inner.get("complete") is not True or inner.get("deal_count") != len(inner["deals"])):
        raise HistoryReportInputError("complete history export is incomplete")
    deals: list[dict[str, Any]] = []
    excluded_count = 0
    expected_deal = _ALL_HISTORY_DEAL_KEYS if all_history else _WAVE1_DEAL_KEYS
    for index, deal in enumerate(inner["deals"]):
        if not isinstance(deal, dict) or set(deal) != expected_deal:
            raise HistoryReportInputError(f"deal {index} shape is invalid")
        for field in ("profit", "commission", "swap", "fee"):
            _number(deal[field], f"deal {index} {field}")
        if deal.get("symbol") != "EURUSD" or deal.get("magic") != 20260020:
            if not all_history:
                raise HistoryReportInputError(f"deal {index} binding is invalid")
            excluded_count += 1
            continue
        if (type(deal.get("entry")) is not int or deal["entry"] not in {0, 1}
                or type(deal.get("position_id")) is not int or deal["position_id"] <= 0
                or not isinstance(deal.get("comment"), str)):
            raise HistoryReportInputError(f"deal {index} binding is invalid")
        deals.append(deal)
    return inner, deals, excluded_count


def build_history_report(raw: bytes) -> dict[str, Any]:
    """Summarise exact paired positions without inferring missing broker facts."""
    if not isinstance(raw, bytes):
        raise HistoryReportInputError("history raw input must be bytes")
    inner, deals, excluded_count = _history(_json(raw))
    positions: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for deal in deals:
        positions[deal["position_id"]].append(deal)
    closed: list[dict[str, Any]] = []
    incomplete: list[dict[str, Any]] = []
    for position_id, rows in sorted(positions.items()):
        entries = [row for row in rows if row["entry"] == 0]
        exits = [row for row in rows if row["entry"] == 1]
        if len(entries) != 1 or len(exits) != 1:
            incomplete.append({"position_id": position_id, "entry_deal_count": len(entries), "exit_deal_count": len(exits)})
            continue
        exit_deal = exits[0]
        net = sum(_number(row[field], field) for row in rows for field in ("profit", "commission", "swap", "fee"))
        closed.append({
            "position_id": position_id,
            "entry_ticket": entries[0]["ticket"],
            "exit_ticket": exit_deal["ticket"],
            "net_realized_aud": round(net, 2),
            "exit_reason": exit_deal["reason"],
            "stop_loss_like_exit": exit_deal["reason"] == 4 or exit_deal["comment"].startswith("[sl "),
        })
    return {
        "schema_version": SCHEMA_VERSION,
        "source_sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
        "captured_at_utc": inner["captured_at_utc"],
        "server": inner["server"],
        "currency": inner["currency"],
        "history_operation": "m20_all_demo_history_export" if "complete" in inner else "m20_wave1_history",
        "source_deal_count": len(inner["deals"]),
        "excluded_non_m20_eurusd_deal_count": excluded_count,
        "deal_count": len(deals),
        "position_count": len(positions),
        "closed_position_count": len(closed),
        "incomplete_positions": incomplete,
        "net_realized_aud": round(sum(item["net_realized_aud"] for item in closed), 2),
        "wins": sum(item["net_realized_aud"] > 0 for item in closed),
        "losses": sum(item["net_realized_aud"] < 0 for item in closed),
        "flat": sum(item["net_realized_aud"] == 0 for item in closed),
        "stop_loss_like_exit_count": sum(item["stop_loss_like_exit"] for item in closed),
        "broker_commission_total_aud": round(sum(_number(item["commission"], "commission") for item in deals), 2),
        "broker_fee_total_aud": round(sum(_number(item["fee"], "fee") for item in deals), 2),
        "broker_swap_total_aud": round(sum(_number(item["swap"], "swap") for item in deals), 2),
        "financial_conclusion": "NOT_EVALUATED_RETAINED_HISTORY_ONLY",
        "closed_positions": closed,
        "execution_authority": False,
    }


def load_and_build_history_report(path: Path) -> dict[str, Any]:
    if not isinstance(path, Path) or path.is_symlink() or not path.is_file():
        raise HistoryReportInputError("history source must be a regular non-symlink file")
    try:
        return build_history_report(path.read_bytes())
    except OSError as exc:
        raise HistoryReportInputError("history source cannot be read") from exc
