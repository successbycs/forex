"""Pure validation of the inactive fixed-v1 H_SLOW execution semantics."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


PROPOSAL_SCHEMA_VERSION = "forex.h-slow.execution-semantics-proposal.v1"
REPORT_SCHEMA_VERSION = "forex.h-slow.execution-semantics-report.v1"
_TOP_LEVEL = {
    "schema_version", "state", "stream_id", "server", "instrument", "policy_version",
    "decision_clock", "entry_lifecycle", "protection", "holding", "costs", "event_context",
    "risk_caps", "execution_authority",
}
_EXPECTED = {
    "schema_version": PROPOSAL_SCHEMA_VERSION,
    "state": "DRAFT_NOT_ACTIVE",
    "stream_id": "H_SLOW",
    "server": "GOMarketsMU-Demo",
    "instrument": "EUR/USD",
    "policy_version": "forex.h-slow.eurusd-tsmom-12m.v1",
    "decision_clock": {
        "cadence": "MONTHLY", "decision_at": "FIRST_UTC_DAY", "completed_data_only": True,
    },
    "entry_lifecycle": {
        "flat_directional_target": "OPEN_ONCE_ONLY", "unchanged_target": "HOLD_NO_NEW_ORDER",
        "opposite_target": "CLOSE_FIRST_NEXT_MONTH_OPEN_ONLY",
    },
    "protection": {
        "initial_stop": "ATR20X3_BROKER_SIDE", "widening": "PROHIBITED",
        "trailing": "PROHIBITED", "take_profit": "NONE",
    },
    "holding": {
        "end_date": "NONE", "ongoing_hold_requires": "BROKER_PROTECTION_AND_RECONCILIATION_HEALTHY",
        "overnight_weekend": "OBSERVED_TERMS_AND_PRE_POST_RECONCILIATION", "unknown_terms": "NO_NEW_ENTRY",
    },
    "costs": {"unknown_terms": "NO_NEW_ENTRY", "zero_assumption": "PROHIBITED"},
    "event_context": {"mode": "ANNOTATION_ONLY", "direction_or_entry_authority": "PROHIBITED"},
    "risk_caps": {"max_open_positions": 1, "cap_expansion": "PROHIBITED"},
    "execution_authority": False,
}


class HSlowExecutionSemanticsError(ValueError):
    """A proposed H_SLOW execution semantics contract is unsafe or incomplete."""


def _copy(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise HSlowExecutionSemanticsError("execution semantics proposal must be an object")
    try:
        copied = json.loads(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise HSlowExecutionSemanticsError("execution semantics proposal must be finite JSON") from exc
    if not isinstance(copied, dict):
        raise HSlowExecutionSemanticsError("execution semantics proposal must be an object")
    return copied


def _digest(value: Mapping[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _same_type_and_value(actual: Any, expected: Any) -> bool:
    """Compare a closed JSON contract without Python bool/int coercion."""
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(actual) == set(expected) and all(
            _same_type_and_value(actual[key], value) for key, value in expected.items()
        )
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            _same_type_and_value(item, value) for item, value in zip(actual, expected, strict=True)
        )
    return actual == expected


def validate_h_slow_execution_semantics(proposal: Mapping[str, Any]) -> dict[str, Any]:
    """Return a canonical validation report for the one inactive v1 proposal."""
    checked = _copy(proposal)
    if set(checked) != _TOP_LEVEL:
        raise HSlowExecutionSemanticsError("execution semantics proposal fields are invalid")
    for field, expected in _EXPECTED.items():
        if not _same_type_and_value(checked.get(field), expected):
            raise HSlowExecutionSemanticsError(f"execution semantics proposal {field} is invalid")
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "proposal_sha256": _digest(checked),
        "validation_state": "VALID_DRAFT_NOT_ACTIVE",
        "execution_authority": False,
    }
