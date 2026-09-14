#!/usr/bin/env python3
"""Evaluate retained H_SLOW order-sizing inputs without submitting an order."""
import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _constant(value):
    raise ValueError(f"nonfinite JSON constant: {value}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    args = parser.parse_args()
    try:
        from forex.h_slow_order_preparation import prepare_h_slow_order
        payload = json.loads(args.input.read_bytes(), object_pairs_hook=_unique,
                             parse_constant=_constant)
        required = {"lifecycle_plan", "market_inputs", "limits"}
        if (not isinstance(payload, dict) or not required <= set(payload)
                or set(payload) - required - {"protection_snapshot", "research_decision", "event_eligibility", "primary_context", "edge_sizing_result"}):
            raise ValueError("input requires lifecycle_plan, market_inputs, limits and optional protection_snapshot/research_decision/event_eligibility/primary_context/edge_sizing_result")
        protection = None
        if "protection_snapshot" in payload:
            from forex.h_slow_decision import attach_event_context, evaluate_h_slow_snapshot
            from forex.h_slow_protection import derive_h_slow_stop
            snapshot = payload["protection_snapshot"]
            if not isinstance(snapshot, dict):
                raise ValueError("protection_snapshot must be a dataset snapshot")
            cutoff = snapshot.get("decision_cutoff_utc")
            decision = evaluate_h_slow_snapshot(snapshot, decision_at_utc=cutoff)
            if "research_decision" in payload:
                supplied = payload["research_decision"]
                if not isinstance(supplied, dict):
                    raise ValueError("research_decision must be a retained decision record")
                if supplied.get("event_annotation_status") == "ATTACHED_CONTEXT_ONLY":
                    decision = attach_event_context(decision, supplied.get("event_annotation"))
                if supplied != decision:
                    raise ValueError("research_decision does not reproduce from the protection snapshot")
            plan = payload["lifecycle_plan"]
            if not isinstance(plan, dict) or plan.get("decision_sha256") != decision["decision_sha256"]:
                raise ValueError("protection snapshot must reproduce the lifecycle research decision")
            market = payload["market_inputs"]
            if not isinstance(market, dict) or "technical_stop_price" in market:
                raise ValueError("derived protection requires market inputs without technical_stop_price")
            direction = decision["target"]["action"]
            if direction not in {"BUY", "SELL"}:
                raise ValueError("derived protection requires a directional research target")
            if (plan.get("next_action") != "OPEN" or not isinstance(plan.get("intent"), dict)
                    or plan["intent"].get("direction") != direction):
                raise ValueError("derived protection requires a matching OPEN direction")
            def utc(value):
                if not isinstance(value, str):
                    raise ValueError("protection clocks must be timestamps")
                stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
                if stamp.tzinfo is None:
                    raise ValueError("protection clocks require offsets")
                return stamp.astimezone(UTC)
            decided = utc(cutoff)
            observed = utc(market.get("observed_at_utc"))
            evaluated = utc(market.get("evaluated_at_utc"))
            if decided > observed or (decided.year, decided.month) != (evaluated.year, evaluated.month):
                raise ValueError("protection decision must precede quote and remain in the evaluation month")
            rule = json.loads((ROOT / "config/h_slow_protection.json").read_bytes(),
                              object_pairs_hook=_unique, parse_constant=_constant)
            protection = derive_h_slow_stop(snapshot, decision_at_utc=cutoff,
                direction=direction, entry_price=market.get("ask" if direction == "BUY" else "bid"), rule=rule)
            payload["market_inputs"] = {**market, "technical_stop_price": protection["technical_stop_price"]}
        result = prepare_h_slow_order(payload["lifecycle_plan"],
            market_inputs=payload["market_inputs"], limits=payload["limits"],
            event_eligibility=payload.get("event_eligibility"), research_decision=payload.get("research_decision"),
            primary_context=payload.get("primary_context"), edge_sizing_result=payload.get("edge_sizing_result"))
        if protection is not None:
            result["derived_protection"] = protection
        print(json.dumps(result, sort_keys=True, allow_nan=False))
    except (OSError, ValueError, TypeError, OverflowError) as exc:
        print(f"H_SLOW preparation refused: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
