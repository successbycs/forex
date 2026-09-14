"""Strict read-only validation for immutable listener assessment spool files.

The listener writes source records after a completed runner invocation.  This
module deliberately does not delete, acknowledge, or contact the broker: a
future drain service must first retain the returned bytes independently.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any


SCHEMA = "forex.m20.latest-assessment.v1"
_NAME = re.compile(r"[0-9]{20}[.]json")
_RELEASE = re.compile(r"[0-9a-f]{16}")


class AssessmentSpoolError(ValueError):
    """The immutable source directory is incomplete, unsafe, or inconsistent."""


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise AssessmentSpoolError("duplicate JSON field")
        value[key] = item
    return value


def _load(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise AssessmentSpoolError("spool source file is unsafe")
    try:
        value = json.loads(path.read_bytes(), object_pairs_hook=_pairs,
                           parse_constant=lambda item: (_ for _ in ()).throw(AssessmentSpoolError("nonfinite JSON value")))
    except (OSError, json.JSONDecodeError) as exc:
        raise AssessmentSpoolError("spool source file is not valid JSON") from exc
    if not isinstance(value, dict):
        raise AssessmentSpoolError("spool source record is not an object")
    return value


def read_immutable_spool(root: Path, *, listener_release_id: str) -> dict[str, Any]:
    """Read all complete source records and prove internal sequence continuity.

    The first sequence is a baseline because a spool may begin after a release.
    Any gap after that point, unfinished staging file, unexpected entry, or
    disagreement between filename and record refuses the whole read.
    """
    if not isinstance(root, Path) or not root.exists() or root.is_symlink() or not root.is_dir():
        raise AssessmentSpoolError("spool root must be an existing non-symlink directory")
    if not isinstance(listener_release_id, str) or _RELEASE.fullmatch(listener_release_id) is None:
        raise AssessmentSpoolError("listener release ID is invalid")
    entries = sorted(root.iterdir(), key=lambda item: item.name)
    if any(item.is_symlink() or _NAME.fullmatch(item.name) is None for item in entries):
        raise AssessmentSpoolError("spool root contains an unfinished or unsafe entry")
    records: list[dict[str, Any]] = []
    previous: int | None = None
    for path in entries:
        record = _load(path)
        sequence = record.get("assessment_sequence")
        assessment = record.get("assessment")
        if (set(record) != {"schema_version", "listener_release_id", "assessment_sequence",
                           "assessment_started_at_utc", "assessment_completed_at_utc", "assessment"}
                or record.get("schema_version") != SCHEMA or record.get("listener_release_id") != listener_release_id
                or isinstance(sequence, bool) or not isinstance(sequence, int) or sequence <= 0
                or path.name != f"{sequence:020d}.json" or not isinstance(assessment, dict)
                or assessment.get("server") != "GOMarketsMU-Demo" or assessment.get("symbol") != "EURUSD"
                or not isinstance(assessment.get("decision_snapshot"), dict)
                or not isinstance(assessment.get("proposal"), dict)):
            raise AssessmentSpoolError("spool source record binding is invalid")
        if previous is not None and sequence != previous + 1:
            raise AssessmentSpoolError("spool assessment sequence has a gap")
        previous = sequence
        raw = path.read_bytes()
        records.append({"assessment_sequence": sequence, "source_path": str(path),
                        "source_sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
                        "record": record})
    return {"schema_version": "forex.m20.assessment-spool-read.v1", "listener_release_id": listener_release_id,
            "coverage_status": "EMPTY" if not records else "BASELINE_CONTIGUOUS",
            "first_assessment_sequence": None if not records else records[0]["assessment_sequence"],
            "last_assessment_sequence": None if not records else records[-1]["assessment_sequence"],
            "records": records, "execution_authority": False}
