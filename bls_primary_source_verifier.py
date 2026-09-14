"""Read-only verification and conservative primary-context projection for BLS."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from forex.bls_collection import validate_response
from forex.bls_monthly_events import _source_month
from forex.event_capture_store import (
    EventCaptureStoreError, _existing_layout, _no_symlink_ancestors, _sha,
    _validated_metadata, read_capture_store,
)


SCHEMA = "forex.bls-primary-source-verifier.v1"
_FAMILIES = {
    "bls-cpi-release-schedule": "US_CPI",
    "bls-employment-situation-release-schedule": "US_EMPLOYMENT_SITUATION",
}
_PRIMARY_SOURCE_ID = "bls-monthly-release-calendar"
_PRIMARY_URL_TEMPLATE = "https://www.bls.gov/schedule/{year}/{month:02d}_sched_list.htm"


class BLSPrimarySourceVerificationError(RuntimeError):
    """Retained BLS source evidence is incomplete, unsafe, or inconsistent."""


def _read(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise BLSPrimarySourceVerificationError("retained BLS artifact is unsafe or missing")
    try:
        return path.read_bytes()
    except OSError as exc:
        raise BLSPrimarySourceVerificationError("retained BLS artifact cannot be read") from exc


def _acquisition(root: Path, *, capture_id: str, source_url: str, raw_html: bytes,
                 capture_completed_at_utc: str) -> dict[str, Any]:
    """Validate the retained HTTP response that produced one parsed capture."""
    try:
        year, month = _source_month(source_url)
    except Exception as exc:
        raise BLSPrimarySourceVerificationError("BLS capture source URL is invalid") from exc
    directory = root / "acquisitions" / capture_id
    _no_symlink_ancestors(directory)
    if directory.is_symlink() or not directory.is_dir():
        raise BLSPrimarySourceVerificationError("BLS acquisition receipt is missing")
    paths = list(directory.glob("*.json"))
    if len(paths) != 1 or paths[0].is_symlink() or not paths[0].is_file():
        raise BLSPrimarySourceVerificationError("exactly one BLS acquisition receipt is required")
    raw = _read(paths[0])
    if paths[0].stem != _sha(raw).removeprefix("sha256:"):
        raise BLSPrimarySourceVerificationError("BLS acquisition receipt hash mismatch")
    try:
        response, body = validate_response(raw, year=year, month=month)
    except (ValueError, json.JSONDecodeError) as exc:
        raise BLSPrimarySourceVerificationError("BLS acquisition receipt is invalid") from exc
    if response["outcome"] != "SUCCESS" or body != raw_html:
        raise BLSPrimarySourceVerificationError("BLS acquisition receipt does not bind parsed raw HTML")
    if response["requested_url"] != source_url or response["completed_at_utc"] != capture_completed_at_utc:
        raise BLSPrimarySourceVerificationError("BLS acquisition receipt provenance conflicts with capture")
    return {"observation_sha256": _sha(raw), "requested_url": source_url,
            "completed_at_utc": capture_completed_at_utc}


def verify_bls_primary_source(root: Path) -> dict[str, Any]:
    """Verify retained BLS monthly evidence without modifying the local root.

    Current primary-context configuration declares a URL *template*, whereas
    each official retained source has one concrete monthly URL.  This verifier
    therefore exports detailed candidate observations but explicitly withholds
    direct context ingestion rather than pretending a concrete URL equals the
    literal template.
    """
    if not isinstance(root, Path) or not root.exists() or not root.is_dir() or root.is_symlink():
        raise BLSPrimarySourceVerificationError("root must be an existing non-symlink directory")
    try:
        _no_symlink_ancestors(root)
        layout = _existing_layout(root)
        store = read_capture_store(root)
    except EventCaptureStoreError as exc:
        raise BLSPrimarySourceVerificationError("BLS retained store is invalid or partial") from exc
    journal = store["journal"]
    details: list[dict[str, Any]] = []
    context_candidates: list[dict[str, Any]] = []
    capture_by_id = {capture["capture_id"]: capture for capture in journal["captures"]}
    for capture_id in sorted(capture_by_id):
        capture = capture_by_id[capture_id]
        if capture["source_family"] != "BLS_MONTHLY":
            raise BLSPrimarySourceVerificationError("non-monthly capture is outside this BLS verifier")
        try:
            metadata = _validated_metadata(layout["metadata"] / f"{capture_id}.json", layout["raw"])
        except EventCaptureStoreError as exc:
            raise BLSPrimarySourceVerificationError("BLS raw/metadata integrity failure") from exc
        raw_html = _read(layout["raw"] / f"{capture_id}.html")
        receipt = _acquisition(root, capture_id=capture_id, source_url=capture["source_url"], raw_html=raw_html,
                               capture_completed_at_utc=capture["capture_completed_at_utc"])
        if metadata["metadata_sha256"] != _sha(__import__("forex.event_capture_store", fromlist=["_canonical"])._canonical({key: metadata[key] for key in metadata if key != "metadata_sha256"})):
            raise BLSPrimarySourceVerificationError("BLS metadata hash mismatch")
        # Capture content is immutable and journal-validated.  Read it here,
        # rather than only the current journal revisions, so repeated monthly
        # captures remain separately visible instead of being overwritten by
        # revision compaction.
        source_records = capture["content"]["records"]
        for record in source_records:
            family = _FAMILIES.get(record.get("source_id"))
            if family is None:
                continue
            candidate = {"source_id": _PRIMARY_SOURCE_ID, "source_url": capture["source_url"],
                         "capture_state": "RETAINED", "coverage_status": "UNKNOWN",
                         "captured_at_utc": capture["capture_completed_at_utc"],
                         "source_sha256": capture["payload_sha256"]}
            context_candidates.append({"family_id": family, "event_id": record["event_id"],
                                       "event_revision": next((row["revision"] for row in journal["records"]
                                                               if row["event_id"] == record["event_id"]), None),
                                       "observation": candidate})
        details.append({"capture_id": capture_id, "capture_completed_at_utc": capture["capture_completed_at_utc"],
                        "raw_capture_sha256": capture["payload_sha256"], "metadata_sha256": metadata["metadata_sha256"],
                        "acquisition_receipt": receipt, "source_url": capture["source_url"],
                        "journal_sha256": journal["journal_sha256"], "event_count": len(source_records)})
    return {"schema_version": SCHEMA, "execution_authority": False, "coverage_status": "UNKNOWN",
            "qualification_state": "RETAINED_CAPTURE_ACTIVE_COVERAGE_UNKNOWN", "journal_sha256": journal["journal_sha256"],
            "captures": details, "context_candidates": context_candidates,
            "primary_context_observations": [],
            "primary_context_limitation": {
                "state": "REFUSED_SOURCE_URL_TEMPLATE_MISMATCH",
                "declared_template": _PRIMARY_URL_TEMPLATE,
                "reason": "Concrete retained BLS monthly URLs cannot equal the current literal primary-context URL template; no observation is injected or qualified.",
            }}
