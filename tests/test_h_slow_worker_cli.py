from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from tests.test_h_slow_lifecycle import decision, observation, registry


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "h_slow_worker.py"


def payload() -> dict:
    return {
        "research_decision": decision(),
        "envelope": {
            "schema_version": "forex.h-slow.timed-observation.v1",
            "observed_at_utc": "2026-09-01T12:00:00Z",
            "received_at_utc": "2026-09-01T12:00:01Z",
            "observation": observation(),
        },
        "stream_registry": registry(),
        "evaluated_at_utc": "2026-09-01T12:00:01Z",
        "maximum_observation_age_seconds": 30,
    }


def test_cli_refuses_without_an_explicit_local_dsn_and_preserves_input(tmp_path):
    path = tmp_path / "worker.json"
    raw = json.dumps(payload()).encode()
    path.write_bytes(raw)
    environment = {key: value for key, value in __import__("os").environ.items() if key != "FOREX_H_SLOW_DSN"}
    result = subprocess.run([sys.executable, str(SCRIPT), str(path)], cwd=tmp_path,
                            env=environment, capture_output=True, text=True)
    assert result.returncode == 2
    assert not result.stdout
    assert "DSN environment variable is unset" in result.stderr
    assert path.read_bytes() == raw


def test_cli_refuses_unsafe_environment_name_before_any_database_import(tmp_path):
    path = tmp_path / "worker.json"
    path.write_text(json.dumps(payload()))
    result = subprocess.run([sys.executable, str(SCRIPT), str(path), "--dsn-env", "PATH"], cwd=tmp_path,
                            capture_output=True, text=True)
    assert result.returncode == 2
    assert not result.stdout
    assert "environment variable name is not permitted" in result.stderr


def test_command_has_no_order_or_broker_surface():
    source = SCRIPT.read_text(encoding="utf-8")
    for forbidden in ("t480_adapter", "order_send", "MetaTrader", "claim_intent", "mark_submission_unknown"):
        assert forbidden not in source
