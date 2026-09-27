"""Pure deterministic T480 trading-health classification (M33.2 policy).

No function here touches the OS, MT5, PostgreSQL or the clock.  The guardian
gathers an ``Observation`` and applies at most one fixed effect itself; this
module only says what the observation means.  ``recommended_action`` is advice
for a later recovery wave and never authorises an order, a close or a setting
change.  Missing or contradictory evidence always fails closed: it may fence
entries, but it never grants them.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

MODES = ("STOPPED", "MONITOR_ONLY", "RUN_DEMO")

STOPPED_BY_OPERATOR = "STOPPED_BY_OPERATOR"
MONITOR_ONLY = "MONITOR_ONLY"
STARTING = "STARTING"
RECOVERING_LISTENER = "RECOVERING_LISTENER"
RECOVERING_MT5 = "RECOVERING_MT5"
RECOVERY_WAIT_INFLIGHT = "RECOVERY_WAIT_INFLIGHT"
RECONCILING = "RECONCILING"
READY_FOR_ASSESSMENT = "READY_FOR_ASSESSMENT"
HEALTHY_NO_SETUP = "HEALTHY_NO_SETUP"
BLOCKED_POLICY = "BLOCKED_POLICY"
WAITING_MARKET = "WAITING_MARKET"
BLOCKED_DEPENDENCY = "BLOCKED_DEPENDENCY"
BLOCKED_SESSION = "BLOCKED_SESSION"
BLOCKED_OWNERSHIP = "BLOCKED_OWNERSHIP"
EXPOSURE_RECOVERY_REQUIRED = "EXPOSURE_RECOVERY_REQUIRED"
CIRCUIT_OPEN = "CIRCUIT_OPEN"

ENTRY_STATES = frozenset({READY_FOR_ASSESSMENT, HEALTHY_NO_SETUP})


@dataclass(frozen=True)
class Policy:
    startup_grace_s: float = 180.0
    cycle_stale_s: float = 150.0
    listener_heartbeat_warn_s: float = 30.0
    assessment_stall_s: float = 120.0
    permit_lifetime_s: float = 120.0
    attempts_per_window: int = 3
    attempt_window_s: float = 900.0
    attempt_spacing_s: tuple[float, ...] = (60.0, 120.0)


@dataclass(frozen=True)
class Observation:
    """Facts for one cycle.  ``None`` means "could not be determined"."""

    boot_seconds: float | None = None
    clock_trusted: bool = True
    last_cycle_age_s: float | None = None
    session_ok: bool | None = None
    managed_mt5_count: int | None = None
    unattributable_mt5_count: int = 0
    mt5_identity_ok: bool | None = None
    mt5_responding: bool | None = None
    permissions_ok: bool | None = None
    broker_connected: bool | None = None
    data_fresh: bool | None = None
    db_available: bool | None = None
    listener_present: bool | None = None
    listener_heartbeat_age_s: float | None = None
    assessment_age_s: float | None = None
    source_input_advancing: bool | None = None
    monitoring_fresh: bool | None = None
    exposure_flat: bool | None = None
    inflight_unresolved: bool | None = None
    risk_or_maintenance_hold: bool | None = None
    lease_valid: bool | None = None
    market_open: bool | None = None
    last_assessment_no_setup: bool = False


@dataclass(frozen=True)
class HealthDecision:
    state: str
    reasons: tuple[str, ...]
    execution_capable: bool
    entry_eligible: bool
    recommended_action: str = "NONE"


@dataclass(frozen=True)
class RecoveryRequest:
    """A persisted intent for one later fixed recovery effect, never authority itself."""

    generation: int
    state: str
    action: str
    observed_at_utc: str


RECOVERY_ACTIONS = frozenset({"START_LISTENER", "RESTART_LISTENER", "START_ONE_MT5",
                              "RESTART_ONE_MT5_IF_SAFE", "RECYCLE_MANAGED_SET_FLAT"})


def _d(state: str, *reasons: str, action: str = "NONE", capable: bool = False,
       eligible: bool = False) -> HealthDecision:
    return HealthDecision(state, tuple(reasons), capable, eligible and state in ENTRY_STATES, action)


def classify(obs: Observation, mode: str | None, budget_open: bool = False,
             policy: Policy = Policy()) -> HealthDecision:
    if mode not in MODES:
        return _d(BLOCKED_POLICY, "INTENT_MISSING_OR_INVALID")
    if not obs.clock_trusted:
        return _d(BLOCKED_DEPENDENCY, "CLOCK_UNTRUSTED")
    if mode == "STOPPED":
        return _d(STOPPED_BY_OPERATOR, "OPERATOR_INTENT")
    if budget_open:
        return _d(CIRCUIT_OPEN, "RECOVERY_BUDGET_EXHAUSTED")

    # A missing or stale listener must remain distinguishable even when its
    # normal runtime binding is no longer available.  The later recovery
    # executor still has to prove ownership, flatness and reconciliation
    # before it can act; this policy result never grants entry authority.
    # Check this before dependent MT5/session/data observations so an outage
    # is not misreported as a generic dependency failure.
    starting = obs.boot_seconds is not None and obs.boot_seconds < policy.startup_grace_s
    if not obs.listener_present:
        if starting:
            return _d(STARTING, "LISTENER_ABSENT_IN_GRACE")
        return _d(RECOVERING_LISTENER, "LISTENER_ABSENT", action="START_LISTENER")
    if (obs.listener_heartbeat_age_s is None
            or obs.listener_heartbeat_age_s >= policy.listener_heartbeat_warn_s):
        return _d(RECOVERING_LISTENER, "LISTENER_HEARTBEAT_STALE", action="RESTART_LISTENER")

    count = obs.managed_mt5_count
    if count is None:
        return _d(BLOCKED_DEPENDENCY, "MT5_INVENTORY_UNAVAILABLE")
    if obs.unattributable_mt5_count:
        return _d(BLOCKED_OWNERSHIP, "UNATTRIBUTABLE_MT5_PROCESS")
    if count == 0:
        # A missing Session-0 terminal necessarily makes ``session_ok`` false.
        # Classify that exact absence before the generic session fence so the
        # guarded START branch can refuse or recover with an explicit reason.
        if starting:
            return _d(STARTING, "MT5_ABSENT_IN_GRACE")
        reasons = ("MT5_ABSENT",) + (() if obs.exposure_flat is True else ("EXPOSURE_UNKNOWN",))
        return _d(RECOVERING_MT5, *reasons, action="START_ONE_MT5")
    if count > 1:
        if obs.exposure_flat is True and obs.inflight_unresolved is False:
            return _d(RECOVERING_MT5, "MT5_DUPLICATE", action="RECYCLE_MANAGED_SET_FLAT")
        return _d(EXPOSURE_RECOVERY_REQUIRED, "MT5_DUPLICATE", "EXPOSURE_OR_INFLIGHT_NOT_CLEAR",
                  action="PRESERVE_MONITOR_FENCE_ENTRIES")
    if obs.session_ok is not True:
        return _d(BLOCKED_SESSION, "SESSION_UNVERIFIED" if obs.session_ok is None else "SESSION_ABSENT")

    if obs.mt5_identity_ok is not True or obs.permissions_ok is False:
        return _d(BLOCKED_POLICY, "MT5_IDENTITY_OR_PERMISSION_MISMATCH")
    if obs.mt5_responding is False:
        return _d(RECOVERING_MT5, "MT5_UNRESPONSIVE", action="RESTART_ONE_MT5_IF_SAFE")
    if obs.broker_connected is not True or obs.data_fresh is False:
        return _d(BLOCKED_DEPENDENCY, "BROKER_OR_MARKET_DATA_UNAVAILABLE", action="BOUNDED_REPROBE")
    if obs.db_available is False:
        return _d(BLOCKED_DEPENDENCY, "AUDIT_DATABASE_UNAVAILABLE", action="BOUNDED_REPROBE")

    if (obs.source_input_advancing is True and obs.assessment_age_s is not None
            and obs.assessment_age_s >= policy.assessment_stall_s):
        return _d(RECOVERING_LISTENER, "ASSESSMENT_STALLED", action="RESTART_LISTENER", capable=True)

    if mode == "MONITOR_ONLY":
        return _d(MONITOR_ONLY, "OPERATOR_INTENT", capable=True)
    if obs.inflight_unresolved is not False:
        return _d(RECOVERY_WAIT_INFLIGHT, "INFLIGHT_UNRESOLVED_OR_UNKNOWN", capable=True)
    if obs.monitoring_fresh is not True:
        return _d(RECONCILING, "MONITORING_NOT_FRESH", capable=True)
    if obs.risk_or_maintenance_hold is not False or obs.lease_valid is not True:
        return _d(BLOCKED_POLICY, "RISK_MAINTENANCE_OR_LEASE_HOLD", capable=True)
    if obs.market_open is None:
        return _d(BLOCKED_DEPENDENCY, "DATA_UNAVAILABLE_MARKET_SESSION", capable=True)
    if obs.market_open is False:
        return _d(WAITING_MARKET, "MARKET_CLOSED", capable=True)
    if obs.last_assessment_no_setup:
        return _d(HEALTHY_NO_SETUP, "NO_VALID_SETUP", capable=True, eligible=True)
    return _d(READY_FOR_ASSESSMENT, "ALL_DIMENSIONS_OK", capable=True, eligible=True)


def recovery_budget(attempt_times: list[datetime], now: datetime, clock_trusted: bool,
                    policy: Policy = Policy()) -> tuple[bool, float]:
    """Return ``(circuit_open, seconds_until_next_attempt_allowed)``.

    ``attempt_times`` are persisted before each destructive action.  An
    untrustworthy clock keeps the breaker open; a reboot does not reset it.
    """
    if not clock_trusted:
        return True, 0.0
    window = [t for t in attempt_times if timedelta(0) <= now - t < timedelta(seconds=policy.attempt_window_s)]
    if any(t > now for t in attempt_times) or len(window) >= policy.attempts_per_window:
        return True, 0.0
    if not window:
        return False, 0.0
    spacing = policy.attempt_spacing_s[min(len(window), len(policy.attempt_spacing_s)) - 1]
    wait = spacing - (now - max(window)).total_seconds()
    return False, max(0.0, wait)


def recovery_request(decision: HealthDecision, generation: int, observed_at: datetime) -> RecoveryRequest | None:
    """Create a fail-closed, generation-bound request for the fixed executor.

    The executor must independently re-observe its preconditions; this helper
    deliberately cannot turn a healthy, policy-blocked, or entry-capable state
    into a recovery action.
    """
    if (type(generation) is not int or generation < 1 or decision.entry_eligible
            or decision.recommended_action not in RECOVERY_ACTIONS
            or decision.state not in {RECOVERING_LISTENER, RECOVERING_MT5}):
        return None
    return RecoveryRequest(generation, decision.state, decision.recommended_action,
                           observed_at.astimezone(UTC).isoformat().replace("+00:00", "Z"))


def validate_recovery_request(request: dict[str, Any] | None, expected: RecoveryRequest) -> bool:
    """Accept only the exact current, fail-closed persisted recovery request."""
    return isinstance(request, dict) and request == {
        "schema_version": "forex.trading-health-recovery-request.v1", "state": "PENDING",
        "generation": expected.generation, "observed_at_utc": expected.observed_at_utc,
        "health_state": expected.state, "action": expected.action, "entry_eligible": False,
    }


@dataclass(frozen=True)
class PermitDecision:
    valid: bool
    reason: str


def validate_entry_permit(permit: dict[str, Any] | None, boot_id: str, generation: int,
                          mode: str | None, now: datetime,
                          policy: Policy = Policy()) -> PermitDecision:
    """A permit only allows the existing runner to continue its own checks."""
    if mode != "RUN_DEMO":
        return PermitDecision(False, "INTENT_NOT_RUN_DEMO")
    if not isinstance(permit, dict):
        return PermitDecision(False, "PERMIT_MISSING")
    try:
        issued = datetime.fromisoformat(str(permit["issued_at_utc"]).replace("Z", "+00:00"))
        expires = datetime.fromisoformat(str(permit["expires_at_utc"]).replace("Z", "+00:00"))
        p_boot, p_gen = permit["boot_id"], permit["generation"]
    except (KeyError, ValueError, TypeError):
        return PermitDecision(False, "PERMIT_CORRUPT")
    if issued.tzinfo is None or expires.tzinfo is None or isinstance(p_gen, bool) or not isinstance(p_gen, int):
        return PermitDecision(False, "PERMIT_CORRUPT")
    issued, expires = issued.astimezone(UTC), expires.astimezone(UTC)
    if p_boot != boot_id:
        return PermitDecision(False, "PERMIT_WRONG_BOOT")
    if p_gen != generation:
        return PermitDecision(False, "PERMIT_GENERATION_MISMATCH")
    if issued > now:
        return PermitDecision(False, "PERMIT_FROM_FUTURE")
    if (expires - issued).total_seconds() > policy.permit_lifetime_s or expires <= issued:
        return PermitDecision(False, "PERMIT_LIFETIME_INVALID")
    if now >= expires:
        return PermitDecision(False, "PERMIT_EXPIRED")
    return PermitDecision(True, "PERMIT_CURRENT")
