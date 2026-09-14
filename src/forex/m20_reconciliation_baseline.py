"""Read-only baseline joining retained M1 assessment identities to MT5 history.

The join key is an explicitly retained broker ``position_identifier``.  Times,
prices, volume, order comments, or trade direction are deliberately never used
as substitutes: they are insufficient to prove which decision caused a deal.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from forex.m20_history_report import HistoryReportInputError, load_and_build_history_report


SCHEMA = "forex.m20.reconciliation-baseline.v1"
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_BROKER_ACCEPTED = {"ACCEPTED", "ACCEPTED_PARTIAL"}


class ReconciliationBaselineError(ValueError):
    """A history report or retained assessment cannot be safely reconciled."""


def _sha(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _json(raw: bytes) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ReconciliationBaselineError("duplicate JSON field")
            result[key] = value
        return result
    try:
        return json.loads(raw, object_pairs_hook=pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(ReconciliationBaselineError("nonfinite JSON")))
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        raise ReconciliationBaselineError("retained assessment is not valid JSON") from exc


def assessment_identity(value: Any, *, source_sha256: str) -> dict[str, Any]:
    """Extract only declared identity fields from one retained M1 operation.

    ``position_identifier`` is accepted only when explicitly retained in the
    operation's execution result.  A ``position_ticket`` is not silently
    substituted because MT5 position tickets and position identifiers are not
    an interchangeable evidence contract.
    """
    if not isinstance(value, dict) or value.get("server") != "GOMarketsMU-Demo" or value.get("symbol") != "EURUSD":
        raise ReconciliationBaselineError("assessment is not a Demo EURUSD operation")
    proposal, snapshot, execution = value.get("proposal"), value.get("decision_snapshot"), value.get("execution")
    if not isinstance(proposal, dict) or not isinstance(snapshot, dict) or not isinstance(execution, dict):
        raise ReconciliationBaselineError("assessment lacks retained decision, snapshot, or execution identity")
    proposal_id, snapshot_id = proposal.get("proposal_id"), snapshot.get("snapshot_id")
    if not isinstance(proposal_id, str) or not proposal_id or not isinstance(snapshot_id, str) or not snapshot_id:
        raise ReconciliationBaselineError("assessment decision identity is invalid")
    if proposal.get("snapshot_id") != snapshot_id:
        raise ReconciliationBaselineError("assessment proposal does not bind its snapshot")
    position_identifier = execution.get("position_identifier")
    if position_identifier is not None and (isinstance(position_identifier, bool) or not isinstance(position_identifier, int) or position_identifier <= 0):
        raise ReconciliationBaselineError("assessment position identifier is invalid")
    outcome = value.get("outcome")
    if outcome is None and isinstance(value.get("reconciliation"), dict):
        outcome = value["reconciliation"].get("outcome")
    if outcome is not None and (not isinstance(outcome, dict) or outcome.get("proposal_id") != proposal_id):
        raise ReconciliationBaselineError("assessment outcome does not bind its proposal")
    return {
        "assessment_source_sha256": source_sha256,
        "proposal_id": proposal_id,
        "snapshot_id": snapshot_id,
        "execution_status": execution.get("status"),
        "position_identifier": position_identifier,
        "outcome_proposal_id": None if outcome is None else outcome["proposal_id"],
    }


def load_assessment_identity(path: Path) -> dict[str, Any]:
    if not isinstance(path, Path) or path.is_symlink() or not path.is_file():
        raise ReconciliationBaselineError("assessment source must be a regular non-symlink file")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ReconciliationBaselineError("assessment source cannot be read") from exc
    return assessment_identity(_json(raw), source_sha256=_sha(raw))


def reconcile(*, history_report: dict[str, Any], assessments: list[dict[str, Any]]) -> dict[str, Any]:
    """Classify exact identity joins without repairing, inferring, or writing."""
    if (not isinstance(history_report, dict) or history_report.get("schema_version") != "forex.m20.history-report.v1"
            or history_report.get("server") != "GOMarketsMU-Demo" or history_report.get("currency") != "AUD"
            or not isinstance(history_report.get("closed_positions"), list)):
        raise ReconciliationBaselineError("history report is not a complete Demo history summary")
    if not isinstance(assessments, list) or not all(isinstance(item, dict) for item in assessments):
        raise ReconciliationBaselineError("assessment identities must be a list")
    positions: dict[int, dict[str, Any]] = {}
    for row in history_report["closed_positions"]:
        if (not isinstance(row, dict) or set(row) != {"position_id", "entry_ticket", "exit_ticket", "net_realized_aud", "exit_reason", "stop_loss_like_exit"}
                or isinstance(row.get("position_id"), bool) or not isinstance(row.get("position_id"), int) or row["position_id"] <= 0):
            raise ReconciliationBaselineError("history closed position is invalid")
        if row["position_id"] in positions:
            raise ReconciliationBaselineError("history report has duplicate closed position identity")
        positions[row["position_id"]] = row
    by_position: dict[int, list[dict[str, Any]]] = defaultdict(list)
    by_proposal: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for identity in assessments:
        required = {"assessment_source_sha256", "proposal_id", "snapshot_id", "execution_status", "position_identifier", "outcome_proposal_id"}
        if (set(identity) != required or not isinstance(identity["assessment_source_sha256"], str)
                or _DIGEST.fullmatch(identity["assessment_source_sha256"]) is None
                or not isinstance(identity["proposal_id"], str) or not identity["proposal_id"]
                or not isinstance(identity["snapshot_id"], str) or not identity["snapshot_id"]
                or identity["execution_status"] is not None and not isinstance(identity["execution_status"], str)
                or identity["position_identifier"] is not None and (isinstance(identity["position_identifier"], bool)
                                                                  or not isinstance(identity["position_identifier"], int)
                                                                  or identity["position_identifier"] <= 0)
                or identity["outcome_proposal_id"] is not None and identity["outcome_proposal_id"] != identity["proposal_id"]):
            raise ReconciliationBaselineError("assessment identity shape is invalid")
        by_proposal[identity["proposal_id"]].append(identity)
        if (identity["execution_status"] in _BROKER_ACCEPTED
                and identity["position_identifier"] is not None):
            by_position[identity["position_identifier"]].append(identity)

    assessment_rows: list[dict[str, Any]] = []
    for identity in assessments:
        position_id = identity["position_identifier"]
        duplicate_decision = len(by_proposal[identity["proposal_id"]]) > 1
        if duplicate_decision:
            status = "AMBIGUOUS_DECISION_IDENTITY"
        elif identity["execution_status"] not in _BROKER_ACCEPTED or position_id is None:
            status = "MISSING_EVIDENCE"
        elif len(by_position[position_id]) > 1:
            status = "AMBIGUOUS_POSITION_IDENTITY"
        elif position_id not in positions:
            status = "MISSING_MT5_HISTORY"
        elif identity["outcome_proposal_id"] is None:
            status = "MISSING_EVIDENCE"
        else:
            status = "MATCHED"
        assessment_rows.append({**identity, "reconciliation_status": status,
                                "matched_position_id": position_id if status == "MATCHED" else None})

    broker_rows: list[dict[str, Any]] = []
    for position_id, position in sorted(positions.items()):
        candidates = by_position.get(position_id, [])
        if not candidates:
            status, proposal_ids = "UNMATCHED_MT5_HISTORY", []
        elif len(candidates) > 1:
            status, proposal_ids = "AMBIGUOUS_POSITION_IDENTITY", sorted(item["proposal_id"] for item in candidates)
        elif len(by_proposal[candidates[0]["proposal_id"]]) > 1:
            status, proposal_ids = "AMBIGUOUS_DECISION_IDENTITY", [candidates[0]["proposal_id"]]
        elif candidates[0]["outcome_proposal_id"] is None:
            status, proposal_ids = "MISSING_EVIDENCE", [candidates[0]["proposal_id"]]
        else:
            status, proposal_ids = "MATCHED", [candidates[0]["proposal_id"]]
        broker_rows.append({"position_id": position_id, "entry_ticket": position["entry_ticket"],
                            "exit_ticket": position["exit_ticket"], "reconciliation_status": status,
                            "proposal_ids": proposal_ids})
    counts: dict[str, int] = defaultdict(int)
    for row in assessment_rows + broker_rows:
        counts[row["reconciliation_status"]] += 1
    return {"schema_version": SCHEMA, "history_source_sha256": history_report.get("source_sha256"),
            "assessment_count": len(assessment_rows), "closed_position_count": len(broker_rows),
            "assessment_rows": assessment_rows, "broker_rows": broker_rows,
            "status_counts": dict(sorted(counts.items())), "execution_authority": False,
            "limitations": ["Only an explicit retained position_identifier can link a decision to MT5 history.",
                            "No time, price, side, volume, comment, ticket, or inferred trade matching is performed."]}


def reconcile_files(*, history_path: Path, assessment_paths: list[Path]) -> dict[str, Any]:
    try:
        history = load_and_build_history_report(history_path)
    except HistoryReportInputError as exc:
        raise ReconciliationBaselineError(f"history source refused: {exc}") from exc
    return reconcile(history_report=history, assessments=[load_assessment_identity(path) for path in assessment_paths])
