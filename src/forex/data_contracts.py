"""Canonical, point-in-time-safe contracts for historical Forex research.

M2 deliberately defines data contracts rather than an adapter or download API.
Every object is JSON-friendly, hashable, and rejects fields that would make a
historical decision depend on information not available at its UTC cutoff.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Iterable


CONTRACT_VERSION = "forex.historical-data.v1"
UTC = timezone.utc


class ContractError(ValueError):
    """A historical-research contract is incomplete or unsafe."""


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def sha256(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value)).hexdigest()


def _utc(value: Any, label: str) -> datetime:
    if not isinstance(value, str):
        raise ContractError(f"{label} must be an RFC3339 UTC string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError(f"{label} is not a timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise ContractError(f"{label} must be UTC")
    return parsed.astimezone(UTC)


def _exact_keys(value: dict[str, Any], required: set[str], label: str) -> None:
    missing, extra = required - value.keys(), value.keys() - required
    if missing or extra:
        raise ContractError(f"{label} fields mismatch; missing={sorted(missing)}, extra={sorted(extra)}")


SOURCE_REGISTRY_FIELDS = {
    "contract_version", "source_id", "owner", "license", "cost_model", "api_version",
    "endpoint_allowlist", "rate_limit", "retention_rule", "historical_depth", "revision_support",
    "timezone_policy", "outage_policy", "approval_status", "secrets_reference", "provenance_note",
}


def validate_source_registry_entry(entry: dict[str, Any]) -> dict[str, Any]:
    _exact_keys(entry, SOURCE_REGISTRY_FIELDS, "source registry entry")
    if entry["contract_version"] != CONTRACT_VERSION:
        raise ContractError("unsupported source registry contract version")
    for field in SOURCE_REGISTRY_FIELDS - {"endpoint_allowlist"}:
        if not isinstance(entry[field], str) or not entry[field].strip():
            raise ContractError(f"source registry {field} must be a non-empty string")
    if not isinstance(entry["endpoint_allowlist"], list) or not all(isinstance(x, str) for x in entry["endpoint_allowlist"]):
        raise ContractError("source registry endpoint_allowlist must be a list of strings")
    if entry["approval_status"] not in {"DEMO_ONLY", "PENDING_QUALIFICATION", "APPROVED"}:
        raise ContractError("source registry approval_status is invalid")
    if entry["secrets_reference"] != "NONE" and not entry["secrets_reference"].startswith("ENV:"):
        raise ContractError("source registry secrets_reference must be NONE or an environment reference")
    return entry


RAW_OBSERVATION_FIELDS = {
    "contract_version", "observation_id", "source_id", "source_revision", "observed_at_utc",
    "available_at_utc", "retrieved_at_utc", "timezone", "payload_sha256", "payload_path", "redacted",
}


def validate_raw_observation(observation: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    validate_source_registry_entry(source)
    _exact_keys(observation, RAW_OBSERVATION_FIELDS, "raw observation")
    if observation["contract_version"] != CONTRACT_VERSION or observation["source_id"] != source["source_id"]:
        raise ContractError("raw observation contract or source does not match registry")
    for field in ("observation_id", "source_revision", "timezone", "payload_sha256", "payload_path"):
        if not isinstance(observation[field], str) or not observation[field].strip():
            raise ContractError(f"raw observation {field} must be a non-empty string")
    if observation["timezone"] != "UTC" or not observation["payload_sha256"].startswith("sha256:"):
        raise ContractError("raw observation must be UTC and content-addressed")
    if not isinstance(observation["redacted"], bool):
        raise ContractError("raw observation redacted must be boolean")
    observed = _utc(observation["observed_at_utc"], "observed_at_utc")
    available = _utc(observation["available_at_utc"], "available_at_utc")
    retrieved = _utc(observation["retrieved_at_utc"], "retrieved_at_utc")
    if available < observed or retrieved < observed:
        raise ContractError("raw observation timestamps are inconsistent")
    return observation


PRICE_BAR_FIELDS = {"time_utc", "open", "high", "low", "close", "volume", "raw_observation_id", "available_at_utc"}


def validate_price_bar(bar: dict[str, Any], raw_observation: dict[str, Any]) -> dict[str, Any]:
    _exact_keys(bar, PRICE_BAR_FIELDS, "price bar")
    if bar["raw_observation_id"] != raw_observation["observation_id"]:
        raise ContractError("price bar must point to its raw observation")
    opened = _utc(bar["time_utc"], "price bar time_utc")
    available = _utc(bar["available_at_utc"], "price bar available_at_utc")
    raw_available = _utc(raw_observation["available_at_utc"], "raw observation available_at_utc")
    if available < opened or available < raw_available:
        raise ContractError("price bar availability predates its source observation")
    for field in ("open", "high", "low", "close"):
        if not isinstance(bar[field], (int, float)) or isinstance(bar[field], bool) or bar[field] <= 0:
            raise ContractError(f"price bar {field} must be a positive number")
    if bar["high"] < max(bar["open"], bar["close"]) or bar["low"] > min(bar["open"], bar["close"]):
        raise ContractError("price bar OHLC values are inconsistent")
    if not isinstance(bar["volume"], int) or isinstance(bar["volume"], bool) or bar["volume"] < 0:
        raise ContractError("price bar volume must be a non-negative integer")
    return bar


SNAPSHOT_FIELDS = {
    "contract_version", "snapshot_id", "instrument", "timeframe", "decision_cutoff_utc",
    "created_at_utc", "source_registry", "raw_observations", "price_bars", "artifact_sha256", "no_lookahead",
}


def build_dataset_snapshot(*, snapshot_id: str, instrument: str, timeframe: str, decision_cutoff_utc: str,
                           created_at_utc: str, source_registry: list[dict[str, Any]],
                           raw_observations: list[dict[str, Any]], price_bars: list[dict[str, Any]]) -> dict[str, Any]:
    provisional = {
        "contract_version": CONTRACT_VERSION, "snapshot_id": snapshot_id, "instrument": instrument,
        "timeframe": timeframe, "decision_cutoff_utc": decision_cutoff_utc, "created_at_utc": created_at_utc,
        "source_registry": source_registry, "raw_observations": raw_observations, "price_bars": price_bars,
        "no_lookahead": True,
    }
    return {**provisional, "artifact_sha256": sha256(provisional)}


def validate_dataset_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    _exact_keys(snapshot, SNAPSHOT_FIELDS, "dataset snapshot")
    if snapshot["contract_version"] != CONTRACT_VERSION or snapshot["instrument"] != "EUR/USD":
        raise ContractError("snapshot contract version or canonical instrument is invalid")
    if snapshot["timeframe"] not in {"H1", "M15", "D1"} or snapshot["no_lookahead"] is not True:
        raise ContractError("snapshot timeframe or no-lookahead declaration is invalid")
    if not isinstance(snapshot["snapshot_id"], str) or not snapshot["snapshot_id"].strip():
        raise ContractError("snapshot_id must be non-empty")
    cutoff, created = _utc(snapshot["decision_cutoff_utc"], "decision_cutoff_utc"), _utc(snapshot["created_at_utc"], "created_at_utc")
    if created < cutoff:
        raise ContractError("snapshot cannot be created before its decision cutoff")
    sources = snapshot["source_registry"]
    observations = snapshot["raw_observations"]
    bars = snapshot["price_bars"]
    if not isinstance(sources, list) or not isinstance(observations, list) or not isinstance(bars, list) or not bars:
        raise ContractError("snapshot must contain sources, observations, and at least one bar")
    source_by_id = {item["source_id"]: validate_source_registry_entry(item) for item in sources}
    if len(source_by_id) != len(sources):
        raise ContractError("source registry IDs must be unique")
    observations_by_id = {}
    for observation in observations:
        source = source_by_id.get(observation.get("source_id"))
        if source is None:
            raise ContractError("raw observation source is absent from registry")
        observations_by_id[observation["observation_id"]] = validate_raw_observation(observation, source)
    if len(observations_by_id) != len(observations):
        raise ContractError("raw observation IDs must be unique")
    previous: datetime | None = None
    for bar in bars:
        observation = observations_by_id.get(bar.get("raw_observation_id"))
        if observation is None:
            raise ContractError("price bar raw observation is absent from snapshot")
        validate_price_bar(bar, observation)
        opened = _utc(bar["time_utc"], "price bar time_utc")
        if previous is not None and opened <= previous:
            raise ContractError("snapshot price bars must be strictly chronological")
        if _utc(bar["available_at_utc"], "price bar available_at_utc") > cutoff:
            raise ContractError("snapshot includes data unavailable at its decision cutoff")
        previous = opened
    content = {key: value for key, value in snapshot.items() if key != "artifact_sha256"}
    if snapshot["artifact_sha256"] != sha256(content):
        raise ContractError("dataset snapshot artifact hash does not match canonical content")
    return snapshot


def bars_available_before(snapshot: dict[str, Any], cutoff_utc: str) -> list[dict[str, Any]]:
    """Return only bars valid at a declared UTC cutoff; reject a future request."""
    validate_dataset_snapshot(snapshot)
    cutoff = _utc(cutoff_utc, "cutoff_utc")
    snapshot_cutoff = _utc(snapshot["decision_cutoff_utc"], "decision_cutoff_utc")
    if cutoff > snapshot_cutoff:
        raise ContractError("requested cutoff exceeds the snapshot's declared point-in-time boundary")
    return [bar for bar in snapshot["price_bars"] if _utc(bar["available_at_utc"], "price bar available_at_utc") <= cutoff]
