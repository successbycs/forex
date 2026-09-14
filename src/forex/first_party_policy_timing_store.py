"""Immutable local retention for verified FOMC/ECB timing projections.

This is deliberately a storage boundary, not a fetcher, scheduler, source
qualifier, or execution surface.  A retained target directory is either a
complete, hash-verified publication or is refused as partial/tampered state.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from forex.first_party_policy_event_adapter import PolicyEventAdapterError, project_policy_timing_event
from forex.first_party_policy_timing import PolicyTimingError, derive_exact_policy_time


SCHEMA = "forex.first-party-policy-timing-store.v1"
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_ARTIFACTS = ("calendar.html", "timing.html", "calendar.receipt.json", "timing.receipt.json",
              "timing.bundle.json", "event.record.json")
_MANIFEST_FIELDS = {"schema_version", "family_id", "target_date", "artifacts", "manifest_sha256"}


class PolicyTimingStoreError(RuntimeError):
    """The explicit local root is unsafe, incomplete, conflicting, or tampered."""


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise PolicyTimingStoreError("artifact is not finite JSON") from exc


def _sha(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PolicyTimingStoreError("duplicate JSON field")
        result[key] = value
    return result


def _invalid_constant(value: str) -> None:
    raise PolicyTimingStoreError("nonfinite JSON value")


def _read_json(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise PolicyTimingStoreError("artifact path is unsafe or missing")
    try:
        value = json.loads(path.read_bytes(), object_pairs_hook=_unique, parse_constant=_invalid_constant)
    except (OSError, json.JSONDecodeError) as exc:
        raise PolicyTimingStoreError("artifact JSON is invalid") from exc
    if not isinstance(value, dict):
        raise PolicyTimingStoreError("artifact JSON must be an object")
    return value


def _no_symlink(path: Path) -> None:
    if any(item.is_symlink() for item in (path, *path.parents)):
        raise PolicyTimingStoreError("symlink path component is not permitted")


def _root(root: Path) -> Path:
    if not isinstance(root, Path):
        raise PolicyTimingStoreError("root must be an explicit pathlib.Path")
    _no_symlink(root)
    if root.exists() and not root.is_dir():
        raise PolicyTimingStoreError("root is unsafe")
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if root.is_symlink() or not root.is_dir():
        raise PolicyTimingStoreError("root is unsafe")
    return root


@contextmanager
def _lock(root: Path) -> Iterator[None]:
    path = root / ".policy-timing-store.lock"
    if path.is_symlink():
        raise PolicyTimingStoreError("store lock is unsafe")
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "r+") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            yield
    finally:
        pass


def _publish(path: Path, payload: bytes) -> None:
    if path.exists() or path.is_symlink():
        raise PolicyTimingStoreError("immutable artifact already exists")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        raise
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def _receipt(*, source_url: str, raw: bytes, capture_completed_at_utc: str) -> dict[str, str]:
    return {"source_url": source_url, "source_sha256": _sha(raw),
            "capture_completed_at_utc": capture_completed_at_utc}


def _manifest_payload(*, family_id: str, target_date: str, payloads: dict[str, bytes]) -> dict[str, Any]:
    return {"schema_version": SCHEMA, "family_id": family_id, "target_date": target_date,
            "artifacts": {name: _sha(payload) for name, payload in sorted(payloads.items())}}


def _expected(*, family_id: str, target_date: str, calendar_raw: bytes, calendar_receipt: dict[str, Any],
              timing_raw: bytes, timing_receipt: dict[str, Any], revision: int) -> tuple[dict[str, bytes], dict[str, Any], dict[str, Any]]:
    try:
        bundle = derive_exact_policy_time(family_id=family_id, target_date=target_date,
                                          calendar_raw=calendar_raw, calendar_url=calendar_receipt.get("source_url"),
                                          timing_raw=timing_raw, timing_url=timing_receipt.get("source_url"))
        event = project_policy_timing_event(bundle=bundle, calendar_raw=calendar_raw,
                                            calendar_receipt=calendar_receipt, timing_raw=timing_raw,
                                            timing_receipt=timing_receipt, revision=revision)
    except (PolicyTimingError, PolicyEventAdapterError, AttributeError) as exc:
        raise PolicyTimingStoreError("timing publication input is invalid") from exc
    payloads = {"calendar.html": calendar_raw, "timing.html": timing_raw,
                "calendar.receipt.json": _canonical(calendar_receipt), "timing.receipt.json": _canonical(timing_receipt),
                "timing.bundle.json": _canonical(bundle), "event.record.json": _canonical(event)}
    return payloads, bundle, event


def _validate_existing(target: Path, *, family_id: str, target_date: str, expected_payloads: dict[str, bytes]) -> dict[str, Any]:
    if target.is_symlink() or not target.is_dir() or set(path.name for path in target.iterdir()) != set(_ARTIFACTS) | {"manifest.json"}:
        raise PolicyTimingStoreError("existing publication is partial or unsafe")
    manifest = _read_json(target / "manifest.json")
    if set(manifest) != _MANIFEST_FIELDS or manifest.get("schema_version") != SCHEMA:
        raise PolicyTimingStoreError("manifest shape is invalid")
    payload = {key: manifest[key] for key in _MANIFEST_FIELDS - {"manifest_sha256"}}
    if manifest.get("manifest_sha256") != _sha(_canonical(payload)):
        raise PolicyTimingStoreError("manifest hash mismatch")
    if manifest.get("family_id") != family_id or manifest.get("target_date") != target_date:
        raise PolicyTimingStoreError("existing publication identity conflicts")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict) or set(artifacts) != set(_ARTIFACTS):
        raise PolicyTimingStoreError("manifest artifact set is invalid")
    for name in _ARTIFACTS:
        path = target / name
        if path.is_symlink() or not path.is_file() or _sha(path.read_bytes()) != artifacts.get(name):
            raise PolicyTimingStoreError("immutable artifact hash mismatch")
        if path.read_bytes() != expected_payloads[name]:
            raise PolicyTimingStoreError("existing publication conflicts with supplied input")
    # Recalculate the derivation and projection from the retained bytes as an
    # independent semantic check, rather than trusting a rehashed JSON file.
    calendar_receipt = _read_json(target / "calendar.receipt.json")
    timing_receipt = _read_json(target / "timing.receipt.json")
    payloads, bundle, event = _expected(family_id=family_id, target_date=target_date,
                                        calendar_raw=(target / "calendar.html").read_bytes(), calendar_receipt=calendar_receipt,
                                        timing_raw=(target / "timing.html").read_bytes(), timing_receipt=timing_receipt,
                                        revision=_read_json(target / "event.record.json").get("revision"))
    if payloads != {name: (target / name).read_bytes() for name in _ARTIFACTS}:
        raise PolicyTimingStoreError("retained derivation does not bind raw documents")
    return {"status": "EXISTING", "capture_path": str(target), "manifest_sha256": manifest["manifest_sha256"],
            "event_record": event, "timing_bundle": bundle, "coverage_status": "UNKNOWN",
            "qualification_state": "PENDING_RETAINED_CAPTURE", "execution_authority": False}


def retain_policy_timing_bundle(root: Path, *, family_id: str, target_date: str, calendar_raw: bytes,
                                calendar_capture_completed_at_utc: str, timing_raw: bytes,
                                timing_capture_completed_at_utc: str, revision: int = 1) -> dict[str, Any]:
    """Publish one immutable local timing bundle, or return the exact existing one.

    The two receipt objects are closed here from supplied source bytes and
    declared completion clocks; their hashes are always recomputed before the
    timing projection is accepted.
    """
    from forex.first_party_policy_capture import SOURCES
    from forex.first_party_policy_timing import TIMING_URLS
    if family_id not in SOURCES or family_id not in TIMING_URLS:
        raise PolicyTimingStoreError("policy family is invalid")
    calendar_receipt = _receipt(source_url=SOURCES[family_id][1], raw=calendar_raw,
                                capture_completed_at_utc=calendar_capture_completed_at_utc)
    timing_receipt = _receipt(source_url=TIMING_URLS[family_id], raw=timing_raw,
                              capture_completed_at_utc=timing_capture_completed_at_utc)
    payloads, bundle, event = _expected(family_id=family_id, target_date=target_date, calendar_raw=calendar_raw,
                                        calendar_receipt=calendar_receipt, timing_raw=timing_raw,
                                        timing_receipt=timing_receipt, revision=revision)
    root = _root(root)
    target = root / family_id / target_date
    _no_symlink(target)
    with _lock(root):
        if target.exists() or target.is_symlink():
            return _validate_existing(target, family_id=family_id, target_date=target_date, expected_payloads=payloads)
        target.parent.mkdir(mode=0o700, exist_ok=True)
        if target.parent.is_symlink() or not target.parent.is_dir():
            raise PolicyTimingStoreError("policy family directory is unsafe")
        target.mkdir(mode=0o700)
        try:
            for name in _ARTIFACTS:
                _publish(target / name, payloads[name])
            manifest_payload = _manifest_payload(family_id=family_id, target_date=target_date, payloads=payloads)
            manifest = {**manifest_payload, "manifest_sha256": _sha(_canonical(manifest_payload))}
            _publish(target / "manifest.json", _canonical(manifest))
        except Exception as exc:
            raise PolicyTimingStoreError("publication left partial immutable state; exact recovery is refused") from exc
    return {"status": "CREATED", "capture_path": str(target), "manifest_sha256": manifest["manifest_sha256"],
            "event_record": event, "timing_bundle": bundle, "coverage_status": "UNKNOWN",
            "qualification_state": "PENDING_RETAINED_CAPTURE", "execution_authority": False}
