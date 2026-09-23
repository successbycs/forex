"""Read-only re-evaluation of an unchanged M31 NO_TRADE observation.

Supplemental provenance is joined to original decisions, never substituted for
them. This report is not the registry proof marker or a closeout approval.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from forex.m31_scorecard import (
    M31ScorecardInputError, _instant, _json, parse_completeness,
    parse_lifecycle, parse_protocol, scorecard_from_raw,
)
from forex.m20_history_report import build_history_report
from forex.m31_evidence import REQUIRED


def require(condition: bool, message: str) -> None:
    if not condition:
        raise M31ScorecardInputError(message)


def successful(raw: bytes, operation: str) -> dict[str, Any]:
    value = _json(raw, operation)
    require(isinstance(value, dict), "source envelope must be an object")
    result = value.get("result")
    require(value.get("operation") == operation and value.get("ok") is True
            and isinstance(result, dict) and result.get("ok") is True
            and result.get("exit_code") == 0 and isinstance(result.get("stdout"), str),
            "source operation did not succeed")
    return _json(result["stdout"], operation)


def verify_original_hashes(bundle: Path) -> dict[str, bytes]:
    """Verify the original v1 manifest without re-evaluating its old scorecard."""
    require(not bundle.is_symlink() and bundle.is_dir(), "original bundle is not a regular directory")
    raw = {}
    require({p.name for p in bundle.iterdir()} == REQUIRED, "original artifact set differs")
    for name in REQUIRED:
        path = bundle / name
        require(not path.is_symlink() and path.is_file(), "original artifact is not a regular file")
        raw[name] = path.read_bytes()
    manifest = _json(raw["manifest.json"], "original manifest")
    require(isinstance(manifest, dict) and manifest.get("schema_version") == "forex.m31.evidence-bundle.v1"
            and manifest.get("milestone_id") == "M31"
            and manifest.get("observed_result") == "FOREX_M31_EVIDENCE_CAPTURED",
            "original manifest binding differs")
    items = manifest.get("artifacts")
    require(isinstance(items, list) and all(isinstance(i, dict) for i in items), "invalid original inventory")
    names = [item.get("path") for item in items]
    require(all(isinstance(n, str) for n in names) and len(names) == len(set(names))
            and set(names) == REQUIRED - {"manifest.json"}, "invalid original inventory")
    for item in items:
        require(item.get("sha256") == "sha256:" + hashlib.sha256(raw[item["path"]]).hexdigest(),
                "original artifact digest mismatch")
    receipt = _json(raw["protocol-receipt.json"], "original receipt")
    require(manifest.get("git_revision") == receipt.get("git_revision") == raw["revision.txt"].decode().strip(),
            "original revision bindings differ")
    protocol = parse_protocol(raw["protocol.json"])
    require(_instant(manifest.get("captured_at_utc"), "original capture") >=
            _instant(protocol["interval"]["to_utc"], "interval end"), "original capture preceded interval end")
    return raw


def evaluate_no_trade_supplement(*, protocol_raw: bytes, receipt_raw: bytes,
                               original_raw: bytes, enriched_raw: bytes,
                               lifecycle_raw: bytes, broker_raw: bytes,
                               historical_raw: bytes) -> dict[str, Any]:
    """Evaluate the refusal-only case; do not infer costs for traded intervals."""
    protocol = parse_protocol(protocol_raw)
    start = _instant(protocol["interval"]["from_utc"], "start")
    end = _instant(protocol["interval"]["to_utc"], "end")
    receipt = _json(receipt_raw, "receipt")
    require(isinstance(receipt, dict), "receipt must be an object")
    require(receipt.get("schema_version") == "forex.m31.protocol-receipt.v1"
            and receipt.get("execution_authority") is False
            and receipt.get("protocol_sha256") == "sha256:" + hashlib.sha256(protocol_raw).hexdigest()
            and re.fullmatch(r"[0-9a-f]{40}", str(receipt.get("git_revision"))) is not None,
            "declaration receipt binding is invalid")
    require(receipt.get("declared_at_utc") == protocol["captured_at_utc"]
            and _instant(receipt["declared_at_utc"], "declared") < start,
            "protocol was not declared before observation")
    successful(original_raw, "forex_m1_postgres_completeness_summary")
    successful(enriched_raw, "forex_m1_postgres_completeness_summary")
    successful(lifecycle_raw, "forex_m20_lifecycle_summary")
    original = parse_completeness(original_raw)
    enriched = parse_completeness(enriched_raw)
    # Parse both through the same evaluator to detect duplicate keys, bad bounds
    # and source-version drift before constructing the provenance join.
    scorecard_from_raw(protocol_raw=protocol_raw, completeness_raw=original_raw,
                       lifecycle_raw=lifecycle_raw)
    scorecard = scorecard_from_raw(protocol_raw=protocol_raw, completeness_raw=enriched_raw,
                                   lifecycle_raw=lifecycle_raw)
    indexed = {row["proposal_id"]: row for row in enriched["records"]}
    strategies = set()
    require(len(original["records"]) == len(indexed) > 0, "supplement decision set differs")
    for row in original["records"]:
        extra = indexed.get(row["proposal_id"], {})
        require(all(key in extra and extra[key] == value for key, value in row.items()),
                "supplement changed an original decision field")
        require(extra.get("action") == "NO_TRADE" and extra.get("attempt_id") is None,
                "supplement requires refusal-only decisions with no attempts")
        require(extra.get("selected_timeframe") == "M1" and extra.get("server") == "GOMarketsMU-Demo"
                and extra.get("instrument") == "EURUSD" and isinstance(extra.get("session_id"), str)
                and bool(extra["session_id"]), "decision scope is not Demo EURUSD M1")
        require(isinstance(extra.get("strategy_version"), str) and bool(extra["strategy_version"]),
                "strategy version is missing")
        strategies.add(extra["strategy_version"])
        require(re.fullmatch(r"[0-9a-f]{40}", str(extra.get("application_revision"))) is not None
                and re.fullmatch(r"sha256:[0-9a-f]{64}", str(extra.get("configuration_fingerprint"))) is not None
                and bool(extra.get("rationale")), "decision provenance or rationale is missing")
    require(len(strategies) == 1, "strategy version drift")
    scorecard["provenance"]["strategy_version"] = next(iter(strategies))
    require(not any(start <= _instant(row["decision_at_utc"], "lifecycle decision") < end
                    for row in parse_lifecycle(lifecycle_raw)), "unexpected lifecycle in refusal window")

    broker = successful(broker_raw, "m20_all_demo_history_export")
    build_history_report(broker_raw)
    require(broker.get("complete") is True and broker.get("ok") is True
            and broker.get("server") == "GOMarketsMU-Demo" and broker.get("currency") == "AUD",
            "broker history must be complete Demo/AUD")
    require(_instant(broker["captured_at_utc"], "broker capture") >= end
            and _instant(broker["from_utc"], "history start") <= start,
            "broker history does not cover observation")
    offset = broker.get("broker_timestamp_offset_seconds")
    require(type(offset) is int and abs(offset) <= 86400, "broker clock offset is invalid")
    require(_instant(broker["query_to_server_clock_utc"], "history end").timestamp() - offset >= end.timestamp(),
            "broker query ends before observation")
    # All EURUSD deals are checked, not just magic-filtered automation; an
    # unexplained deal must not be silently attributed or excluded.
    require(all(type(d.get("time")) is int for d in broker["deals"]), "deal timestamp is invalid")
    interval_deals = [d for d in broker["deals"] if d.get("symbol") == "EURUSD"
                      and start.timestamp() <= d["time"] - offset < end.timestamp()]
    require(not interval_deals, "EURUSD broker activity requires separate attribution")
    history = successful(historical_raw, "forex_m16_walk_forward_probe")
    evaluation = history.get("evaluation", {})
    baseline = evaluation.get("overall", {}).get("no_change", {})
    require(history.get("marker") == "FOREX_M16_WALK_FORWARD_PROBE_OK"
            and evaluation.get("evaluation_version") == "eurusd-walk-forward.v1"
            and evaluation.get("availability_policy") == "RETROSPECTIVE_H1_BAR_CLOSE_ASSUMPTION"
            and baseline.get("sessions", 0) > 0 and baseline.get("actionable_sessions") == 0
            and baseline.get("total_net_return") == 0 and baseline.get("mean_net_return") == 0,
            "historical no-change reference is invalid")
    windows = evaluation.get("windows", [])
    require(bool(windows) and all(_instant(w["last_test_day"] + "T23:59:59Z", "historical end") < start
            and w["no_change"]["actionable_sessions"] == 0
            and w["no_change"]["total_net_return"] == 0 for w in windows),
            "historical windows are not prior no-change observations")
    scorecard["historical_comparator"] = "NO_CHANGE_NO_EXPOSURE_ONLY"
    scorecard["limitations"].remove("HISTORICAL_COMPARISON_UNQUALIFIED")
    scorecard["limitations"].extend([
        "HISTORICAL_ARTIFACT_BOUND_AFTER_OBSERVATION",
        "NO_DIRECT_DECISION_TO_BROKER_ACCOUNT_HASH",
        "NO_ACTIVE_STRATEGY_PERFORMANCE_COMPARISON",
    ])
    return {
        "schema_version": "forex.m31.no-trade-supplement.v1", "scorecard": scorecard,
        "declaration_revision": receipt["git_revision"],
        "historical_reference": {"kind": "NO_CHANGE", "sessions": baseline["sessions"],
            "total_net_return_fraction": baseline["total_net_return"],
            "snapshot": history.get("snapshot"), "evaluation_version": evaluation["evaluation_version"],
            "availability_policy": evaluation["availability_policy"],
            "qualification": "NO_EXPOSURE_BEHAVIOUR_ONLY_NOT_M1_STRATEGY_PERFORMANCE",
            "bound_after_observation": True},
        "comparison": {"automated_entries": 0, "interval_realized_pnl_aud": 0,
            "new_trade_costs_aud": 0, "delta_to_declared_no_change_aud": 0,
            "account_pnl_or_flatness_claim": False, "profitability_claim": False},
        "broker_crosscheck": {"interval_eurusd_deals": 0,
            "captured_at_utc": broker["captured_at_utc"],
            "account_scope_sha256": broker["account_scope_sha256"],
            "decision_account_identity": "NOT_RETAINED_IN_PROPOSAL_SESSION_SCHEMA"},
        "input_sha256": {name: "sha256:" + hashlib.sha256(raw).hexdigest() for name, raw in {
            "protocol": protocol_raw, "receipt": receipt_raw, "original": original_raw,
            "enriched": enriched_raw, "lifecycle": lifecycle_raw, "broker": broker_raw,
            "historical": historical_raw}.items()},
        "formal_m31_proven": False, "execution_authority": False,
    }
