"""Read-only verification of immutable first-party policy timing captures."""
from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from forex.first_party_policy_capture import SOURCES
from forex.first_party_policy_event_adapter import PolicyEventAdapterError, project_policy_timing_event
from forex.first_party_policy_timing import PolicyTimingError, derive_exact_policy_time
from forex.first_party_policy_timing_store import (
    SCHEMA as STORE_SCHEMA, _ARTIFACTS, _MANIFEST_FIELDS, _canonical, _read_json, _sha,
)


SCHEMA = "forex.first-party-policy-source-verifier.v1"
_DATE = re.compile(r"20\d{2}-\d{2}-\d{2}\Z")


class PolicySourceVerificationError(RuntimeError):
    """A trusted timing-store root cannot be verified without ambiguity."""


def _no_symlink(path: Path) -> None:
    if any(item.is_symlink() for item in (path, *path.parents)):
        raise PolicySourceVerificationError("symlink path component is not permitted")


def _read(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise PolicySourceVerificationError("retained artifact is unsafe or missing")
    try:
        return path.read_bytes()
    except OSError as exc:
        raise PolicySourceVerificationError("retained artifact cannot be read") from exc


def _json(path: Path) -> dict[str, Any]:
    try:
        return _read_json(path)
    except Exception as exc:
        raise PolicySourceVerificationError("retained JSON artifact is invalid") from exc


def _verify_bundle(target: Path, *, family_id: str, target_date: str) -> dict[str, Any]:
    names = {path.name for path in target.iterdir()}
    if names != set(_ARTIFACTS) | {"manifest.json"}:
        raise PolicySourceVerificationError("timing publication is partial or has unexpected artifacts")
    manifest = _json(target / "manifest.json")
    if set(manifest) != _MANIFEST_FIELDS or manifest.get("schema_version") != STORE_SCHEMA:
        raise PolicySourceVerificationError("timing manifest shape is invalid")
    manifest_payload = {key: manifest[key] for key in _MANIFEST_FIELDS - {"manifest_sha256"}}
    if manifest.get("manifest_sha256") != _sha(_canonical(manifest_payload)):
        raise PolicySourceVerificationError("timing manifest hash mismatch")
    if manifest.get("family_id") != family_id or manifest.get("target_date") != target_date:
        raise PolicySourceVerificationError("timing manifest identity conflicts with path")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict) or set(artifacts) != set(_ARTIFACTS):
        raise PolicySourceVerificationError("timing manifest artifact set is invalid")
    raw = {name: _read(target / name) for name in _ARTIFACTS}
    if any(artifacts[name] != _sha(raw[name]) for name in _ARTIFACTS):
        raise PolicySourceVerificationError("timing artifact hash mismatch")
    calendar_receipt = _json(target / "calendar.receipt.json")
    timing_receipt = _json(target / "timing.receipt.json")
    recorded_bundle = _json(target / "timing.bundle.json")
    recorded_event = _json(target / "event.record.json")
    try:
        derived_bundle = derive_exact_policy_time(
            family_id=family_id, target_date=target_date, calendar_raw=raw["calendar.html"],
            calendar_url=calendar_receipt.get("source_url"), timing_raw=raw["timing.html"],
            timing_url=timing_receipt.get("source_url"),
        )
        if _canonical(recorded_bundle) != _canonical(derived_bundle):
            raise PolicySourceVerificationError("recorded timing bundle does not bind retained documents")
        event = project_policy_timing_event(
            bundle=derived_bundle, calendar_raw=raw["calendar.html"], calendar_receipt=calendar_receipt,
            timing_raw=raw["timing.html"], timing_receipt=timing_receipt,
            revision=recorded_event.get("revision"),
        )
    except (PolicyTimingError, PolicyEventAdapterError, AttributeError) as exc:
        raise PolicySourceVerificationError("retained timing derivation is invalid") from exc
    if _canonical(recorded_event) != _canonical(event):
        raise PolicySourceVerificationError("recorded event does not bind retained timing derivation")
    source_id, source_url, _ = SOURCES[family_id]
    # This has the exact input shape expected by primary_event_context.  Its
    # URL/digest/capture time must all describe the named calendar source; the
    # complete manifest and timing document remain bound in ``bundles``.
    context_observation = {
        "source_id": source_id, "source_url": source_url, "capture_state": "RETAINED",
        "coverage_status": "UNKNOWN", "captured_at_utc": calendar_receipt["capture_completed_at_utc"],
        "source_sha256": calendar_receipt["source_sha256"],
    }
    return {"family_id": family_id, "target_date": target_date,
            "manifest_sha256": manifest["manifest_sha256"], "event_record": event,
            "context_observation": context_observation}


def verify_policy_timing_store(root: Path) -> dict[str, Any]:
    """Discover and fully verify every bundle under an explicit local root.

    The result intentionally never declares complete coverage. Multiple
    retained bundles for one family remain separate context observations so a
    later context layer must make coverage/selection explicit rather than have
    this verifier silently choose one.
    """
    if not isinstance(root, Path) or not root.exists() or not root.is_dir() or root.is_symlink():
        raise PolicySourceVerificationError("root must be an existing non-symlink directory")
    _no_symlink(root)
    allowed_root = set(SOURCES) | {".policy-timing-store.lock"}
    entries = list(root.iterdir())
    if any(entry.name not in allowed_root for entry in entries):
        raise PolicySourceVerificationError("timing-store root has unexpected path")
    lock = root / ".policy-timing-store.lock"
    if lock.exists() and (lock.is_symlink() or not lock.is_file()):
        raise PolicySourceVerificationError("timing-store lock is unsafe")
    bundles: list[dict[str, Any]] = []
    for family_id in sorted(SOURCES):
        directory = root / family_id
        if not directory.exists():
            continue
        if directory.is_symlink() or not directory.is_dir():
            raise PolicySourceVerificationError("policy family directory is unsafe")
        dates = list(directory.iterdir())
        if any(not _DATE.fullmatch(item.name) or item.is_symlink() or not item.is_dir() for item in dates):
            raise PolicySourceVerificationError("policy target-date path is unsafe or invalid")
        for target in sorted(dates, key=lambda item: item.name):
            bundles.append(_verify_bundle(target, family_id=family_id, target_date=target.name))
    observations = [item["context_observation"] for item in bundles]
    return {"schema_version": SCHEMA, "execution_authority": False,
            "coverage_status": "UNKNOWN", "qualification_state": "PENDING_RETAINED_CAPTURE",
            "bundles": bundles, "context_observations": observations}
