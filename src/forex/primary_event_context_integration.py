"""Read-only policy timing-store detail for primary-event context reporting."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from forex.first_party_policy_source_verifier import (
    PolicySourceVerificationError,
    verify_policy_timing_store,
)
from forex.primary_event_context import PrimaryEventContextError, qualify_context


SCHEMA = "forex.primary-event-context-policy-timing-integration.v1"


class PrimaryEventContextIntegrationError(RuntimeError):
    """The verifier, supplied contract, or integration boundary is unsafe."""


def report_policy_timing_context(*, store_root: Path, contract: dict[str, Any]) -> dict[str, Any]:
    """Report verified policy timing observations through primary context.

    This function does not modify the store or contract.  It deliberately
    passes one observation per retained bundle into ``qualify_context`` so
    repeated captures remain an explicit per-source ambiguity there.
    """
    try:
        verified = verify_policy_timing_store(store_root)
        context = qualify_context(contract=contract, observations=verified["context_observations"])
    except (PolicySourceVerificationError, PrimaryEventContextError) as exc:
        raise PrimaryEventContextIntegrationError("policy timing context integration refused") from exc
    return {
        "schema_version": SCHEMA,
        "execution_authority": False,
        "coverage_status": "UNKNOWN",
        "qualification_state": "RETAINED_TIMING_ACTIVE_COVERAGE_UNKNOWN",
        "primary_context": context,
        # Keep the complete raw/bundle/event provenance available to the
        # report consumer without pretending primary context selected a row.
        "verified_policy_timing_bundles": verified["bundles"],
        "verified_policy_timing_observations": verified["context_observations"],
    }
