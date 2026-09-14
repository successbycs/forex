#!/usr/bin/env python3
"""Persist facts from one explicit retained BLS store through the T480 path.

The command has no source-fetch, schema, SQL, broker, or trading interface.
It validates and canonicalises immutable retained evidence locally, then stages
only its hash-pinned JSON payload at one fixed T480 path. The remote operation
has fixed SQL and can insert only that staged canonical fact shape.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from postgres_admin_adapter import SETTINGS, TARGET, load_local_env, remote  # noqa: E402
from t480_core import build_ssh_command  # noqa: E402

_STAGE_WINDOWS_DIRECTORY = r"C:\Users\chris\Documents\Code\forex-bls-calendar-projection"
_STAGE_WINDOWS_FILE = _STAGE_WINDOWS_DIRECTORY + r"\bls_calendar_persistence_payload.json"
_STAGE_WSL_FILE = "/mnt/c/Users/chris/Documents/Code/forex-bls-calendar-projection/bls_calendar_persistence_payload.json"
_CONTAINER_FILE = "/tmp/forex_bls_calendar_persistence_payload.json"
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")


def _store(value: Path) -> Path:
    absolute = value.absolute()
    if any(candidate.is_symlink() for candidate in (absolute, *absolute.parents)):
        raise ValueError("retained BLS store path must not traverse a symlink")
    try:
        absolute.stat()
    except OSError as exc:
        raise ValueError("retained BLS store is unavailable") from exc
    if not absolute.is_dir():
        raise ValueError("retained BLS store must be an existing directory")
    return absolute


def build_payload(store: Path) -> tuple[dict[str, Any], bytes, str]:
    """Project one retained store and use the existing writer's validation."""
    from forex.bls_calendar_projection_persistence import _validated_projection
    from forex.bls_retained_calendar_facts import project_retained_bls_store

    projection = project_retained_bls_store(_store(store))
    payload = {
        "schema_version": "forex.bls-calendar-fact-persistence-payload.v1",
        "projection_sha256": projection["projection_sha256"],
        "journal_sha256": projection["journal_sha256"],
        "facts": _validated_projection(projection),
        "execution_authority": False,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return payload, raw, "sha256:" + hashlib.sha256(raw).hexdigest()


def _stage_payload(raw: bytes, payload_sha256: str) -> None:
    """Use the established Windows-backed T480 transfer pattern for one payload."""
    if not _DIGEST.fullmatch(payload_sha256) or "sha256:" + hashlib.sha256(raw).hexdigest() != payload_sha256:
        raise ValueError("canonical BLS persistence payload hash is invalid")
    quote = lambda value: "'" + value.replace("'", "''") + "'"
    with tempfile.NamedTemporaryFile(prefix="forex-bls-calendar-", suffix=".json", delete=False) as stream:
        stream.write(raw)
        local_file = Path(stream.name)
    try:
        mkdir = subprocess.run(
            build_ssh_command(TARGET, "$ErrorActionPreference='Stop'; New-Item -ItemType Directory -Force -Path "
                              + quote(_STAGE_WINDOWS_DIRECTORY) + " | Out-Null", SETTINGS),
            text=True, capture_output=True, check=False,
        )
        if mkdir.returncode:
            raise RuntimeError("T480 BLS payload staging directory could not be prepared")
        source_windows = subprocess.run(
            ["wslpath", "-w", str(local_file)], text=True, capture_output=True, check=True,
        ).stdout.strip()
        command = ("$ErrorActionPreference='Stop'; & scp.exe -B -o BatchMode=yes -o StrictHostKeyChecking=yes -- "
                   + quote(source_windows) + " " + quote(TARGET + ":" + _STAGE_WINDOWS_FILE)
                   + "; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }")
        transfer = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand",
             base64.b64encode(command.encode("utf-16-le")).decode("ascii")],
            text=True, capture_output=True, check=False,
        )
        if transfer.returncode:
            raise RuntimeError("T480 BLS payload staging transfer failed")
    finally:
        local_file.unlink(missing_ok=True)


def _remote_persist(payload: dict[str, Any], payload_sha256: str) -> dict[str, Any]:
    """Run fixed no-input SQL after the staged payload's hash is checked."""
    journal_sha256, projection_sha256 = payload["journal_sha256"], payload["projection_sha256"]
    if not all(isinstance(value, str) and _DIGEST.fullmatch(value)
               for value in (journal_sha256, projection_sha256, payload_sha256)):
        raise ValueError("canonical BLS persistence provenance digest is invalid")
    query = """WITH payload AS (SELECT pg_read_file(:'container_file')::jsonb AS document), guarded AS (
 SELECT document FROM payload WHERE document->>'schema_version'='forex.bls-calendar-fact-persistence-payload.v1'
 AND document->>'journal_sha256'=:'journal_sha256' AND document->>'projection_sha256'=:'projection_sha256'
 AND document->>'execution_authority'='false' AND jsonb_typeof(document->'facts')='array'
), facts AS (SELECT fact.* FROM guarded CROSS JOIN LATERAL jsonb_to_recordset(document->'facts') AS fact(
 fact_sha256 text,source_family text,source_url text,capture_completed_at_utc timestamptz,raw_sha256 text,receipt_sha256 text,event_identifier text,scheduled_at_utc timestamptz,event_title text,country_code text,currency_code text,impact text,qualification_state text,qualification_reason text,source_revision integer,event_payload jsonb
)), inserted AS (INSERT INTO forex.economic_calendar_event_fact
 (fact_sha256,source_family,source_url,capture_completed_at_utc,raw_sha256,receipt_sha256,event_identifier,scheduled_at_utc,event_title,country_code,currency_code,impact,qualification_state,qualification_reason,source_revision,event_payload)
 SELECT fact_sha256,source_family,source_url,capture_completed_at_utc,raw_sha256,receipt_sha256,event_identifier,scheduled_at_utc,event_title,country_code,currency_code,impact,qualification_state,qualification_reason,source_revision,event_payload FROM facts ON CONFLICT (fact_sha256) DO NOTHING RETURNING fact_sha256)
SELECT COALESCE((SELECT document->>'journal_sha256' FROM guarded),''),(SELECT count(*) FROM facts),(SELECT count(*) FROM inserted);"""
    encoded_query = base64.b64encode(query.encode("utf-8")).decode("ascii")
    body = f'''set -eu
source="{_STAGE_WSL_FILE}"
expected_payload="{payload_sha256[7:]}"
expected_journal="{journal_sha256}"
expected_projection="{projection_sha256}"
for ancestor in /mnt /mnt/c /mnt/c/Users /mnt/c/Users/chris /mnt/c/Users/chris/Documents /mnt/c/Users/chris/Documents/Code /mnt/c/Users/chris/Documents/Code/forex-bls-calendar-projection; do
 [ -d "$ancestor" ] && [ ! -L "$ancestor" ] || {{ printf '%s\\n' 'FOREX_BLS_PAYLOAD_STAGE_ANCESTOR_INVALID' >&2; exit 1; }}
done
[ -f "$source" ] && [ ! -L "$source" ] || {{ printf '%s\\n' 'FOREX_BLS_PAYLOAD_STAGE_INVALID' >&2; exit 1; }}
[ "$(sha256sum "$source" | awk '{{print $1}}')" = "$expected_payload" ] || {{ printf '%s\\n' 'FOREX_BLS_PAYLOAD_STAGE_HASH_MISMATCH' >&2; exit 1; }}
container="$(docker compose ps -q postgres)"
[ -n "$container" ] || {{ printf '%s\\n' 'FOREX_BLS_POSTGRES_CONTAINER_UNAVAILABLE' >&2; exit 1; }}
docker cp "$source" "$container:{_CONTAINER_FILE}"
docker compose exec -T postgres chmod 0644 "{_CONTAINER_FILE}"
query="$(printf '%s' '{encoded_query}' | base64 --decode)"
output="$(docker compose exec -T postgres psql -qAt -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v container_file='{_CONTAINER_FILE}' -v journal_sha256="$expected_journal" -v projection_sha256="$expected_projection" -c "$query" </dev/null)"
IFS='|' read -r observed_journal total_count created_count <<EOF
$output
EOF
[ "$observed_journal" = "$expected_journal" ] || {{ printf '%s\\n' 'FOREX_BLS_PAYLOAD_GUARD_REJECTED' >&2; exit 1; }}
case "$total_count:$created_count" in (*[!0-9:]*|:*|*::*) printf '%s\\n' 'FOREX_BLS_PERSISTENCE_COUNTS_INVALID' >&2; exit 1;; esac
[ "$created_count" -le "$total_count" ] || {{ printf '%s\\n' 'FOREX_BLS_PERSISTENCE_COUNTS_INVALID' >&2; exit 1; }}
existing_count=$((total_count-created_count))
printf 'FOREX_BLS_CALENDAR_FACTS_PERSISTED journal_sha256:%s created:%s existing:%s payload_sha256:{payload_sha256}\\n' "$observed_journal" "$created_count" "$existing_count"
'''
    result = remote(body)
    if not result.get("ok"):
        raise RuntimeError((result.get("stderr") or "").strip() or "T480 BLS fact persistence failed")
    pattern = re.compile(r"FOREX_BLS_CALENDAR_FACTS_PERSISTED journal_sha256:(sha256:[0-9a-f]{64}) created:([0-9]+) existing:([0-9]+) payload_sha256:(sha256:[0-9a-f]{64})")
    match = pattern.search(result.get("stdout", ""))
    if match is None or match.group(1) != journal_sha256 or match.group(4) != payload_sha256:
        raise RuntimeError("T480 BLS fact persistence returned an invalid result")
    return {"journal_sha256": journal_sha256, "created_count": int(match.group(2)),
            "existing_count": int(match.group(3)), "execution_authority": False}


def persist_store(store: Path) -> dict[str, Any]:
    payload, raw, payload_sha256 = build_payload(store)
    load_local_env()
    _stage_payload(raw, payload_sha256)
    return _remote_persist(payload, payload_sha256)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, required=True, help="existing retained BLS event-capture-store root")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(persist_store(args.store), sort_keys=True, allow_nan=False))
        return 0
    except (OSError, ValueError, TypeError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"retained BLS fact persistence refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
