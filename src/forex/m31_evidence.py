"""Offline M31 evidence-bundle creation and verification rules."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from forex.m31_scorecard import M31ScorecardInputError, parse_protocol, scorecard_from_raw
from forex.m20_history_report import HistoryReportInputError, build_history_report


MARKER = "FOREX_M31_EVIDENCE_VERIFIED"
REQUIRED = {"protocol.json", "protocol-receipt.json", "completeness.json", "lifecycle.json", "broker-history.json", "scorecard.json", "revision.txt", "manifest.json"}


class M31EvidenceError(ValueError):
    """An M31 bundle is incomplete, altered, or internally inconsistent."""


def _sha(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _read(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise M31EvidenceError(f"required regular artifact is absent: {path.name}")
    return path.read_bytes()


def _json(raw: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise M31EvidenceError(f"{label} is not valid JSON") from exc
    if not isinstance(value, dict):
        raise M31EvidenceError(f"{label} must be an object")
    return value


def verify_bundle(bundle: Path, *, expected_revision: str | None = None) -> dict[str, Any]:
    """Verify a retained M31 bundle without contacting any external service."""
    if not isinstance(bundle, Path) or bundle.is_symlink() or not bundle.is_dir():
        raise M31EvidenceError("bundle must be a regular directory")
    actual_names = {path.name for path in bundle.iterdir() if path.is_file()}
    if actual_names != REQUIRED:
        raise M31EvidenceError("bundle artifact set is invalid")
    raw = {name: _read(bundle / name) for name in REQUIRED}
    manifest = _json(raw["manifest.json"], "manifest")
    if manifest.get("schema_version") != "forex.m31.evidence-bundle.v1" or manifest.get("milestone_id") != "M31" or manifest.get("observed_result") != "FOREX_M31_EVIDENCE_CAPTURED":
        raise M31EvidenceError("manifest binding is invalid")
    revision = raw["revision.txt"].decode("utf-8").strip()
    if not revision or manifest.get("git_revision") != revision or (expected_revision is not None and revision != expected_revision):
        raise M31EvidenceError("bundle revision does not match expected revision")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or {item.get("path") for item in artifacts if isinstance(item, dict)} != REQUIRED - {"manifest.json"}:
        raise M31EvidenceError("manifest artifact inventory is invalid")
    for item in artifacts:
        if not isinstance(item, dict) or item.get("sha256") != _sha(raw[item["path"]]):
            raise M31EvidenceError("artifact digest mismatch")
    try:
        protocol = parse_protocol(raw["protocol.json"])
        computed = scorecard_from_raw(protocol_raw=raw["protocol.json"], completeness_raw=raw["completeness.json"], lifecycle_raw=raw["lifecycle.json"])
        broker_history = build_history_report(raw["broker-history.json"])
    except (M31ScorecardInputError, HistoryReportInputError) as exc:
        raise M31EvidenceError(f"captured input refused: {exc}") from exc
    stored = _json(raw["scorecard.json"], "scorecard")
    if stored != computed:
        raise M31EvidenceError("stored scorecard differs from deterministic result")
    if computed.get("execution_authority") is not False or protocol["server"] != "GOMarketsMU-Demo" or protocol["symbol"] != "EURUSD":
        raise M31EvidenceError("Demo-only safety binding is invalid")
    receipt = _json(raw["protocol-receipt.json"], "protocol receipt")
    if (receipt.get("schema_version") != "forex.m31.protocol-receipt.v1" or receipt.get("git_revision") != revision
            or receipt.get("protocol_sha256") != _sha(raw["protocol.json"]) or receipt.get("execution_authority") is not False):
        raise M31EvidenceError("protocol receipt binding is invalid")
    from datetime import datetime
    try:
        declared = datetime.fromisoformat(str(receipt["declared_at_utc"]).replace("Z", "+00:00"))
        start = datetime.fromisoformat(protocol["interval"]["from_utc"].replace("Z", "+00:00"))
    except (KeyError, ValueError) as exc:
        raise M31EvidenceError("protocol receipt timestamp is invalid") from exc
    if declared.tzinfo is None or start.tzinfo is None or declared >= start:
        raise M31EvidenceError("protocol was not declared before its interval")
    return {"marker": MARKER, "milestone_id": "M31", "git_revision": revision,
            "interval": protocol["interval"], "decision_count": computed["counts"]["decisions"],
            "reconciled_closed": computed["counts"]["reconciled_closed"],
            "broker_history_closed_positions": broker_history["closed_position_count"], "execution_authority": False}
