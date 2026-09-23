"""Pure, fail-closed M31 Demo evaluation scorecard."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from typing import Any


SCHEMA_VERSION = "forex.m31.demo-scorecard.v1"
PROTOCOL_SCHEMA_VERSION = "forex.m31.evaluation-protocol.v1"
COMPLETENESS_SCHEMA_VERSION = "forex.m1.postgres-completeness-summary.v1"


class M31ScorecardInputError(ValueError):
    """An input cannot support an honest M31 scorecard."""


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise M31ScorecardInputError("duplicate JSON field")
        result[key] = value
    return result


def _json(raw: bytes | str, label: str) -> Any:
    try:
        return json.loads(raw, object_pairs_hook=_pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(M31ScorecardInputError("non-finite JSON")))
    except (TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise M31ScorecardInputError(f"{label} is not valid JSON") from exc


def _instant(value: Any, label: str) -> datetime:
    if not isinstance(value, str):
        raise M31ScorecardInputError(f"{label} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise M31ScorecardInputError(f"{label} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise M31ScorecardInputError(f"{label} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _number_or_unknown(value: Any, label: str) -> str:
    if value is None:
        return "UNKNOWN"
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise M31ScorecardInputError(f"{label} must be numeric or null")
    return "PRESENT"


def parse_protocol(raw: bytes | str) -> dict[str, Any]:
    value = _json(raw, "protocol")
    required = {"schema_version", "interval", "baseline", "server", "symbol", "captured_at_utc"}
    if not isinstance(value, dict) or set(value) != required:
        raise M31ScorecardInputError("protocol schema is unsupported")
    if value["schema_version"] != PROTOCOL_SCHEMA_VERSION or value["server"] != "GOMarketsMU-Demo" or value["symbol"] != "EURUSD":
        raise M31ScorecardInputError("protocol Demo identity is invalid")
    interval = value["interval"]
    if not isinstance(interval, dict) or set(interval) != {"from_utc", "to_utc", "bounds"} or interval["bounds"] != "inclusive/exclusive":
        raise M31ScorecardInputError("protocol interval is invalid")
    start, end = _instant(interval["from_utc"], "interval from_utc"), _instant(interval["to_utc"], "interval to_utc")
    if start >= end or (end - start).total_seconds() > 86400:
        raise M31ScorecardInputError("protocol interval must be positive and at most 24 hours")
    baseline = value["baseline"]
    if baseline != {"kind": "NO_CHANGE", "trade_count": 0, "realized_pnl_aud": 0, "cost_aud": 0}:
        raise M31ScorecardInputError("protocol baseline must be the declared NO_CHANGE baseline")
    _instant(value["captured_at_utc"], "protocol captured_at_utc")
    return value


def parse_completeness(raw: bytes | str) -> dict[str, Any]:
    wrapper = _json(raw, "completeness wrapper")
    if not isinstance(wrapper, dict) or wrapper.get("operation") != "forex_m1_postgres_completeness_summary":
        raise M31ScorecardInputError("completeness operation binding is invalid")
    result = wrapper.get("result")
    if not isinstance(result, dict) or not result.get("ok") or not isinstance(result.get("stdout"), str):
        raise M31ScorecardInputError("completeness result is unavailable")
    value = _json(result["stdout"], "completeness result")
    if not isinstance(value, dict) or value.get("schema_version") != COMPLETENESS_SCHEMA_VERSION or not isinstance(value.get("records"), list):
        raise M31ScorecardInputError("completeness result schema is unsupported")
    return value


def parse_lifecycle(raw: bytes | str) -> list[dict[str, Any]]:
    wrapper = _json(raw, "lifecycle wrapper")
    if not isinstance(wrapper, dict) or wrapper.get("operation") != "forex_m20_lifecycle_summary":
        raise M31ScorecardInputError("lifecycle operation binding is invalid")
    result = wrapper.get("result")
    if not isinstance(result, dict) or not result.get("ok") or not isinstance(result.get("stdout"), str):
        raise M31ScorecardInputError("lifecycle result is unavailable")
    value = _json(result["stdout"], "lifecycle result")
    if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):
        raise M31ScorecardInputError("lifecycle rows are invalid")
    return value


def build_scorecard(*, protocol: dict[str, Any], completeness: dict[str, Any], lifecycle: list[dict[str, Any]]) -> dict[str, Any]:
    """Create a deterministic scorecard from already-parsed immutable inputs."""
    protocol = parse_protocol(json.dumps(protocol, sort_keys=True, allow_nan=False))
    start = _instant(protocol["interval"]["from_utc"], "interval from_utc")
    end = _instant(protocol["interval"]["to_utc"], "interval to_utc")
    interval = completeness.get("interval")
    if not isinstance(interval, dict) or interval.get("from_utc") != protocol["interval"]["from_utc"] or interval.get("to_utc") != protocol["interval"]["to_utc"] or interval.get("bounds") != "inclusive/exclusive":
        raise M31ScorecardInputError("completeness interval does not match protocol")
    records = completeness.get("records")
    if not isinstance(records, list):
        raise M31ScorecardInputError("completeness records are invalid")
    proposal_ids: set[str] = set()
    actions: Counter[str] = Counter()
    decision_versions: set[tuple[str, str]] = set()
    missing_decision_versions = False
    refusal_reasons: Counter[str] = Counter()
    selected: list[dict[str, Any]] = []
    for row in records:
        if not isinstance(row, dict) or not isinstance(row.get("proposal_id"), str) or row["proposal_id"] in proposal_ids:
            raise M31ScorecardInputError("duplicate or invalid proposal identity")
        decision_at = _instant(row.get("decision_at_utc"), "proposal decision_at_utc")
        if not start <= decision_at < end:
            raise M31ScorecardInputError("proposal lies outside frozen interval")
        action = row.get("action")
        if action not in {"NO_TRADE", "BUY", "SELL"}:
            raise M31ScorecardInputError("proposal action is invalid")
        proposal_ids.add(row["proposal_id"])
        actions[action] += 1
        revision, fingerprint = row.get("application_revision"), row.get("configuration_fingerprint")
        if isinstance(revision, str) and revision and isinstance(fingerprint, str) and fingerprint:
            decision_versions.add((revision, fingerprint))
        else:
            missing_decision_versions = True
        if action == "NO_TRADE" and isinstance(row.get("rationale"), str) and row["rationale"]:
            refusal_reasons[row["rationale"]] += 1
        if action != "NO_TRADE":
            selected.append(row)

    lifecycle_by_proposal: dict[str, dict[str, Any]] = {}
    revisions: set[tuple[Any, Any]] = set()
    for row in lifecycle:
        proposal_id = row.get("proposal_id")
        if not isinstance(proposal_id, str):
            raise M31ScorecardInputError("lifecycle proposal identity is invalid")
        decision_at = _instant(row.get("decision_at_utc"), "lifecycle decision_at_utc")
        if not start <= decision_at < end:
            continue
        if proposal_id in lifecycle_by_proposal:
            raise M31ScorecardInputError("duplicate lifecycle proposal identity")
        if proposal_id not in proposal_ids:
            raise M31ScorecardInputError("lifecycle proposal is absent from completeness input")
        if row.get("action") not in {"BUY", "SELL"}:
            raise M31ScorecardInputError("lifecycle action is invalid")
        revisions.add((row.get("application_revision"), row.get("configuration_fingerprint")))
        closed_at = row.get("closed_at_utc")
        if closed_at is not None and not start <= _instant(closed_at, "outcome closed_at_utc") < end:
            raise M31ScorecardInputError("outcome lies outside frozen interval")
        lifecycle_by_proposal[proposal_id] = row
    revisions.update(decision_versions)
    if len(revisions) > 1:
        raise M31ScorecardInputError("source version drift within frozen interval")

    joined: list[dict[str, Any]] = []
    cost_coverage: Counter[str] = Counter()
    limitations: list[str] = []
    for row in selected:
        lifecycle_row = lifecycle_by_proposal.get(row["proposal_id"])
        if lifecycle_row is None:
            limitations.append("SELECTED_PROPOSAL_WITHOUT_LIFECYCLE:" + row["proposal_id"])
            continue
        costs = {field: _number_or_unknown(lifecycle_row.get(field), field) for field in ("commission_account", "fee_account", "swap_account", "estimated_spread_cost_account", "slippage_cost_account")}
        cost_coverage.update(costs.values())
        joined.append({"proposal_id": row["proposal_id"], "action": row["action"],
                       "strategy_id": lifecycle_row.get("trade_owner_strategy_id") or lifecycle_row.get("selected_strategy_id") or "UNKNOWN",
                       "attempt_status": lifecycle_row.get("status", "UNKNOWN"),
                       "reconciliation_status": lifecycle_row.get("reconciliation_status", "UNKNOWN"),
                       "realized_pnl_aud": lifecycle_row.get("realized_pnl_account"), "cost_coverage": costs})
    if len(lifecycle_by_proposal) != len(selected):
        limitations.append("INCOMPLETE_SELECTED_LIFECYCLE_COVERAGE")
    reconciled = [row for row in joined if row["reconciliation_status"] == "MATCHED" and isinstance(row["realized_pnl_aud"], (int, float))]
    provenance = {"completeness_query_sha256": completeness.get("query_sha256"), "application_revision": next(iter(revisions))[0] if revisions else "UNKNOWN", "configuration_fingerprint": next(iter(revisions))[1] if revisions else "UNKNOWN"}
    # These inputs cannot establish a complete evaluation, even when their
    # joins happen to be empty. Never render missing evidence as 'no limits'.
    limitations.append("HISTORICAL_COMPARISON_UNQUALIFIED")
    if not reconciled:
        limitations.append("NO_RECONCILED_TRADE_OUTCOMES_IN_INTERVAL")
    if missing_decision_versions or any(not provenance[key] or provenance[key] == "UNKNOWN"
           for key in ("application_revision", "configuration_fingerprint")):
        limitations.append("DECISION_VERSION_PROVENANCE_UNAVAILABLE")
    if sum(refusal_reasons.values()) < actions["NO_TRADE"]:
        limitations.append("NO_TRADE_REASONS_NOT_EXPORTED")
    return {"schema_version": SCHEMA_VERSION, "interval": protocol["interval"], "baseline": protocol["baseline"],
            "counts": {"decisions": len(records), "no_trade": actions["NO_TRADE"], "buy": actions["BUY"], "sell": actions["SELL"], "selected": len(selected), "joined_selected": len(joined), "reconciled_closed": len(reconciled)},
            "outcomes": joined, "realized_pnl_aud": round(sum(float(row["realized_pnl_aud"]) for row in reconciled), 2),
            "cost_field_coverage": dict(sorted(cost_coverage.items())), "provenance": provenance,
            "no_trade_reasons": dict(sorted(refusal_reasons.items())),
            "limitations": sorted(set(limitations)), "historical_comparator": "NON_COMPARABLE_CONTEXT", "execution_authority": False}


def render_terminal(scorecard: dict[str, Any]) -> str:
    """Render the same deterministic result in a concise terminal form."""
    if not isinstance(scorecard, dict) or scorecard.get("schema_version") != SCHEMA_VERSION:
        raise M31ScorecardInputError("scorecard schema is unsupported")
    counts = scorecard["counts"]
    interval = scorecard["interval"]
    lines = ["M31 DEMO SCORECARD", f"Window: {interval['from_utc']} to {interval['to_utc']} UTC", "Baseline: NO_CHANGE (0 trades, AUD 0.00)",
             f"Decisions: {counts['decisions']} | no trade: {counts['no_trade']} | selected: {counts['selected']} (buy {counts['buy']}, sell {counts['sell']})",
             f"Outcomes: {counts['reconciled_closed']} reconciled | realized: AUD {scorecard['realized_pnl_aud']:.2f}",
             f"Costs: {json.dumps(scorecard['cost_field_coverage'], sort_keys=True)}",
             f"Limits: {', '.join(scorecard['limitations']) if scorecard['limitations'] else 'none'}",
             f"Historical comparator: {scorecard['historical_comparator']}",
             "Evaluation incomplete: formal M31 acceptance remains unproven.",
             "Execution authority: false"]
    return "\n".join(lines)


def scorecard_from_raw(*, protocol_raw: bytes, completeness_raw: bytes, lifecycle_raw: bytes) -> dict[str, Any]:
    protocol = parse_protocol(protocol_raw)
    completeness = parse_completeness(completeness_raw)
    lifecycle = parse_lifecycle(lifecycle_raw)
    scorecard = build_scorecard(protocol=protocol, completeness=completeness, lifecycle=lifecycle)
    scorecard["input_sha256"] = {"protocol": "sha256:" + hashlib.sha256(protocol_raw).hexdigest(), "completeness": "sha256:" + hashlib.sha256(completeness_raw).hexdigest(), "lifecycle": "sha256:" + hashlib.sha256(lifecycle_raw).hexdigest()}
    return scorecard
