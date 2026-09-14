"""Pure declarative validation for the two-stream Demo isolation plan.

This module deliberately knows no MT5 login, account number, terminal path,
configuration file, runtime state, or broker API.  Its input is an operator
supplied *opaque* plan identifier set, not an account-selection mechanism.
Passing validation documents that the two logical streams cannot share the
declared ownership targets; it does not deploy either stream or grant trading
authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Any, Mapping


REGISTRY_SCHEMA_VERSION = "forex.stream-isolation.v1"
DEMO_SERVER = "GOMarketsMU-Demo"
LIVE_SERVER = "GOMarketsMU-Live"
STREAM_IDS = frozenset({"M1", "H_SLOW"})
NAMESPACE_KEYS = (
    "state_namespace",
    "monitor_namespace",
    "lease_namespace",
    "reservation_namespace",
    "outcome_namespace",
)
_OPAQUE_ID = re.compile(r"^[a-z][a-z0-9_-]{2,127}$")


class StreamIsolationError(ValueError):
    """A declarative stream plan is unsafe, incomplete, or implies authority."""


@dataclass(frozen=True)
class StreamStatus:
    """A read-only summary of one validated stream."""

    stream_id: str
    isolation_status: str
    deployment_state: str
    execution_capability: str


@dataclass(frozen=True)
class IsolationPlan:
    """Validated snapshot of the registry, with no operational capability."""

    registry_fingerprint: str
    status: str
    streams: tuple[StreamStatus, ...]

    def as_dict(self) -> dict[str, Any]:
        """Return a serialisable status projection, without opaque targets."""
        return {
            "registry_fingerprint": self.registry_fingerprint,
            "status": self.status,
            "streams": [
                {
                    "stream_id": stream.stream_id,
                    "isolation_status": stream.isolation_status,
                    "deployment_state": stream.deployment_state,
                    "execution_capability": stream.execution_capability,
                }
                for stream in self.streams
            ],
        }


def _snapshot(registry: Mapping[str, Any]) -> dict[str, Any]:
    """Make a JSON-only copy so caller mutation cannot alter a returned plan."""
    if not isinstance(registry, Mapping):
        raise StreamIsolationError("registry must be a mapping")
    try:
        encoded = json.dumps(registry, sort_keys=True, separators=(",", ":"), allow_nan=False)
        copied = json.loads(encoded)
    except (TypeError, ValueError) as exc:
        raise StreamIsolationError("registry must contain only JSON-safe values") from exc
    if not isinstance(copied, dict):  # Defensive: json loads a Mapping as an object.
        raise StreamIsolationError("registry must be an object")
    return copied


def _require_exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        details = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if unknown:
            details.append("unsupported " + ", ".join(unknown))
        raise StreamIsolationError(f"{label} fields are invalid: {'; '.join(details)}")


def _opaque(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _OPAQUE_ID.fullmatch(value):
        raise StreamIsolationError(f"{label} must be a lowercase opaque identifier")
    if value.isdecimal():
        raise StreamIsolationError(f"{label} must not be an account number")
    return value


def _stream_record(record: Any, index: int) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise StreamIsolationError(f"stream {index} must be an object")
    _require_exact_keys(
        record,
        {
            "stream_id",
            "server",
            "account_scope",
            "terminal_instance",
            "namespaces",
            "deployment_state",
            "account_selection",
            "execution_capability",
        },
        f"stream {index}",
    )
    return record


def _validate_namespaces(value: Any, stream_id: str) -> tuple[str, ...]:
    if not isinstance(value, dict):
        raise StreamIsolationError(f"{stream_id} namespaces must be an object")
    _require_exact_keys(value, set(NAMESPACE_KEYS), f"{stream_id} namespaces")
    return tuple(_opaque(value[key], f"{stream_id} {key}") for key in NAMESPACE_KEYS)


def _fingerprint(snapshot: dict[str, Any]) -> str:
    encoded = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return "sha256:" + sha256(encoded.encode("utf-8")).hexdigest()


def validate_stream_registry(registry: Mapping[str, Any]) -> IsolationPlan:
    """Validate the only supported M1 + disabled-H_SLOW ownership declaration.

    The registry schema is intentionally closed.  In particular, it has no
    account login, terminal path, order option, limit, lease acquisition or
    activation field.  Adding any such field is rejected rather than ignored.
    """
    snapshot = _snapshot(registry)
    _require_exact_keys(snapshot, {"schema_version", "streams"}, "registry")
    if snapshot["schema_version"] != REGISTRY_SCHEMA_VERSION:
        raise StreamIsolationError("unsupported registry schema version")
    records = snapshot["streams"]
    if not isinstance(records, list) or len(records) != len(STREAM_IDS):
        raise StreamIsolationError("registry must declare exactly M1 and H_SLOW")

    seen_ids: set[str] = set()
    account_scopes: set[str] = set()
    terminal_instances: set[str] = set()
    namespace_values: set[str] = set()
    summaries: dict[str, StreamStatus] = {}
    for index, raw_record in enumerate(records):
        record = _stream_record(raw_record, index)
        stream_id = record["stream_id"]
        if not isinstance(stream_id, str) or stream_id not in STREAM_IDS:
            raise StreamIsolationError(f"unsupported stream ID: {stream_id!r}")
        if stream_id in seen_ids:
            raise StreamIsolationError(f"duplicate stream ID: {stream_id}")
        seen_ids.add(stream_id)

        server = record["server"]
        if server == LIVE_SERVER:
            raise StreamIsolationError("GOMarketsMU-Live is forbidden")
        if server != DEMO_SERVER:
            raise StreamIsolationError(f"{stream_id} must use {DEMO_SERVER}")
        account_scope = _opaque(record["account_scope"], f"{stream_id} account_scope")
        terminal_instance = _opaque(record["terminal_instance"], f"{stream_id} terminal_instance")
        namespaces = _validate_namespaces(record["namespaces"], stream_id)
        if len(set(namespaces)) != len(namespaces):
            raise StreamIsolationError(f"duplicate namespace within {stream_id}")
        if account_scope in account_scopes:
            raise StreamIsolationError("duplicate account_scope across streams")
        if terminal_instance in terminal_instances:
            raise StreamIsolationError("duplicate terminal_instance across streams")
        duplicate_namespace = next((item for item in namespaces if item in namespace_values), None)
        if duplicate_namespace is not None:
            raise StreamIsolationError("duplicate namespace across streams")
        account_scopes.add(account_scope)
        terminal_instances.add(terminal_instance)
        namespace_values.update(namespaces)

        if record["account_selection"] != "NOT_SELECTED":
            raise StreamIsolationError(f"{stream_id} cannot select an account")
        if record["execution_capability"] != "NOT_EXPOSED":
            raise StreamIsolationError(f"{stream_id} cannot expose execution capability")

        if stream_id == "M1":
            if record["deployment_state"] != "RETAINED_EXISTING_OPERATION":
                raise StreamIsolationError("M1 deployment_state must retain the existing operation")
            summaries[stream_id] = StreamStatus(
                stream_id="M1",
                isolation_status="EXISTING_OWNER_UNCHANGED",
                deployment_state="RETAINED_EXISTING_OPERATION",
                execution_capability="NOT_EXPOSED",
            )
        else:
            if record["deployment_state"] not in {"NOT_DEPLOYED", "DISABLED"}:
                raise StreamIsolationError("H_SLOW must remain NOT_DEPLOYED or DISABLED")
            summaries[stream_id] = StreamStatus(
                stream_id="H_SLOW",
                isolation_status="ISOLATED_DISABLED",
                deployment_state="NOT_DEPLOYED",
                execution_capability="NOT_EXPOSED",
            )

    if seen_ids != STREAM_IDS:
        raise StreamIsolationError("registry must declare exactly M1 and H_SLOW")
    return IsolationPlan(
        registry_fingerprint=_fingerprint(snapshot),
        status="ISOLATED_DISABLED_PLAN",
        streams=(summaries["M1"], summaries["H_SLOW"]),
    )


def assert_registry_fingerprint(registry: Mapping[str, Any], expected: str) -> IsolationPlan:
    """Revalidate a current declaration and reject drift from a recorded hash."""
    plan = validate_stream_registry(registry)
    if not isinstance(expected, str) or plan.registry_fingerprint != expected:
        raise StreamIsolationError("registry fingerprint mismatch")
    return plan
