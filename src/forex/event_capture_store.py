"""Durable local-only storage for retained BLS HTML captures.

Raw captures and their metadata are published once with exclusive creation.
Journal snapshots are immutable generations rebuilt from verified metadata while
holding an advisory cross-process lock.  There is no network, broker, or
default storage location in this module.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import tempfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from forex.bls_events import FAMILIES, parse_bls_schedule_html
from forex.event_revisions import EventRevisionError, append_parsed_capture, empty_journal, validate_journal


STORE_VERSION = "forex.local-event-capture-store.v1"
ISOLATION_VERSION = "forex.local-event-capture-isolation.v1"
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z")
_METADATA_FIELDS = {"schema_version", "capture_id", "raw_capture_sha256", "capture_completed_at_utc", "source_family", "source_url", "parser_result", "metadata_sha256"}
_ISOLATION_FIELDS = {"schema_version", "capture_id", "metadata_sha256", "published_journal_sha256", "reason", "marker_sha256"}
_ISOLATION_REASON = "LATE_CAPTURE_NOT_APPLIED"


class EventCaptureStoreError(RuntimeError):
    """A local evidence-store safety or integrity condition failed."""


class CaptureConflictError(EventCaptureStoreError):
    """An immutable capture identifier has already been published."""


class CaptureRecoveryRequired(EventCaptureStoreError):
    """Raw evidence exists without enough immutable metadata to recover it."""


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise EventCaptureStoreError("capture metadata must be finite JSON") from exc


def _sha(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _safe_id(capture_id: str) -> None:
    if not isinstance(capture_id, str) or not _ID.fullmatch(capture_id):
        raise EventCaptureStoreError("capture_id must be an alphanumeric, hyphen, or underscore identifier")


def _directory(path: Path) -> None:
    _no_symlink_ancestors(path)
    if path.exists() and path.is_symlink():
        raise EventCaptureStoreError(f"symlink path is not permitted: {path}")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not path.is_dir() or path.is_symlink():
        raise EventCaptureStoreError(f"store directory is unsafe: {path}")


def _no_symlink_ancestors(path: Path) -> None:
    if any(item.is_symlink() for item in (path, *path.parents)):
        raise EventCaptureStoreError("symlink path component is not permitted")


def _layout(root: Path) -> dict[str, Path]:
    if not isinstance(root, Path):
        raise EventCaptureStoreError("root must be an explicit pathlib.Path")
    _directory(root)
    layout = {"raw": root / "raw", "metadata": root / "metadata", "journals": root / "journals"}
    for directory in layout.values():
        _directory(directory)
    isolation_directory = root / "isolations"
    if isolation_directory.exists() or isolation_directory.is_symlink():
        if isolation_directory.is_symlink() or not isolation_directory.is_dir():
            raise EventCaptureStoreError(f"store directory is unsafe: {isolation_directory}")
        layout["isolations"] = isolation_directory
    return layout


def _existing_layout(root: Path) -> dict[str, Path]:
    """Validate an existing store layout without creating or changing it."""
    if not isinstance(root, Path) or not root.exists() or root.is_symlink() or not root.is_dir():
        raise EventCaptureStoreError("root must name an existing non-symlink store directory")
    _no_symlink_ancestors(root)
    layout = {"raw": root / "raw", "metadata": root / "metadata", "journals": root / "journals"}
    for directory in layout.values():
        if not directory.exists() or directory.is_symlink() or not directory.is_dir():
            raise EventCaptureStoreError(f"store directory is unsafe or missing: {directory}")
    isolation_directory = root / "isolations"
    if isolation_directory.exists() or isolation_directory.is_symlink():
        if isolation_directory.is_symlink() or not isolation_directory.is_dir():
            raise EventCaptureStoreError(f"store directory is unsafe: {isolation_directory}")
        layout["isolations"] = isolation_directory
    return layout


@contextmanager
def _lock(root: Path) -> Iterator[None]:
    lock_path = root / ".event-capture-store.lock"
    if lock_path.exists() and lock_path.is_symlink():
        raise EventCaptureStoreError("store lock path is a symlink")
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "r+") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            yield
    finally:
        # fdopen owns the descriptor; this branch only matters before fdopen.
        pass


@contextmanager
def _read_lock(root: Path) -> Iterator[None]:
    """Take a shared lock only when a writer-created lock file exists."""
    lock_path = root / ".event-capture-store.lock"
    if not lock_path.exists():
        yield
        return
    if lock_path.is_symlink():
        raise EventCaptureStoreError("store lock path is a symlink")
    fd = os.open(lock_path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        fcntl.flock(fd, fcntl.LOCK_SH)
        yield
    finally:
        os.close(fd)


def _publish_exclusive(path: Path, payload: bytes) -> None:
    """Publish only fully flushed bytes, without replacing an existing name.

    A failed staging write is retained under a hidden staging name, never
    mistaken for a complete capture. Hard-link publication is atomic and
    exclusive on the supported local POSIX filesystem.
    """
    if path.exists() or path.is_symlink():
        raise CaptureConflictError(f"immutable path already exists: {path.name}")
    fd, staging_name = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    staging = Path(staging_name)
    with os.fdopen(fd, "wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.link(staging, path, follow_symlinks=False)
    except FileExistsError as exc:
        raise CaptureConflictError(f"immutable path already exists: {path.name}") from exc
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
        # The final, fsynced file now owns the bytes. Remove only its duplicate
        # staging link; never delete or replace a published artifact.
        staging.unlink()
        os.fsync(directory)
    finally:
        os.close(directory)


def _read_json(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise EventCaptureStoreError(f"unsafe metadata path: {path.name}")
    try:
        value = json.loads(path.read_bytes(), object_pairs_hook=_unique_fields,
                           parse_constant=_invalid_constant)
    except (OSError, json.JSONDecodeError) as exc:
        raise EventCaptureStoreError(f"cannot read metadata {path.name}") from exc
    if not isinstance(value, dict):
        raise EventCaptureStoreError("capture metadata must be an object")
    return value


def _unique_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise EventCaptureStoreError("duplicate metadata JSON field")
        result[key] = value
    return result


def _invalid_constant(value):
    raise EventCaptureStoreError("nonfinite metadata JSON constant")


def _metadata_payload(metadata: dict[str, Any]) -> dict[str, Any]:
    return {key: metadata[key] for key in _METADATA_FIELDS - {"metadata_sha256"}}


def _validated_metadata(path: Path, raw_directory: Path) -> dict[str, Any]:
    metadata = _read_json(path)
    if set(metadata) != _METADATA_FIELDS or metadata.get("schema_version") != STORE_VERSION:
        raise EventCaptureStoreError("capture metadata schema is invalid")
    if metadata.get("metadata_sha256") != _sha(_canonical(_metadata_payload(metadata))):
        raise EventCaptureStoreError("capture metadata hash mismatch")
    _safe_id(metadata.get("capture_id"))
    if path.stem != metadata["capture_id"]:
        raise EventCaptureStoreError("metadata filename does not bind capture ID")
    raw_path = raw_directory / f"{metadata['capture_id']}.html"
    if raw_path.is_symlink() or not raw_path.is_file():
        raise CaptureRecoveryRequired(f"missing immutable raw capture for {metadata['capture_id']}")
    raw = raw_path.read_bytes()
    if _sha(raw) != metadata.get("raw_capture_sha256"):
        raise EventCaptureStoreError("raw capture hash mismatch")
    parser = metadata.get("parser_result")
    expected_parser = _parse_capture(raw, metadata["source_family"],
        metadata["capture_completed_at_utc"], metadata["source_url"])
    if parser != expected_parser:
        raise EventCaptureStoreError("parser result does not bind raw capture")
    if parser.get("capture_completed_at_utc") != metadata["capture_completed_at_utc"]:
        raise EventCaptureStoreError("parser result does not bind declared capture completion")
    return metadata


def _published_journal_generations(layout: dict[str, Path]) -> list[dict[str, Any]]:
    """Read every intact immutable generation, rejecting unsafe siblings."""
    generations: list[dict[str, Any]] = []
    for path in layout["journals"].glob("*.json"):
        if path.is_symlink() or not path.is_file():
            raise EventCaptureStoreError("unsafe journal generation path")
        try:
            generation = validate_journal(_read_json(path))
            if path.stem != generation["journal_sha256"].removeprefix("sha256:"):
                raise EventCaptureStoreError("journal filename does not bind content")
            generations.append(generation)
        except (OSError, json.JSONDecodeError, EventRevisionError) as exc:
            raise EventCaptureStoreError(f"invalid journal generation: {path.name}") from exc
    return generations


def _latest_published_journal(layout: dict[str, Path]) -> dict[str, Any] | None:
    """Return the longest immutable generation, rejecting ambiguous siblings."""
    generations = _published_journal_generations(layout)
    if not generations:
        return None
    maximum = max(len(item["captures"]) for item in generations)
    candidates = [item for item in generations if len(item["captures"]) == maximum]
    if len({item["journal_sha256"] for item in candidates}) != 1:
        raise EventCaptureStoreError("conflicting equally-current journal generations")
    latest = candidates[0]
    for previous in generations:
        if (latest["captures"][:len(previous["captures"])] != previous["captures"]
                or latest["records"][:len(previous["records"])] != previous["records"]):
            raise EventCaptureStoreError("journal generations do not share an immutable prefix")
    return candidates[0]


def _isolation_payload(marker: dict[str, Any]) -> dict[str, Any]:
    return {key: marker[key] for key in _ISOLATION_FIELDS - {"marker_sha256"}}


def _validated_isolations(layout: dict[str, Path], captures: list[dict[str, Any]],
                          generations: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Validate all optional omission markers before excluding any capture."""
    # Discover the optional directory under the store lock, not from a layout
    # snapshot collected before waiting for another writer's first isolation.
    directory = layout["metadata"].parent / "isolations"
    if not directory.exists() and not directory.is_symlink():
        return {}
    _no_symlink_ancestors(directory)
    if directory.is_symlink() or not directory.is_dir():
        raise EventCaptureStoreError("capture isolation directory is unsafe")
    metadata_by_id = {item["capture_id"]: item for item in captures}
    published_by_hash = {item["journal_sha256"]: item for item in generations}
    published_ids = {capture["capture_id"] for generation in generations for capture in generation["captures"]}
    markers: dict[str, dict[str, Any]] = {}
    for path in directory.glob("*.json"):
        marker = _read_json(path)
        if set(marker) != _ISOLATION_FIELDS or marker.get("schema_version") != ISOLATION_VERSION:
            raise EventCaptureStoreError("capture isolation marker schema is invalid")
        capture_id = marker.get("capture_id")
        _safe_id(capture_id)
        if path.stem != capture_id:
            raise EventCaptureStoreError("isolation filename does not bind capture ID")
        if marker.get("reason") != _ISOLATION_REASON:
            raise EventCaptureStoreError("capture isolation reason is invalid")
        if marker.get("marker_sha256") != _sha(_canonical(_isolation_payload(marker))):
            raise EventCaptureStoreError("capture isolation marker hash mismatch")
        if capture_id in markers:
            raise EventCaptureStoreError("duplicate capture isolation marker")
        metadata = metadata_by_id.get(capture_id)
        if metadata is None or marker.get("metadata_sha256") != metadata.get("metadata_sha256"):
            raise EventCaptureStoreError("capture isolation marker does not bind retained metadata")
        generation = published_by_hash.get(marker.get("published_journal_sha256"))
        if generation is None:
            raise EventCaptureStoreError("capture isolation marker references missing or invalid journal generation")
        if capture_id in published_ids:
            raise EventCaptureStoreError("published capture cannot be isolated")
        if not generation["captures"] or _capture_order(metadata)[0] > _capture_order(generation["captures"][-1])[0]:
            raise EventCaptureStoreError("capture isolation marker does not prove a late capture")
        markers[capture_id] = marker
    return markers


def _verify_published_metadata(published: dict[str, Any], captures: list[dict[str, Any]]) -> None:
    """Ensure an immutable generation still binds the retained raw metadata."""
    by_id = {item["capture_id"]: item for item in captures}
    reconstructed = empty_journal()
    for item in published["captures"]:
        metadata = by_id.get(item["capture_id"])
        if metadata is None:
            raise CaptureRecoveryRequired("published journal capture metadata is missing")
        reconstructed = append_parsed_capture(reconstructed,
            capture_id=item["capture_id"], parsed_capture=metadata["parser_result"])
    if reconstructed != published:
        raise EventCaptureStoreError("published journal does not bind retained capture metadata")


def _journal_from_metadata(layout: dict[str, Path]) -> dict[str, Any]:
    """Recover only an unpublished suffix; never rewrite a published prefix."""
    metadata_paths = list(layout["metadata"].glob("*.json"))
    metadata_ids = {path.stem for path in metadata_paths}
    orphan_raw = {path.stem for path in layout["raw"].glob("*.html")} - metadata_ids
    if orphan_raw:
        raise CaptureRecoveryRequired("raw capture exists without metadata: " + ",".join(sorted(orphan_raw)))
    captures = [_validated_metadata(path, layout["raw"]) for path in metadata_paths]
    generations = _published_journal_generations(layout)
    published = _latest_published_journal(layout)
    isolated = _validated_isolations(layout, captures, generations)
    if published is None:
        journal = empty_journal()
        pending = sorted(captures, key=_capture_order)
    else:
        journal = published
        _verify_published_metadata(published, captures)
        known_ids = {item["capture_id"] for item in journal["captures"]}
        pending = [item for item in captures if item["capture_id"] not in known_ids and item["capture_id"] not in isolated]
        if journal["captures"]:
            last = _capture_order(journal["captures"][-1])[0]
            late = [item["capture_id"] for item in pending if _capture_order(item)[0] <= last]
            if late:
                raise CaptureRecoveryRequired("late capture cannot rewrite published journal prefix: " + ",".join(sorted(late)))
        pending.sort(key=_capture_order)
    for metadata in pending:
        try:
            journal = append_parsed_capture(journal, capture_id=metadata["capture_id"], parsed_capture=metadata["parser_result"])
        except EventRevisionError as exc:
            raise EventCaptureStoreError(f"cannot recover journal from {metadata['capture_id']}: {exc}") from exc
    return validate_journal(journal)


def _capture_order(item: dict[str, Any]) -> tuple[datetime, str]:
    return (datetime.fromisoformat(item["capture_completed_at_utc"].replace("Z", "+00:00")),
            item["capture_id"])


def _publish_journal(layout: dict[str, Path], journal: dict[str, Any]) -> None:
    digest = journal["journal_sha256"].removeprefix("sha256:")
    path = layout["journals"] / f"{digest}.json"
    payload = _canonical(journal)
    if path.exists():
        if path.is_symlink() or path.read_bytes() != payload:
            raise EventCaptureStoreError("existing journal generation is inconsistent")
        return
    _publish_exclusive(path, payload)


def read_capture_journal(root: Path) -> dict[str, Any]:
    """Reconstruct and verify the current journal without writing the store.

    This intentionally does not repair a missing generation snapshot.  A caller
    receives the deterministic journal derivable from the immutable raw/metadata
    evidence, or a recoverable integrity error if that evidence is incomplete.
    """
    layout = _existing_layout(root)
    with _read_lock(root):
        return json.loads(json.dumps(_journal_from_metadata(layout)))


def read_capture_journal_with_metadata_receipts(root: Path) -> dict[str, Any]:
    """Read one verified journal and its exact immutable metadata receipts.

    This is read-only.  It deliberately refuses a retained metadata capture
    that is not part of the journal, including an explicitly isolated late
    capture: a canonical full-store projection must not silently omit it.
    """
    layout = _existing_layout(root)
    with _read_lock(root):
        journal = _journal_from_metadata(layout)
        metadata = [_validated_metadata(path, layout["raw"]) for path in layout["metadata"].glob("*.json")]
        journal_ids = {capture["capture_id"] for capture in journal["captures"]}
        metadata_by_id = {item["capture_id"]: item for item in metadata}
        if set(metadata_by_id) != journal_ids:
            raise CaptureRecoveryRequired("retained metadata does not match journal captures")
        return {"journal": json.loads(json.dumps(journal)),
                "capture_receipt_sha256_by_id": {capture_id: metadata_by_id[capture_id]["metadata_sha256"]
                                                   for capture_id in sorted(journal_ids)}}


def read_capture_store(root: Path) -> dict[str, Any]:
    """Read the verified journal together with every explicit late omission."""
    layout = _existing_layout(root)
    with _read_lock(root):
        journal = _journal_from_metadata(layout)
        captures = [_validated_metadata(path, layout["raw"]) for path in layout["metadata"].glob("*.json")]
        markers = _validated_isolations(layout, captures, _published_journal_generations(layout))
        return {"journal": json.loads(json.dumps(journal)),
                "isolated_captures": [json.loads(json.dumps(markers[key])) for key in sorted(markers)]}


def isolate_late_capture(root: Path, *, capture_id: str) -> dict[str, Any]:
    """Append a hash-bound marker excluding one valid, unpublished late capture.

    The retained raw capture, metadata, and journal generations are never
    changed.  This makes a known omission visible, rather than silently
    repairing chronology or inventing an observation time.
    """
    _safe_id(capture_id)
    layout = _existing_layout(root)
    with _lock(root):
        metadata = _validated_metadata(layout["metadata"] / f"{capture_id}.json", layout["raw"])
        metadata_paths = list(layout["metadata"].glob("*.json"))
        orphan_raw = {path.stem for path in layout["raw"].glob("*.html")} - {path.stem for path in metadata_paths}
        if orphan_raw:
            raise CaptureRecoveryRequired("raw capture exists without metadata: " + ",".join(sorted(orphan_raw)))
        captures = [_validated_metadata(path, layout["raw"]) for path in metadata_paths]
        generations = _published_journal_generations(layout)
        published = _latest_published_journal(layout)
        if published is None:
            raise CaptureRecoveryRequired("cannot isolate without a published journal generation")
        _verify_published_metadata(published, captures)
        existing = _validated_isolations(layout, captures, generations)
        if capture_id in existing:
            return json.loads(json.dumps(existing[capture_id]))
        published_ids = {capture["capture_id"] for generation in generations for capture in generation["captures"]}
        if capture_id in published_ids:
            raise EventCaptureStoreError("published capture cannot be isolated")
        if not published["captures"] or _capture_order(metadata)[0] > _capture_order(published["captures"][-1])[0]:
            raise EventCaptureStoreError("capture is not late against the latest published journal")
        isolation_directory = root / "isolations"
        _directory(isolation_directory)
        # Flush the new directory's name in its parent before publishing a
        # marker within it; syncing only the child does not cover that entry.
        root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(root_fd)
        finally:
            os.close(root_fd)
        marker = {"schema_version": ISOLATION_VERSION, "capture_id": capture_id,
                  "metadata_sha256": metadata["metadata_sha256"],
                  "published_journal_sha256": published["journal_sha256"],
                  "reason": _ISOLATION_REASON}
        marker["marker_sha256"] = _sha(_canonical(marker))
        _publish_exclusive(isolation_directory / f"{capture_id}.json", _canonical(marker))
        return json.loads(json.dumps(marker))


def _parse_capture(raw: bytes, source_family: str, captured: str,
                   source_url: str | None = None) -> dict[str, Any]:
    if not isinstance(raw, bytes) or not raw:
        raise EventCaptureStoreError("raw must be non-empty bytes")
    try:
        html = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise EventCaptureStoreError("raw BLS capture must be UTF-8 HTML") from exc
    if source_family == "BLS_MONTHLY":
        from forex.bls_monthly_events import parse_bls_monthly_html
        return parse_bls_monthly_html(html, capture_completed_at_utc=captured,
                                      source_url=source_url)
    if source_family not in FAMILIES:
        raise EventCaptureStoreError("source_family is unsupported")
    expected_url = "https://www.bls.gov" + FAMILIES[source_family]["path"]
    if source_url is not None and source_url != expected_url:
        raise EventCaptureStoreError("capture source binding mismatch")
    return parse_bls_schedule_html(html, capture_completed_at_utc=captured,
                                   source_url=expected_url, source_family=source_family)


def retain_bls_capture(root: Path, *, capture_id: str, raw: bytes, source_family: str,
                       capture_completed_at_utc: str, source_url: str | None = None) -> dict[str, Any]:
    """Publish one immutable BLS capture and recover/publish its journal.

    ``capture_completed_at_utc`` is caller-declared provenance only.  The
    function does not attest that the caller observed the publisher at that
    time.  If metadata publication fails after raw publication, raw evidence is
    intentionally left in place and later calls raise a recoverable condition.
    """
    _safe_id(capture_id)
    # Parse before filesystem mutation; malformed retained HTML becomes an
    # explicit parser quarantine, not an empty healthy collection state.
    parser_result = _parse_capture(raw, source_family, capture_completed_at_utc, source_url)
    source_url = parser_result["source_url"]
    raw_sha = _sha(raw)
    metadata = {"schema_version": STORE_VERSION, "capture_id": capture_id,
                "raw_capture_sha256": raw_sha, "capture_completed_at_utc": parser_result["capture_completed_at_utc"],
                "source_family": source_family, "source_url": source_url,
                "parser_result": parser_result}
    metadata["metadata_sha256"] = _sha(_canonical(metadata))
    layout = _layout(root)
    with _lock(root):
        raw_path = layout["raw"] / f"{capture_id}.html"
        metadata_path = layout["metadata"] / f"{capture_id}.json"
        if raw_path.exists() or metadata_path.exists():
            raise CaptureConflictError(f"capture_id already published or needs recovery: {capture_id}")
        # A prior process might have failed between raw and metadata publish.
        orphan_raw = {path.stem for path in layout["raw"].glob("*.html")} - {path.stem for path in layout["metadata"].glob("*.json")}
        if orphan_raw:
            raise CaptureRecoveryRequired("raw capture exists without metadata: " + ",".join(sorted(orphan_raw)))
        _publish_exclusive(raw_path, raw)
        _publish_exclusive(metadata_path, _canonical(metadata))
        # If this fails, both raw and metadata are retained and the next store
        # operation deterministically rebuilds the missing journal generation.
        journal = _journal_from_metadata(layout)
        _publish_journal(layout, journal)
    return {"capture_id": capture_id, "raw_capture_sha256": raw_sha,
            "parser_result": json.loads(json.dumps(parser_result)),
            "journal": json.loads(json.dumps(journal)),
            "capture_completed_at_utc": parser_result["capture_completed_at_utc"],
            "capture_timestamp_provenance": "CALLER_DECLARED_NOT_AUTHENTICATED"}
