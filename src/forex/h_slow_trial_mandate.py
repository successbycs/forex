"""Non-operational validation of a human-completed H_SLOW Demo trial mandate."""
from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any, Mapping

from .h_slow_policy import POLICY_VERSION
from .stream_isolation import DEMO_SERVER, IsolationPlan, validate_stream_registry


MANDATE_SCHEMA_VERSION = "forex.h-slow.demo-trial-mandate.v1"
_OPAQUE = re.compile(r"^[a-z][a-z0-9_-]{2,127}$")


class HSlowMandateError(ValueError):
    """A pre-activation mandate is incomplete, unsafe or implies activation."""


def _canonical_copy(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise HSlowMandateError("mandate must be a mapping")
    try:
        copied = json.loads(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise HSlowMandateError("mandate must be JSON-safe") from exc
    if not isinstance(copied, dict):
        raise HSlowMandateError("mandate must be an object")
    return copied


def _opaque(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _OPAQUE.fullmatch(value) or value.isdecimal():
        raise HSlowMandateError(f"{field} must be a non-secret opaque identifier")
    return value


def _positive(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise HSlowMandateError(f"{field} must be a positive finite number")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise HSlowMandateError(f"{field} must be a positive finite number") from exc
    if not math.isfinite(number) or number <= 0:
        raise HSlowMandateError(f"{field} must be a positive finite number")
    return number


def _fingerprint(value: dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def validate_h_slow_trial_mandate(
    mandate: Mapping[str, Any], *, stream_registry: Mapping[str, Any]
) -> dict[str, Any]:
    """Validate a completed trial mandate while explicitly refusing activation.

    The only accepted state is ``PRE_ACTIVATION_REVIEWED``.  This validates
    human-supplied references and limits; it neither writes them to runtime
    configuration nor turns any reference into a broker account or route.
    """
    plan: IsolationPlan = validate_stream_registry(stream_registry)
    snapshot = _canonical_copy(mandate)
    expected = {
        "schema_version", "state", "server", "account_scope", "terminal_instance",
        "policy_version", "operator_approval_reference", "risk_resume_authority_reference",
        "limits", "rule_references",
    }
    if set(snapshot) != expected:
        raise HSlowMandateError("mandate fields are invalid")
    if snapshot["schema_version"] != MANDATE_SCHEMA_VERSION:
        raise HSlowMandateError("unsupported mandate schema version")
    if snapshot["state"] != "PRE_ACTIVATION_REVIEWED":
        raise HSlowMandateError("mandate must remain PRE_ACTIVATION_REVIEWED")
    if snapshot["server"] != DEMO_SERVER:
        raise HSlowMandateError("H_SLOW mandate must use GOMarketsMU-Demo")
    if snapshot["policy_version"] != POLICY_VERSION:
        raise HSlowMandateError("mandate policy version does not match H_SLOW v1")
    for field in (
        "account_scope", "terminal_instance", "operator_approval_reference",
        "risk_resume_authority_reference",
    ):
        _opaque(snapshot[field], field)

    if not isinstance(snapshot["limits"], dict) or set(snapshot["limits"]) != {
        "max_open_positions", "max_loss_aud", "max_notional_usd", "lease_budget_usd",
    }:
        raise HSlowMandateError("mandate limits are invalid")
    if type(snapshot["limits"]["max_open_positions"]) is not int or snapshot["limits"]["max_open_positions"] != 1:
        raise HSlowMandateError("H_SLOW trial mandate must cap itself at one position")
    for field in ("max_loss_aud", "max_notional_usd", "lease_budget_usd"):
        _positive(snapshot["limits"][field], f"limits.{field}")

    if not isinstance(snapshot["rule_references"], dict) or set(snapshot["rule_references"]) != {
        "sizing", "protection", "holding_exit", "financing_cost", "reconciliation",
    }:
        raise HSlowMandateError("mandate rule_references are invalid")
    for name, reference in snapshot["rule_references"].items():
        _opaque(reference, f"rule_references.{name}")

    hslow = next(stream for stream in stream_registry["streams"] if stream["stream_id"] == "H_SLOW")
    if (snapshot["account_scope"] != hslow["account_scope"]
            or snapshot["terminal_instance"] != hslow["terminal_instance"]):
        raise HSlowMandateError("mandate scope does not match the isolated H_SLOW declaration")
    content = {"mandate": snapshot, "stream_registry_fingerprint": plan.registry_fingerprint}
    return {
        "mandate_schema_version": MANDATE_SCHEMA_VERSION,
        "preflight_status": "PRE_ACTIVATION_MANDATE_VALIDATED",
        "mandate_sha256": _fingerprint(content),
        "stream_registry_fingerprint": plan.registry_fingerprint,
        "execution_authority": False,
    }
