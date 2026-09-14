"""Read-only projection of one explicit retained BLS store into canonical facts."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from forex.bls_journal_calendar_projection import project_bls_journal
from forex.event_capture_store import read_capture_journal_with_metadata_receipts


def project_retained_bls_store(root: Path) -> dict[str, Any]:
    """Validate immutable store evidence, then project it without side effects."""
    if not isinstance(root, Path):
        raise ValueError("store root must be an explicit pathlib.Path")
    retained = read_capture_journal_with_metadata_receipts(root)
    return project_bls_journal(retained["journal"],
                               capture_receipt_sha256_by_id=retained["capture_receipt_sha256_by_id"])
