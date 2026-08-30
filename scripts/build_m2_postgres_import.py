#!/usr/bin/env python3
"""Build fixed SQL for the one allowed M2 initial snapshot import.

The program has no network, database, shell, or user-supplied path surface.
It consumes the retained M1 evidence at its fixed repository location and
writes SQL to stdout for the local PostgreSQL command in import_m2_postgres.sh.
"""

from __future__ import annotations

import base64
from datetime import datetime, timedelta
import gzip
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from forex.data_contracts import build_dataset_snapshot


M1_CAPTURE = Path("runs/evidence/M1/20260829T064204Z/capture.stdout.json")
SNAPSHOT_ID = "m2-m1-eurusd-h1-720"
OBSERVATION_ID = "m1-demo-eurusd-h1-720"
SOURCE_ID = "gomarketsmu-demo-m1"


def quote(value: object) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def snapshot_from_retained_m1(root: Path) -> dict:
    envelope = json.loads((root / M1_CAPTURE).read_text(encoding="utf-8"))
    execution = envelope["result"]
    result = json.loads(execution["stdout"])
    bars = json.loads(gzip.decompress(base64.b64decode(result["bars_payload"])))
    source = {"contract_version": "forex.historical-data.v1", "source_id": SOURCE_ID, "owner": "GO Markets Mauritius", "license": "UNQUALIFIED_BROKER_TERMINAL_DATA", "cost_model": "account-access", "api_version": "MT5-terminal", "endpoint_allowlist": [], "rate_limit": "terminal-governed", "retention_rule": "retain-redacted-metadata-and-hashes", "historical_depth": "terminal-dependent", "revision_support": "not-provided", "timezone_policy": "UTC-normalised", "outage_policy": "record-missing-observation", "approval_status": "DEMO_ONLY", "secrets_reference": "NONE", "provenance_note": "Retained M1 fixed Demo-only historical observation; not externally source-qualified."}
    available = execution["finished_at"].replace("+00:00", "Z")
    observation = {"contract_version": "forex.historical-data.v1", "observation_id": OBSERVATION_ID, "source_id": SOURCE_ID, "source_revision": "M1-720-bars:" + result["bars_sha256"][:16], "observed_at_utc": available, "available_at_utc": available, "retrieved_at_utc": available, "timezone": "UTC", "payload_sha256": "sha256:" + result["bars_sha256"], "payload_path": str(M1_CAPTURE), "redacted": True}
    price_bars = []
    for bar in bars:
        end = (datetime.fromisoformat(bar["time_utc"].replace("Z", "+00:00")) + timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        price_bars.append({**bar, "raw_observation_id": OBSERVATION_ID, "available_at_utc": available if available >= end else end})
    return build_dataset_snapshot(snapshot_id=SNAPSHOT_ID, instrument="EUR/USD", timeframe="H1", decision_cutoff_utc=available, created_at_utc=available, source_registry=[source], raw_observations=[observation], price_bars=price_bars)


def build_sql(snapshot: dict) -> str:
    source, observation = snapshot["source_registry"][0], snapshot["raw_observations"][0]
    lines = ["BEGIN;", "SET TIME ZONE 'UTC';"]
    lines.append("INSERT INTO forex.source_registry (source_id, contract_version, owner, license, cost_model, api_version, endpoint_allowlist, rate_limit, retention_rule, historical_depth, revision_support, timezone_policy, outage_policy, approval_status, secrets_reference, provenance_note) VALUES (" + ", ".join([quote(source[k]) if k != "endpoint_allowlist" else quote(json.dumps(source[k])) + "::jsonb" for k in ("source_id", "contract_version", "owner", "license", "cost_model", "api_version", "endpoint_allowlist", "rate_limit", "retention_rule", "historical_depth", "revision_support", "timezone_policy", "outage_policy", "approval_status", "secrets_reference", "provenance_note")]) + ") ON CONFLICT (source_id) DO NOTHING;")
    lines.append("INSERT INTO forex.raw_observation (observation_id, contract_version, source_id, source_revision, observed_at_utc, available_at_utc, retrieved_at_utc, timezone, payload_sha256, payload_path, redacted) VALUES (" + ", ".join(quote(observation[k]) if k != "redacted" else str(observation[k]).lower() for k in ("observation_id", "contract_version", "source_id", "source_revision", "observed_at_utc", "available_at_utc", "retrieved_at_utc", "timezone", "payload_sha256", "payload_path", "redacted")) + ") ON CONFLICT (observation_id) DO NOTHING;")
    lines.append("INSERT INTO forex.dataset_snapshot (snapshot_id, contract_version, instrument, timeframe, decision_cutoff_utc, created_at_utc, artifact_sha256, no_lookahead) VALUES (" + ", ".join(quote(snapshot[k]) if k != "no_lookahead" else str(snapshot[k]).lower() for k in ("snapshot_id", "contract_version", "instrument", "timeframe", "decision_cutoff_utc", "created_at_utc", "artifact_sha256", "no_lookahead")) + ");")
    lines.append(f"INSERT INTO forex.dataset_snapshot_observation (snapshot_id, observation_id) VALUES ({quote(SNAPSHOT_ID)}, {quote(OBSERVATION_ID)});")
    for bar in snapshot["price_bars"]:
        values = [quote(SNAPSHOT_ID)] + [
            quote(bar[key]) if key in {"time_utc", "raw_observation_id", "available_at_utc"} else str(bar[key])
            for key in ("time_utc", "open", "high", "low", "close", "volume", "raw_observation_id", "available_at_utc")
        ]
        lines.append(
            "INSERT INTO forex.price_bar (snapshot_id, time_utc, open, high, low, close, volume, raw_observation_id, available_at_utc) VALUES ("
            + ", ".join(values)
            + ");"
        )
    lines.extend(["COMMIT;", "SELECT 'FOREX_M2_POSTGRES_IMPORT_OK' AS marker;"])
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    print(build_sql(snapshot_from_retained_m1(Path.cwd())), end="")
