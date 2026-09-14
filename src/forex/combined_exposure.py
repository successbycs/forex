"""Pure combined M1/H_SLOW exposure reporting with no execution capability."""
from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any, Mapping

from .stream_isolation import StreamIsolationError, validate_stream_registry


SCHEMA_VERSION = "forex.combined-exposure-report.v1"
_STREAMS = frozenset({"M1", "H_SLOW"})
_OPAQUE = re.compile(r"^[a-z][a-z0-9_-]{2,127}$")


class CombinedExposureError(ValueError):
    """A stream observation cannot safely support aggregate reporting."""


def _copy(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise CombinedExposureError("combined exposure input must be an object")
    try:
        copied = json.loads(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise CombinedExposureError("combined exposure input must be finite JSON") from exc
    if not isinstance(copied, dict):
        raise CombinedExposureError("combined exposure input must be an object")
    return copied


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise CombinedExposureError(f"{label} must be a positive finite number")
    return float(value)


def _digest(value: Mapping[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def combined_exposure_report(*, stream_registry: Mapping[str, Any], observations: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Return aggregate EUR/USD exposure only when both isolated streams reconcile.

    This is reporting only. It accepts neither limits nor any action/route
    field; an unknown stream state remains explicitly unknown rather than
    allowing a netted total to mask exposure.
    """
    try:
        plan = validate_stream_registry(stream_registry)
    except StreamIsolationError as exc:
        raise CombinedExposureError(f"invalid stream isolation: {exc}") from exc
    if not isinstance(observations, list) or len(observations) != len(_STREAMS):
        raise CombinedExposureError("one observation for each stream is required")
    declared = {row["stream_id"]: row for row in stream_registry["streams"]}
    normalized: dict[str, list[dict[str, Any]]] = {}
    states: dict[str, str] = {}
    for raw in observations:
        row = _copy(raw)
        if set(row) != {"stream_id", "account_scope", "terminal_instance", "reconciliation_status", "positions"}:
            raise CombinedExposureError("stream observation fields are invalid")
        stream_id = row.get("stream_id")
        if stream_id not in _STREAMS or stream_id in normalized:
            raise CombinedExposureError("stream observation identity is invalid")
        declared_row = declared[stream_id]
        if (row.get("account_scope") != declared_row["account_scope"]
                or row.get("terminal_instance") != declared_row["terminal_instance"]):
            raise CombinedExposureError("stream observation isolation scope mismatch")
        if row.get("reconciliation_status") not in {"RECONCILED", "UNKNOWN"} or not isinstance(row.get("positions"), list):
            raise CombinedExposureError("stream observation reconciliation state is invalid")
        positions: list[dict[str, Any]] = []
        tickets: set[str] = set()
        for position in row["positions"]:
            if not isinstance(position, dict) or set(position) != {"ticket_id", "owner_stream_id", "direction", "position_status", "notional_usd", "margin_aud", "maximum_loss_aud"}:
                raise CombinedExposureError("position exposure fields are invalid")
            ticket = position.get("ticket_id")
            if (not isinstance(ticket, str) or not _OPAQUE.fullmatch(ticket) or ticket in tickets
                    or position.get("owner_stream_id") != stream_id or position.get("direction") not in {"BUY", "SELL"}
                    or position.get("position_status") != "OPEN"):
                raise CombinedExposureError("position exposure identity is invalid")
            tickets.add(ticket)
            positions.append({**position, "notional_usd": _number(position["notional_usd"], "position notional_usd"),
                              "margin_aud": _number(position["margin_aud"], "position margin_aud"),
                              "maximum_loss_aud": _number(position["maximum_loss_aud"], "position maximum_loss_aud")})
        normalized[stream_id] = positions
        states[stream_id] = row["reconciliation_status"]
    if set(normalized) != _STREAMS:
        raise CombinedExposureError("one observation for each stream is required")
    content: dict[str, Any] = {"schema_version": SCHEMA_VERSION, "isolation_registry_fingerprint": plan.registry_fingerprint,
                               "stream_reconciliation": states, "execution_authority": False}
    if "UNKNOWN" in states.values():
        content.update({"report_state": "RECONCILIATION_REQUIRED", "positions": None, "gross_notional_usd": None,
                        "net_notional_usd": None, "margin_aud": None, "maximum_loss_aud": None})
    else:
        positions = [dict(position, stream_id=stream_id) for stream_id in sorted(normalized) for position in normalized[stream_id]]
        content.update({"report_state": "RECONCILED", "positions": positions,
                        "gross_notional_usd": sum(item["notional_usd"] for item in positions),
                        "net_notional_usd": sum(item["notional_usd"] if item["direction"] == "BUY" else -item["notional_usd"] for item in positions),
                        "margin_aud": sum(item["margin_aud"] for item in positions),
                        "maximum_loss_aud": sum(item["maximum_loss_aud"] for item in positions)})
    return {**content, "report_sha256": _digest(content)}
