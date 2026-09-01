"""Lean M12 normalisation and quarantine rules for historical observations."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


REQUIRED = {"observation_id", "source_id", "observed_at_utc", "available_at_utc", "payload_sha256"}


def normalise(records: list[dict[str, Any]], cutoff_utc: str) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    cutoff = datetime.fromisoformat(cutoff_utc.replace("Z", "+00:00"))
    accepted: list[dict[str, Any]] = []
    quarantined: list[dict[str, str]] = []
    seen: set[str] = set()
    for record in records:
        missing = REQUIRED - record.keys()
        identity = str(record.get("observation_id", "unknown"))
        if missing:
            quarantined.append({"observation_id": identity, "reason": "MISSING_REQUIRED_FIELD"})
            continue
        if identity in seen:
            quarantined.append({"observation_id": identity, "reason": "DUPLICATE"})
            continue
        seen.add(identity)
        try:
            observed = datetime.fromisoformat(str(record["observed_at_utc"]).replace("Z", "+00:00"))
            available = datetime.fromisoformat(str(record["available_at_utc"]).replace("Z", "+00:00"))
        except ValueError:
            quarantined.append({"observation_id": identity, "reason": "MALFORMED_TIMESTAMP"})
            continue
        if available < observed:
            quarantined.append({"observation_id": identity, "reason": "INVALID_AVAILABILITY"})
        elif available > cutoff:
            quarantined.append({"observation_id": identity, "reason": "LATE_OR_LOOKAHEAD"})
        elif not str(record["payload_sha256"]).startswith("sha256:"):
            quarantined.append({"observation_id": identity, "reason": "UNVERIFIABLE_HASH"})
        else:
            accepted.append({**record, "observed_at_utc": observed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"), "available_at_utc": available.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")})
    return accepted, quarantined
