"""Validate one fixed T480 spool page and mirror its immutable source bytes."""
from __future__ import annotations
import base64
import binascii
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any

from forex.m20_spool_drain import SpoolDrainError, _load_cursor, _trusted, drain

_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_RELEASE = re.compile(r"[0-9a-f]{16}")

class SpoolPageError(ValueError):
    pass


def _trusted_mirror(capture_root: Path, *, release: str) -> Path:
    """Create and validate each local mirror component below a trusted root.

    Checking only the final release directory is insufficient: ``mkdir`` can
    follow a pre-existing symlink in its parent.  The mirror is local staging,
    but it still contains raw source bytes and must never escape the configured
    capture root.
    """
    parent = capture_root / ".m20-spool-page-source"
    for path in (parent, parent / release):
        try:
            path.mkdir(mode=0o700, exist_ok=True)
        except OSError as exc:
            raise SpoolPageError("local spool mirror cannot be created") from exc
        if path.is_symlink() or not path.is_dir():
            raise SpoolPageError("local spool mirror is unsafe")
    return parent / release


def _retain_mirror_record(mirror: Path, *, sequence: int, raw: bytes) -> None:
    """Publish raw mirror bytes by an exclusive link after durable staging."""
    path = mirror / f"{sequence:020d}.json"
    if path.exists():
        if path.is_symlink() or not path.is_file() or path.read_bytes() != raw:
            raise SpoolPageError("local spool mirror conflicts")
        return
    staging = mirror / f".{sequence:020d}.pending"
    if staging.exists() or staging.is_symlink():
        raise SpoolPageError("local spool mirror has unfinished staging")
    try:
        with staging.open("xb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(staging, path)
        except FileExistsError:
            if path.is_symlink() or not path.is_file() or path.read_bytes() != raw:
                raise SpoolPageError("local spool mirror conflicts")
        finally:
            if staging.exists() and not staging.is_symlink():
                staging.unlink()
        directory = os.open(mirror, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except SpoolPageError:
        raise
    except OSError as exc:
        raise SpoolPageError("local spool mirror cannot retain source bytes") from exc

def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise SpoolPageError("duplicate JSON field")
        result[key] = value
    return result

def _json(raw: bytes | str):
    try:
        return json.loads(raw, object_pairs_hook=_pairs, parse_constant=lambda _: (_ for _ in ()).throw(SpoolPageError("nonfinite JSON value")))
    except (TypeError, json.JSONDecodeError) as exc:
        raise SpoolPageError("spool page is not valid JSON") from exc

def parse_page(raw: bytes, *, after_assessment_sequence: int) -> dict[str, Any]:
    outer = _json(raw)
    if not isinstance(outer, dict) or outer.get("operation") != "m20_listener_spool_page" or outer.get("ok") is not True:
        raise SpoolPageError("result is not a successful fixed spool-page operation")
    result = outer.get("result")
    if not isinstance(result, dict) or not isinstance(result.get("stdout"), str):
        raise SpoolPageError("spool page has no operation stdout")
    page = _json(result["stdout"])
    if not isinstance(page, dict) or page.get("after_assessment_sequence") != after_assessment_sequence:
        raise SpoolPageError("spool page cursor binding is invalid")
    release = page.get("listener_release_id")
    if not isinstance(release, str) or _RELEASE.fullmatch(release) is None:
        raise SpoolPageError("spool page release is invalid")
    if page.get("observation") == "SPOOL_ABSENT" and page.get("records") == []:
        return {"state": "SPOOL_ABSENT", "listener_release_id": release, "records": []}
    rows = page.get("records")
    if page.get("observation") != "AVAILABLE" or not isinstance(rows, list) or len(rows) > 8:
        raise SpoolPageError("spool page shape is invalid")
    records = []
    previous = after_assessment_sequence
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != {"assessment_sequence", "raw_sha256", "raw_base64"}:
            raise SpoolPageError("spool page row shape is invalid")
        seq = row["assessment_sequence"]
        if isinstance(seq, bool) or not isinstance(seq, int) or seq <= 0:
            raise SpoolPageError("spool page sequence is not contiguous")
        # With no local cursor, a source spool may legitimately begin after a
        # listener release's earliest assessments. That first returned record
        # is a baseline, matching ``read_immutable_spool``. Once a cursor is
        # present (or after the baseline within this page), every sequence is
        # exact and contiguous so no intervening source record is skipped.
        if not (index == 0 and after_assessment_sequence == 0) and seq != previous + 1:
            raise SpoolPageError("spool page sequence is not contiguous")
        if not isinstance(row["raw_sha256"], str) or _DIGEST.fullmatch(row["raw_sha256"]) is None or not isinstance(row["raw_base64"], str):
            raise SpoolPageError("spool page row binding is invalid")
        try:
            decoded = base64.b64decode(row["raw_base64"], validate=True)
        except (ValueError, binascii.Error) as exc:
            raise SpoolPageError("spool page row is not base64") from exc
        if "sha256:" + hashlib.sha256(decoded).hexdigest() != row["raw_sha256"]:
            raise SpoolPageError("spool page source hash mismatch")
        record = _json(decoded)
        if (not isinstance(record, dict) or record.get("listener_release_id") != release
                or record.get("assessment_sequence") != seq):
            raise SpoolPageError("spool page source record binding is invalid")
        records.append((seq, decoded))
        previous = seq
    return {"state": "AVAILABLE", "listener_release_id": release, "records": records}

def retain_page_and_drain(*, adapter_raw: bytes, capture_root: Path) -> dict[str, Any]:
    try:
        capture_root = _trusted(capture_root, label="capture_root")
    except SpoolDrainError as exc:
        raise SpoolPageError(str(exc)) from exc
    cursor = _load_cursor(capture_root)
    after = 0 if cursor is None else cursor["assessment_sequence"]
    page = parse_page(adapter_raw, after_assessment_sequence=after)
    if cursor is not None and page["listener_release_id"] != cursor["listener_release_id"]:
        raise SpoolPageError("spool page release differs from local cursor")
    if page["state"] == "SPOOL_ABSENT":
        return {"state": "SPOOL_ABSENT", "execution_authority": False}
    mirror = _trusted_mirror(capture_root, release=page["listener_release_id"])
    for seq, decoded in page["records"]:
        _retain_mirror_record(mirror, sequence=seq, raw=decoded)
    try:
        result = drain(spool_root=mirror, capture_root=capture_root, listener_release_id=page["listener_release_id"])
    except SpoolDrainError as exc:
        raise SpoolPageError(f"local spool drain refused: {exc}") from exc
    return {"state": "DRAINED", "page_record_count": len(page["records"]), **result}
