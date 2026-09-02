#!/usr/bin/env python3
"""Fixed T480 M20 historical Ollama comparison; no caller inputs or orders."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from forex.agent_context import build_context
from forex.ollama_evaluation import EXPERIMENT_SESSIONS, evaluate
from forex.ollama_sentiment import build_request, sha256, validate_response

MODEL = "qwen2.5:3b"
LAB_ROOT = "/home/chris/projects/cs-ai-lab-infra"
SNAPSHOT_ID = "m2-m1-eurusd-h1-720"


def compose(service: str, *args: str, input_text: str | None = None, timeout_seconds: int = 180) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            ["docker", "compose", "exec", "-T", service, *args], input=input_text,
            text=True, capture_output=True, check=False, cwd=LAB_ROOT, timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"fixed M20 {service} operation timed out after {timeout_seconds} seconds") from exc
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or "no command output"
        raise RuntimeError(f"fixed M20 {service} operation failed: {detail}")
    return result


def rows() -> list[dict[str, str]]:
    sql = (
        "SELECT time_utc::text, available_at_utc::text, open, high, low, close, volume "
        f"FROM forex.price_bar WHERE snapshot_id='{SNAPSHOT_ID}' "
        "ORDER BY time_utc;"
    )
    values = compose("postgres", "psql", "-At", "-F", "|", "-U", os.environ["POSTGRES_USER"], "-d", os.environ["POSTGRES_DB"], "-c", sql).stdout.splitlines()
    keys = ("time_utc", "available_at_utc", "open", "high", "low", "close", "volume")
    return [dict(zip(keys, value.split("|"))) for value in values if value]


def select_sessions(bars: list[dict[str, str]]) -> list[tuple[int, int]]:
    by_day: dict[str, dict[str, int]] = {}
    for index, bar in enumerate(bars):
        by_day.setdefault(bar["time_utc"][:10], {})[bar["time_utc"][11:13]] = index
    selected: list[tuple[int, int]] = []
    for day in sorted(by_day):
        slots = by_day[day]
        if "08" in slots and "20" in slots and slots["08"] >= 11:
            selected.append((slots["08"], slots["20"]))
        if len(selected) == EXPERIMENT_SESSIONS:
            break
    if len(selected) != EXPERIMENT_SESSIONS:
        raise RuntimeError("retained snapshot lacks the three declared M20 sessions")
    return selected


def retrospective_close(value: str) -> str:
    """M20 uses M16's declared retrospective H1-bar-close availability policy."""
    return (datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc) + timedelta(hours=1)).isoformat().replace("+00:00", "Z")


def main() -> int:
    bars = rows()
    if len(bars) != 720:
        raise RuntimeError("M20 requires the fixed 720-bar retained Demo-only snapshot")
    model_line = next((line.strip() for line in compose("ollama", "ollama", "list").stdout.splitlines() if line.startswith(f"{MODEL} ")), "")
    if not model_line:
        raise RuntimeError(f"approved local model is unavailable: {MODEL}")
    # A fixed harmless warm-up keeps the already-approved local model resident
    # before the three bounded historical requests; no output is retained.
    compose("ollama", "ollama", "run", MODEL, "Reply READY only.")
    experiments = []
    for entry_index, exit_index in select_sessions(bars):
        context_bars = [{**bar, "available_at_utc": retrospective_close(bar["time_utc"])} for bar in bars[entry_index - 11:entry_index + 1]]
        context = build_context(
            bars=context_bars, cutoff_utc=context_bars[-1]["available_at_utc"],
            features={"source": "DEMO_ONLY_HISTORICAL", "licensing": "UNQUALIFIED_BROKER_TERMINAL_DATA"},
        )
        request = build_request(context)
        try:
            raw = compose("ollama", "ollama", "run", MODEL, "--format", json.dumps(request["response_schema"], separators=(",", ":")), input_text=request["prompt"]).stdout.strip()
            raw_value = json.loads(raw)
            response = validate_response(raw_value)
            model_response_valid = True
        except (RuntimeError, ValueError, json.JSONDecodeError) as exc:
            raw_value = {"m20_rejected_or_timed_out": str(exc)}
            response = {"sentiment": "ABSTAIN", "confidence": 0, "rationale": "Model response did not satisfy the fixed response schema.", "abstain": True, "research_only": True, "order_capability": False}
            model_response_valid = False
        price_only_action = "BUY" if float(context_bars[-1]["close"]) >= float(context_bars[-3]["close"]) else "SELL"
        experiments.append({
            "decision_at_utc": context_bars[-1]["available_at_utc"], "entry_at_utc": bars[entry_index]["time_utc"],
            "exit_at_utc": bars[exit_index]["time_utc"], "entry_close": bars[entry_index]["close"],
            "exit_close": bars[exit_index]["close"], "context_bar_count": len(context_bars),
            "model_output_sha256": sha256(raw_value), "model_response_valid": model_response_valid,
            "response": response, "price_only_action": price_only_action,
        })
    evaluation = evaluate(experiments)
    print(json.dumps({
        "marker": "FOREX_M20_OLLAMA_EVALUATION_PROBE_OK", "snapshot": SNAPSHOT_ID,
        "source": "DEMO_ONLY_HISTORICAL", "model_definition_sha256": sha256(model_line),
        "evaluation": evaluation, "order_capability": False, "live_trading_capability": False,
    }, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
