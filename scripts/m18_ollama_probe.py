#!/usr/bin/env python3
"""Fixed T480 M18 drill: bounded historical context -> Ollama -> strict JSON.

The script has no caller arguments.  It reads a fixed retained Demo-only
historical slice and invokes exactly the approved local Ollama model.  It does
not access MT5, accounts, credentials, live data, or an order surface.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from forex.agent_context import build_context
from forex.ollama_sentiment import build_request, sha256, validate_response

MODEL = "qwen2.5:3b"
LAB_COMPOSE = "/home/chris/projects/cs-ai-lab-infra/compose.yaml"


def compose(*args: str, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "compose", "-f", LAB_COMPOSE, "exec", "-T", "ollama", *args],
        input=input_text, text=True, capture_output=True, check=True,
    )


def main() -> int:
    db_command = [
        "docker", "compose", "-f", LAB_COMPOSE, "exec", "-T", "postgres", "psql", "-At", "-F", "|",
        "-U", os.environ["POSTGRES_USER"], "-d", os.environ["POSTGRES_DB"], "-c",
        "SELECT time_utc::text, available_at_utc::text, open, high, low, close, volume "
        "FROM forex.price_bar WHERE snapshot_id='m2-m1-eurusd-h1-720' ORDER BY time_utc LIMIT 12;",
    ]
    rows = subprocess.run(db_command, text=True, capture_output=True, check=True).stdout.splitlines()
    bars = [dict(zip(("time_utc", "available_at_utc", "open", "high", "low", "close", "volume"), row.split("|"))) for row in rows if row]
    if not bars:
        raise RuntimeError("no retained historical bars are available for M18")
    context = build_context(
        bars=bars,
        cutoff_utc=bars[-1]["available_at_utc"],
        features={"source": "DEMO_ONLY_HISTORICAL", "licensing": "UNQUALIFIED_BROKER_TERMINAL_DATA"},
    )
    request = build_request(context)
    installed_models = compose("list").stdout.splitlines()
    model_info = next((line.strip() for line in installed_models if line.startswith(f"{MODEL} ")), "")
    if not model_info:
        raise RuntimeError(f"approved local model is unavailable: {MODEL}")
    raw = compose("run", MODEL, "--format", json.dumps(request["response_schema"], separators=(",", ":")), input_text=request["prompt"]).stdout.strip()
    response = validate_response(json.loads(raw))
    print(json.dumps({
        "marker": "FOREX_M18_OLLAMA_PROBE_OK",
        "model": MODEL,
        "model_definition_sha256": sha256(model_info),
        "prompt_template_version": request["prompt_template_version"],
        "input_context_sha256": request["input_context_sha256"],
        "output_sha256": sha256(json.loads(raw)),
        "response": response,
        "bars": len(context["price_bars"]),
        "source": "DEMO_ONLY_HISTORICAL",
        "order_capability": False,
        "live_trading_capability": False,
    }, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
