#!/usr/bin/env bash
# Fixed T480-side apply wrapper for the approved calendar-fact schema only.
set -euo pipefail

expected="06b09221ef12bc1758827beaf9973dc374d407524e1f9fe70a77449a98400259"
source="/mnt/c/Users/chris/Documents/Code/forex-calendar-schema/economic_calendar_facts.sql"

for ancestor in /mnt /mnt/c /mnt/c/Users /mnt/c/Users/chris /mnt/c/Users/chris/Documents /mnt/c/Users/chris/Documents/Code /mnt/c/Users/chris/Documents/Code/forex-calendar-schema; do
    [[ -d "$ancestor" && ! -L "$ancestor" ]] || { printf '%s\n' 'FOREX_CALENDAR_FACT_SCHEMA_STAGE_ANCESTOR_INVALID' >&2; exit 1; }
done
[[ -f "$source" && ! -L "$source" ]] || { printf '%s\n' 'FOREX_CALENDAR_FACT_SCHEMA_STAGE_INVALID' >&2; exit 1; }
[[ "$(sha256sum "$source" | awk '{print $1}')" == "$expected" ]] || { printf '%s\n' 'FOREX_CALENDAR_FACT_SCHEMA_STAGE_HASH_MISMATCH' >&2; exit 1; }

cd /home/chris/projects/cs-ai-lab-infra
[[ -f .env && ! -L .env ]] || { printf '%s\n' 'FOREX_CALENDAR_FACT_SCHEMA_DATABASE_ENV_INVALID' >&2; exit 1; }
set -a
source .env
set +a
docker compose exec -T postgres psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" < "$source"
printf 'FOREX_CALENDAR_FACT_SCHEMA_APPLIED sha256:%s\n' "$expected"
