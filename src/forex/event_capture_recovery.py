"""Exact-request recovery for partially published local BLS captures.

This module never publishes raw bytes.  It can only complete missing metadata
or a missing immutable journal generation after proving that the caller's raw
bytes and declared capture identity match what is already retained.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from forex.event_capture_store import (
    STORE_VERSION,
    CaptureConflictError,
    CaptureRecoveryRequired,
    EventCaptureStoreError,
    _canonical,
    _journal_from_metadata,
    _existing_layout,
    _lock,
    _publish_exclusive,
    _publish_journal,
    _parse_capture,
    _safe_id,
    _sha,
    _validated_metadata,
)


def _result(*, capture_id: str, raw_sha: str, parser_result: dict[str, Any], journal: dict[str, Any]) -> dict[str, Any]:
    return {
        "capture_id": capture_id,
        "raw_capture_sha256": raw_sha,
        "parser_result": json.loads(json.dumps(parser_result)),
        "journal": json.loads(json.dumps(journal)),
        "capture_completed_at_utc": parser_result["capture_completed_at_utc"],
        "capture_timestamp_provenance": "CALLER_DECLARED_NOT_AUTHENTICATED",
        "recovery": "EXACT_EXISTING_RAW_ONLY",
    }


def resume_bls_capture(root: Path, *, capture_id: str, raw: bytes, source_family: str,
                       capture_completed_at_utc: str, source_url: str | None = None) -> dict[str, Any]:
    """Complete a partial capture only when the retry exactly matches it.

    A missing raw file is refused: a caller must use ``retain_bls_capture`` for
    a new capture.  Existing raw never changes, and an existing metadata file
    must match the supplied family, completion timestamp, bytes and parser
    result exactly.
    """
    _safe_id(capture_id)
    parser_result = _parse_capture(raw, source_family, capture_completed_at_utc, source_url)
    source_url = parser_result["source_url"]
    raw_sha = _sha(raw)
    expected = {
        "schema_version": STORE_VERSION,
        "capture_id": capture_id,
        "raw_capture_sha256": raw_sha,
        "capture_completed_at_utc": parser_result["capture_completed_at_utc"],
        "source_family": source_family,
        "source_url": source_url,
        "parser_result": parser_result,
    }
    expected["metadata_sha256"] = _sha(_canonical(expected))
    if not isinstance(root, Path):
        raise EventCaptureStoreError("root must be an explicit pathlib.Path")
    if not (root / "raw" / f"{capture_id}.html").exists():
        raise CaptureRecoveryRequired("raw capture is missing; retain_bls_capture is required for a new capture")
    layout = _existing_layout(root)
    with _lock(root):
        raw_path = layout["raw"] / f"{capture_id}.html"
        metadata_path = layout["metadata"] / f"{capture_id}.json"
        if raw_path.is_symlink() or not raw_path.is_file():
            raise CaptureRecoveryRequired("raw capture is missing; retain_bls_capture is required for a new capture")
        if _sha(raw_path.read_bytes()) != raw_sha:
            raise CaptureConflictError("supplied raw bytes do not match immutable capture")
        if metadata_path.exists():
            existing = _validated_metadata(metadata_path, layout["raw"])
            if _canonical(existing) != _canonical(expected):
                raise CaptureConflictError("supplied capture metadata conflicts with immutable capture metadata")
        else:
            # The raw file already exists and matched byte-for-byte.  Metadata
            # is the only missing immutable artifact this recovery may publish.
            _publish_exclusive(metadata_path, _canonical(expected))
        # This validates every retained raw/metadata pair, preserves the latest
        # immutable prefix, and refuses unrelated orphan or late-capture state.
        journal = _journal_from_metadata(layout)
        _publish_journal(layout, journal)
    return _result(capture_id=capture_id, raw_sha=raw_sha, parser_result=parser_result, journal=journal)
