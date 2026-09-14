"""Pure, local projection of a verified policy timing bundle into event quality.

This module neither captures source bytes nor changes primary-event source
qualification.  Its only output is a provenance-rich event record suitable for
the existing :func:`forex.event_quality.qualify_events` contract.
"""
from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from typing import Any

from forex.event_quality import EXACT, qualify_events
from forex.first_party_policy_capture import SOURCES
from forex.first_party_policy_timing import TIMING_URLS, timing_bundle_sha256


class PolicyEventAdapterError(ValueError):
    """The retained timing bundle or its receipt binding is unsafe."""


_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_BUNDLE_FIELDS = {
    "schema_version", "family_id", "target_date", "calendar_url",
    "calendar_sha256", "timing_url", "timing_sha256",
    "timing_source_limitation", "scheduled_at_local", "timezone",
    "scheduled_at_utc", "execution_authority", "coverage_status",
    "bundle_sha256",
}
_RECEIPT_FIELDS = {"source_url", "source_sha256", "capture_completed_at_utc"}
_NAMES = {
    "FOMC_POLICY_DECISION": "FOMC policy decision",
    "ECB_POLICY_DECISION": "ECB monetary policy decision",
}


def _sha(raw: bytes) -> str:
    if not isinstance(raw, bytes) or not raw:
        raise PolicyEventAdapterError("retained raw document is invalid")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _utc(value: Any, *, label: str) -> str:
    if not isinstance(value, str):
        raise PolicyEventAdapterError(f"{label} is invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PolicyEventAdapterError(f"{label} is invalid") from exc
    if parsed.tzinfo is None:
        raise PolicyEventAdapterError(f"{label} is invalid")
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _receipt(receipt: Any, *, expected_url: str, expected_sha: str, label: str) -> str:
    if not isinstance(receipt, dict) or set(receipt) != _RECEIPT_FIELDS:
        raise PolicyEventAdapterError(f"{label} receipt shape is invalid")
    if receipt.get("source_url") != expected_url or receipt.get("source_sha256") != expected_sha:
        raise PolicyEventAdapterError(f"{label} receipt does not bind retained raw document")
    return _utc(receipt["capture_completed_at_utc"], label=f"{label} receipt time")


def project_policy_timing_event(*, bundle: dict[str, Any], calendar_raw: bytes,
                                calendar_receipt: dict[str, Any], timing_raw: bytes,
                                timing_receipt: dict[str, Any], revision: int = 1) -> dict[str, Any]:
    """Project one verified local timing bundle into an exact event record.

    ``available_at_utc`` is the later of the two retained-document completion
    receipts, never the scheduled policy time or a caller-selected value.
    """
    if not isinstance(bundle, dict) or set(bundle) != _BUNDLE_FIELDS:
        raise PolicyEventAdapterError("timing bundle shape is invalid")
    if bundle.get("schema_version") != "forex.first-party-policy-timing-bundle.v1":
        raise PolicyEventAdapterError("timing bundle schema is invalid")
    if not isinstance(bundle.get("bundle_sha256"), str) or bundle["bundle_sha256"] != timing_bundle_sha256(bundle):
        raise PolicyEventAdapterError("timing bundle hash is invalid")
    family = bundle.get("family_id")
    if family not in SOURCES or family not in _NAMES:
        raise PolicyEventAdapterError("timing bundle family is invalid")
    source_id, calendar_url, timezone = SOURCES[family]
    if (bundle.get("calendar_url") != calendar_url or bundle.get("timing_url") != TIMING_URLS[family]
            or bundle.get("timezone") != timezone or bundle.get("execution_authority") is not False
            or bundle.get("coverage_status") != "UNKNOWN"):
        raise PolicyEventAdapterError("timing bundle source binding is invalid")
    if not isinstance(bundle.get("target_date"), str) or not re.fullmatch(r"20\d{2}-\d{2}-\d{2}", bundle["target_date"]):
        raise PolicyEventAdapterError("timing bundle target date is invalid")
    expected_local = bundle["target_date"] + ("T14:00" if family == "FOMC_POLICY_DECISION" else "T14:15")
    if bundle.get("scheduled_at_local") != expected_local or not isinstance(bundle.get("scheduled_at_utc"), str):
        raise PolicyEventAdapterError("timing bundle schedule is invalid")
    calendar_sha, timing_sha = _sha(calendar_raw), _sha(timing_raw)
    if bundle.get("calendar_sha256") != calendar_sha or bundle.get("timing_sha256") != timing_sha:
        raise PolicyEventAdapterError("timing bundle raw hashes are invalid")
    calendar_at = _receipt(calendar_receipt, expected_url=calendar_url, expected_sha=calendar_sha, label="calendar")
    timing_at = _receipt(timing_receipt, expected_url=TIMING_URLS[family], expected_sha=timing_sha, label="timing")
    if type(revision) is not int or revision < 1:
        raise PolicyEventAdapterError("event revision is invalid")
    available = max(calendar_at, timing_at)
    record = {
        "event_id": f"{family.lower()}:{bundle['target_date']}",
        "event_name": _NAMES[family], "source_id": source_id,
        "source_url": calendar_url,
        "license": "First-party public calendar/timing declaration; retained local provenance required.",
        "status": "SCHEDULED", "revision": revision,
        "available_at_utc": available, "time_precision": EXACT,
        "scheduled_at_local": expected_local, "timezone": timezone,
        "document_provenance": {
            "calendar": {"source_url": calendar_url, "source_sha256": calendar_sha, "capture_completed_at_utc": calendar_at},
            "timing": {"source_url": TIMING_URLS[family], "source_sha256": timing_sha, "capture_completed_at_utc": timing_at},
            "timing_bundle_sha256": bundle["bundle_sha256"],
        },
    }
    # Bind the public projection to the exact conversion/acceptance semantics
    # used by event quality, rather than trusting the bundle's claimed UTC.
    qualified = qualify_events([record], available)
    if len(qualified["accepted"]) != 1 or qualified["accepted"][0]["scheduled_at_utc"] != bundle["scheduled_at_utc"]:
        raise PolicyEventAdapterError("timing bundle UTC schedule is not event-quality valid")
    return record
