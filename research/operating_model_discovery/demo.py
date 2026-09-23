"""Offline design demonstration. Synthetic calendars; no trading capability."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo


def instant(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Explicit timezone required")
    return result.astimezone(timezone.utc)


def identity(policy):
    return hashlib.sha256(json.dumps(policy, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def evaluate(policy, example):
    now = instant(example["at"])
    digest = identity(policy)
    reasons = []
    state, transition = "UNKNOWN", None
    # A publication is a bounded, fully covered set of dated intervals. There
    # is no implicit closed default outside those intervals or across gaps.
    valid = (instant(policy["known_at"]) <= now
             and instant(policy["valid_from"]) <= now < instant(policy["valid_until"]))
    if example.get("expected_hash", digest) != digest:
        reasons.append("POLICY_MISMATCH")
    elif not valid:
        reasons.append("POLICY_OUTSIDE_COVERAGE")
    elif example.get("calendar_unknown"):
        reasons.append("CALENDAR_UNKNOWN")
    else:
        rows = policy["intervals"]
        matches = [r for r in rows if instant(r["start"]) <= now < instant(r["end"])]
        if len(matches) == 1:
            row = matches[0]
            state = row["state"]
            if state not in {"OPEN", "CLOSED", "BREAK", "HOLIDAY"}:
                state = "UNKNOWN"
                reasons.append("INVALID_SCHEDULE_STATE")
            else:
                reasons.append(row["reason"])
                boundary = min([instant(row["end"])] + [instant(r["start"]) for r in rows if now < instant(r["start"]) < instant(row["end"])])
                following = [r for r in rows if instant(r["start"]) <= boundary < instant(r["end"])]
                if (len(following) == 1 and boundary < instant(policy["valid_until"])
                        and following[0]["state"] in {"OPEN", "CLOSED", "BREAK", "HOLIDAY"}):
                    transition = {"at_utc": boundary.isoformat(), "to": following[0]["state"],
                                  "auckland": boundary.astimezone(ZoneInfo("Pacific/Auckland")).isoformat(),
                                  "broker_original": following[0]["start"]}
        else:
            reasons.append("CALENDAR_GAP_OR_CONFLICT")
    age = example.get("quote_age_seconds")
    fresh = type(age) in (int, float) and math.isfinite(age) and 0 <= age <= policy["maximum_quote_age_seconds"]
    observed = "DISCONNECTED" if example.get("connected") is not True else "FRESH" if fresh else "STALE_OR_UNKNOWN"
    if observed != "FRESH":
        reasons.append("QUOTE_" + observed)
    spread = example.get("spread_points")
    normal = type(spread) in (int, float) and math.isfinite(spread) and 0 <= spread <= policy["maximum_spread_points"]
    if not normal:
        reasons.append("SPREAD_UNSAFE_OR_UNKNOWN")
    eligible = state == "OPEN" and observed == "FRESH" and normal
    position = "NO_POSITION_IN_EXAMPLE"
    if example.get("open_position"):
        position = "CONTINUE_EXISTING_PROTECTION"
        if example.get("exit_due"):
            position = "EXIT_DUE_REQUIRES_BROKER_CONFIRMATION" if example.get("exit_available") else "EXIT_UNRESOLVED_CONTINUE_PROTECTION"
    return {"name": example["name"], "scope": "SYNTHETIC_OFFLINE_ONLY", "policy_version": policy["version"],
            "policy_hash": digest, "at_utc": now.isoformat(), "effective_from": policy["valid_from"],
            "source_references": policy["sources"], "rule_references": policy["rule_references"],
            "enforcement_status": "PROTOTYPE_ONLY", "responsibility": "Operator maintains client; existing executor owns protection",
            "scheduled_state": state, "observed_state": observed,
            "session_entry_eligibility": "CANDIDATE_ONLY" if eligible else "BLOCKED",
            "execution_permission": "NOT_EVALUATED_NO_ORDER_CAPABILITY", "reasons": reasons,
            "next_expected_transition": transition, "position_handling": position,
            "maximum_quote_age_seconds": policy["maximum_quote_age_seconds"],
            "maximum_spread_points": policy["maximum_spread_points"]}


def render_text(result, details=False):
    # Both the short view and optional audit details use this one result.
    transition = result['next_expected_transition']
    next_text = (f"{transition['to']} at {transition['auckland']} Auckland "
                 f"({transition['at_utc']} UTC; broker {transition['broker_original']})") if transition else 'Unknown'
    lines = [f"{result['name']} — SYNTHETIC EXAMPLE",
             f"  Schedule: {result['scheduled_state']} | Feed: {result['observed_state']}",
             f"  Session check: {result['session_entry_eligibility']} | Overall trading permission: not evaluated",
             f"  Why: {', '.join(result['reasons'])}",
             f"  Next expected change: {next_text}",
             f"  Position: {result['position_handling']}",
             f"  Rules: quote age <= {result['maximum_quote_age_seconds']} seconds; spread <= {result['maximum_spread_points']} points",
             f"  Policy: {result['policy_version']} | Prototype only",
             f"  Policy hash: {result['policy_hash']}"]
    if details:
        lines.append('Audit details:')
        lines.extend(f"  {key}: {json.dumps(value, ensure_ascii=False)}" for key, value in result.items())
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--examples", type=Path, required=True)
    parser.add_argument("--format", choices=("json", "text"), required=True)
    parser.add_argument("--details", action="store_true", help="Include full audit fields in text output")
    args = parser.parse_args()
    data = json.loads(args.examples.read_text())
    results = [evaluate(data["policy"], item) for item in data["examples"]]
    print(json.dumps(results, indent=2) if args.format == "json" else "\n\n".join(render_text(r, args.details) for r in results))


if __name__ == "__main__":
    main()
