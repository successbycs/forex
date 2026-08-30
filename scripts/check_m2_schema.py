#!/usr/bin/env python3
"""Static safety validation for the M2 PostgreSQL migration.

This is intentionally not a claim that PostgreSQL is installed or that the
migration has run. It protects the versioned migration contract when a local
PostgreSQL service is unavailable; M5 owns real application/database proof.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys


REQUIRED_SNIPPETS = (
    "CREATE SCHEMA IF NOT EXISTS forex",
    "CREATE TABLE forex.source_registry",
    "CREATE TABLE forex.raw_observation",
    "CREATE TABLE forex.dataset_snapshot",
    "CREATE TABLE forex.dataset_snapshot_observation",
    "CREATE TABLE forex.price_bar",
    "REFERENCES forex.source_registry(source_id)",
    "REFERENCES forex.raw_observation(observation_id)",
    "payload_sha256 ~ '^sha256:[0-9a-f]{64}$'",
    "CHECK (no_lookahead)",
    "CREATE INDEX price_bar_snapshot_available_idx",
    "dataset snapshots are immutable once sealed",
    "price bar availability exceeds snapshot decision cutoff",
    "raw observation availability exceeds snapshot decision cutoff",
    "CREATE TRIGGER dataset_snapshot_immutable",
    "CREATE TRIGGER dataset_snapshot_observation_immutable",
    "CREATE TRIGGER price_bar_immutable",
    "CREATE TRIGGER price_bar_point_in_time",
    "CREATE TRIGGER snapshot_observation_point_in_time",
    "CREATE TRIGGER raw_observation_sealed_provenance_immutable",
    "CREATE TRIGGER source_registry_sealed_provenance_immutable",
    "sealed snapshot provenance is immutable",
)
FORBIDDEN_PATTERNS = (r"GOMarketsMU-Live", r"order_send", r"COPY\s+FROM\s+PROGRAM", r"dblink", r"http")


def validate(paths: tuple[Path, ...]) -> list[str]:
    sql = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    failures = [f"missing required migration statement: {snippet}" for snippet in REQUIRED_SNIPPETS if snippet not in sql]
    failures.extend(f"forbidden capability in migration: {pattern}" for pattern in FORBIDDEN_PATTERNS if re.search(pattern, sql, re.IGNORECASE))
    if not sql.lstrip().startswith("--") or "BEGIN;" not in sql or not sql.rstrip().endswith("COMMIT;"):
        failures.append("migration must be a single explicit BEGIN/COMMIT transaction")
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Statically validate the M2 PostgreSQL migration")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    failures = validate((
        args.root / "sql" / "migrations" / "001_m2_historical_data.sql",
        args.root / "sql" / "migrations" / "002_m2_sealed_provenance.sql",
    ))
    if failures:
        print("M2 PostgreSQL migration invalid:\n- " + "\n- ".join(failures), file=sys.stderr)
        return 2
    print("FOREX_M2_POSTGRES_SCHEMA_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
