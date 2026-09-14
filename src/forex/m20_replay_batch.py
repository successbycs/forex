"""Read-only inventory of direct retained M20 operation exports.

This module intentionally reports every source separately.  It never merges
financial amounts across source files because source-level duplicate identity
or outcome provenance has not been independently established.  A malformed
or unsupported source is retained as a refusal in the inventory rather than
being omitted or repaired.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from forex.event_capture_store import _no_symlink_ancestors
from forex.m20_replay_report import ReplayReportInputError, build_replay_report
from forex.m20_retained_export import RetainedExportInputError, _strict_json, adapt_retained_m20_export


SCHEMA_VERSION = "forex.m20.retained-replay-batch-report.v1"
_MAX_RECORDS = 256
_MAX_SOURCE_BYTES = 4 * 1024 * 1024


class ReplayBatchInputError(ValueError):
    """A retained M20 batch root or source is not safe to inventory."""


def _trusted_root(root: Path) -> Path:
    if not isinstance(root, Path) or not root.exists() or root.is_symlink() or not root.is_dir():
        raise ReplayBatchInputError("batch root must be an existing trusted directory")
    try:
        _no_symlink_ancestors(root)
    except ValueError as exc:
        raise ReplayBatchInputError("batch root has unsafe symlink ancestry") from exc
    return root


def _sources(root: Path) -> list[Path]:
    """Return only one operation export per direct evidence-run directory."""
    entries = sorted(root.glob("*/demo-trading-operation.json"), key=lambda item: item.parent.name)
    if len(entries) > _MAX_RECORDS:
        raise ReplayBatchInputError("retained batch exceeds fixed source limit")
    for path in entries:
        if path.parent.is_symlink() or path.is_symlink() or not path.is_file():
            raise ReplayBatchInputError("retained batch source is unsafe")
    return entries


def build_retained_replay_batch(*, root: Path) -> dict[str, Any]:
    """Inventory direct retained exports without modifying any source or state."""
    root = _trusted_root(root)
    entries: list[dict[str, Any]] = []
    for path in _sources(root):
        relative_path = str(path.relative_to(root))
        source_sha256: str | None = None
        try:
            raw = path.read_bytes()
            if len(raw) > _MAX_SOURCE_BYTES:
                raise ReplayBatchInputError("retained batch source exceeds fixed size limit")
            source_sha256 = "sha256:" + hashlib.sha256(raw).hexdigest()
            document = adapt_retained_m20_export(
                _strict_json(raw), source_sha256=source_sha256, source_path=relative_path
            )
            report = build_replay_report(document, source_sha256=source_sha256, source_path=relative_path)
        except (OSError, RetainedExportInputError, ReplayReportInputError, ReplayBatchInputError) as exc:
            entries.append({
                "source_path": relative_path,
                "source_sha256": source_sha256,
                "state": "REFUSED",
                "reason": str(exc),
                "execution_authority": False,
            })
            continue
        entries.append({
            "source_path": relative_path,
            "source_sha256": source_sha256,
            "state": "REPORTED",
            "replayable_pair_count": document["retained_export_coverage"]["replayable_pair_count"],
            "coverage_only_row_count": document["retained_export_coverage"]["coverage_only_row_count"],
            "valid_record_count": report["valid_record_count"],
            "error_record_count": report["error_record_count"],
            "broker_outcome_count": report["broker_outcome_coverage"]["outcome_count"],
            "execution_authority": False,
        })
    reported = [entry for entry in entries if entry["state"] == "REPORTED"]
    return {
        "schema_version": SCHEMA_VERSION,
        "root": str(root),
        "source_count": len(entries),
        "reported_source_count": len(reported),
        "refused_source_count": len(entries) - len(reported),
        "replayable_pair_count": sum(entry["replayable_pair_count"] for entry in reported),
        "valid_record_count": sum(entry["valid_record_count"] for entry in reported),
        "error_record_count": sum(entry["error_record_count"] for entry in reported),
        "broker_outcome_count": sum(entry["broker_outcome_count"] for entry in reported),
        "aggregate_financial_conclusion": "NOT_EVALUATED_SOURCE_LEVEL_DUPLICATES_AND_OUTCOMES_NOT_RECONCILED",
        "sources": entries,
        "execution_authority": False,
    }
