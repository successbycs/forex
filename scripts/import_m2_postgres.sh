#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
docker compose up -d postgres
until docker compose exec -T postgres pg_isready -U forex -d forex >/dev/null; do sleep 1; done
docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U forex -d forex -f /migrations/001_m2_historical_data.sql
python3 scripts/build_m2_postgres_import.py | docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U forex -d forex
docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U forex -d forex -Atc "SELECT (SELECT count(*) FROM forex.source_registry), (SELECT count(*) FROM forex.raw_observation), (SELECT count(*) FROM forex.dataset_snapshot), (SELECT count(*) FROM forex.price_bar), (SELECT artifact_sha256 FROM forex.dataset_snapshot WHERE snapshot_id = 'm2-m1-eurusd-h1-720');"
