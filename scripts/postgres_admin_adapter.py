#!/usr/bin/env python3
"""Controlled administrator read/write adapter for Forex PostgreSQL on the T480.

Credentials are machine-local in ``.env``. The adapter uses the existing
shared T480 transport and exposes only the Forex table catalogue; it accepts
no arbitrary SQL and has no MT5 or trading operation. Writes require explicit
approval and remain subject to the database's point-in-time and immutability
controls.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from html import escape
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from postgres_pgvector_adapter import remote  # noqa: E402

TABLES = (
    "source_registry",
    "raw_observation",
    "dataset_snapshot",
    "dataset_snapshot_observation",
    "price_bar",
    "gdelt_h1_aggregate",
)
ORDER_BY = {
    "source_registry": "source_id",
    "raw_observation": "observation_id",
    "dataset_snapshot": "snapshot_id",
    "dataset_snapshot_observation": "snapshot_id, observation_id",
    "price_bar": "time_utc",
    "gdelt_h1_aggregate": "bucket_time_utc",
}
ORDER_DIRECTION = {
    "source_registry": "ASC",
    "raw_observation": "DESC",
    "dataset_snapshot": "DESC",
    "dataset_snapshot_observation": "ASC",
    "price_bar": "DESC",
    "gdelt_h1_aggregate": "DESC",
}
REQUIRED_ENV = ("FOREX_POSTGRES_HOST", "FOREX_POSTGRES_PORT", "FOREX_POSTGRES_DB", "FOREX_POSTGRES_USER", "FOREX_POSTGRES_PASSWORD")
WRITE_COLUMNS = {
    "source_registry": ("source_id", "contract_version", "owner", "license", "cost_model", "api_version", "endpoint_allowlist", "rate_limit", "retention_rule", "historical_depth", "revision_support", "timezone_policy", "outage_policy", "approval_status", "secrets_reference", "provenance_note"),
    "raw_observation": ("observation_id", "contract_version", "source_id", "source_revision", "observed_at_utc", "available_at_utc", "retrieved_at_utc", "timezone", "payload_sha256", "payload_path", "redacted"),
    "dataset_snapshot": ("snapshot_id", "contract_version", "instrument", "timeframe", "decision_cutoff_utc", "created_at_utc", "artifact_sha256", "no_lookahead"),
    "dataset_snapshot_observation": ("snapshot_id", "observation_id"),
    "price_bar": ("snapshot_id", "time_utc", "open", "high", "low", "close", "volume", "raw_observation_id", "available_at_utc"),
    "gdelt_h1_aggregate": ("aggregate_id", "observation_id", "bucket_time_utc", "available_at_utc", "article_count", "mean_tone", "query_definition_version", "uncertainty_label"),
}


def load_local_env() -> dict[str, str]:
    path = ROOT / ".env"
    values: dict[str, str] = {}
    if path.is_file():
        for raw in path.read_text(encoding="utf-8").splitlines():
            name, separator, value = raw.partition("=")
            if separator and not name.lstrip().startswith("#"):
                values[name.strip()] = value.strip()
    values.update({key: value for key, value in os.environ.items() if key.startswith("FOREX_POSTGRES_")})
    missing = [key for key in REQUIRED_ENV if not values.get(key)]
    if missing:
        raise RuntimeError("Missing local PostgreSQL settings: " + ", ".join(missing))
    return values


def _psql(query: str) -> dict:
    # The shared-side .env is the transport credential source. Local .env is
    # deliberately validated above so desktop tools and this adapter share one
    # operator-owned credential set without printing it.
    return remote(
        "docker compose exec -T postgres psql -X -v ON_ERROR_STOP=1 "
        '-U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc '
        + json.dumps(query)
        + " </dev/null"
    )


def _literal(value: object, column: str) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    if column == "endpoint_allowlist":
        if not isinstance(value, list):
            raise RuntimeError("endpoint_allowlist must be a JSON list")
        text = json.dumps(value).replace("'", "''")
        return f"'{text}'::jsonb"
    if not isinstance(value, str):
        raise RuntimeError(f"{column} must be a string, number, boolean, or null")
    return "'" + value.replace("'", "''") + "'"


def _load_write_payload(path: Path) -> dict[str, object]:
    resolved = path.resolve()
    if not resolved.is_relative_to(ROOT.resolve()) or not resolved.is_file():
        raise RuntimeError("--file must name a JSON object beneath this repository")
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("write payload must be one JSON object")
    return payload


def _write_sql(table: str, payload: dict[str, object]) -> str:
    columns = WRITE_COLUMNS[table]
    if set(payload) != set(columns):
        missing = sorted(set(columns) - set(payload))
        unknown = sorted(set(payload) - set(columns))
        details = (["missing=" + ",".join(missing)] if missing else []) + (["unknown=" + ",".join(unknown)] if unknown else [])
        raise RuntimeError("write payload fields must exactly match the table contract: " + " ".join(details))
    names = ", ".join(columns)
    values = ", ".join(_literal(payload[column], column) for column in columns)
    if table == "source_registry":
        updates = ", ".join(f"{column}=EXCLUDED.{column}" for column in columns if column != "source_id")
        return f"INSERT INTO forex.source_registry ({names}) VALUES ({values}) ON CONFLICT (source_id) DO UPDATE SET {updates};"
    return f"INSERT INTO forex.{table} ({names}) VALUES ({values});"


def export_html(output: Path) -> Path:
    load_local_env()
    resolved = output.resolve()
    if not resolved.is_relative_to(ROOT.resolve()):
        raise RuntimeError("--output must remain beneath this repository")
    deployed_tables = set(run("tables", None, 1)["result"])
    rows_by_table = {
        table: run("read", table, 1000)["result"]
        for table in TABLES
        if table in deployed_tables
    }

    def coverage(rows: list[dict[str, object]], field: str) -> str:
        values = sorted(str(row[field]) for row in rows if row.get(field) is not None)
        return f"{values[0]} → {values[-1]}" if values else "No data yet"

    def operator_summary() -> str:
        price_rows = rows_by_table.get("price_bar", [])
        gdelt_rows = rows_by_table.get("gdelt_h1_aggregate", [])
        price_hours = {str(row.get("time_utc")) for row in price_rows}
        gdelt_hours = {str(row.get("bucket_time_utc")) for row in gdelt_rows}
        overlap = len(price_hours & gdelt_hours)
        sources = rows_by_table.get("source_registry", [])
        source_lineage = ", ".join(
            f"{row.get('source_id', '?')} ({row.get('approval_status', '?')})"
            for row in sources
        ) or "No source catalogue rows"
        return f'''<section class="summary"><h2>Read-only research summary</h2>
<p class="boundary">DEMO_ONLY historical research data. No order controls, live-account access, trading signal, or write action is available in this report.</p>
<div class="cards">
<article><h3>EUR/USD H1 coverage</h3><p>{escape(coverage(price_rows, "time_utc"))}</p><small>{len(price_rows)} displayed price bars</small></article>
<article><h3>Price freshness</h3><p>{escape(str(price_rows[0].get("available_at_utc", "No data yet")) if price_rows else "No data yet")}</p><small>Latest displayed price availability</small></article>
<article><h3>GDELT H1 context</h3><p>{escape(coverage(gdelt_rows, "bucket_time_utc"))}</p><small>{len(gdelt_rows)} displayed aggregate rows; experimental context only</small></article>
<article><h3>Alignment coverage</h3><p>{overlap} H1 buckets</p><small>Displayed UTC price/GDELT bucket overlap</small></article>
</div>
<h3>Source lineage</h3><p>{escape(source_lineage)}</p></section>'''

    def render_table(name: str, rows: list[dict[str, object]]) -> str:
        if not rows:
            return f"<h2>{escape(name)}</h2><p>No rows.</p>"
        columns = list(rows[0])
        header = "".join(f"<th>{escape(column)}</th>" for column in columns)
        body = "".join(
            "<tr>" + "".join(f"<td>{escape(str(row.get(column, '')))}</td>" for column in columns) + "</tr>"
            for row in rows
        )
        return f"<h2>{escape(name)} <small>({len(rows)} rows)</small></h2><div class=\"table-wrap\"><table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table></div>"

    captured = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    sections = "".join(render_table(table, rows_by_table[table]) for table in TABLES if table in rows_by_table)
    document = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Forex research data view</title><style>body{{font:14px system-ui,sans-serif;margin:32px;color:#172033}}.muted{{color:#5b6475}}.boundary{{background:#eef5ff;border-left:4px solid #2463b5;padding:12px}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px}}article{{border:1px solid #d9deea;border-radius:8px;padding:12px;background:#fff}}article h3{{margin:0 0 8px}}article p{{font-weight:600;overflow-wrap:anywhere}}.table-wrap{{overflow:auto;border:1px solid #d9deea;border-radius:8px}}table{{border-collapse:collapse;width:100%;white-space:nowrap}}th{{background:#18263d;color:#fff;position:sticky;top:0}}th,td{{padding:8px 10px;text-align:left;border-bottom:1px solid #e6eaf0}}tr:nth-child(even){{background:#f7f9fc}}small{{color:#657086;font-weight:normal}}</style></head><body><h1>Forex research data view</h1><p class="muted">Captured {escape(captured)} from the T480 shared PostgreSQL service.</p>{operator_summary()}{sections}</body></html>'''
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(document, encoding="utf-8")
    return resolved


def run(command: str, table: str | None, limit: int, payload: dict[str, object] | None = None) -> dict:
    load_local_env()
    if command == "status":
        result = _psql("SELECT json_build_object('database', current_database(), 'user', current_user, 'forex_tables', (SELECT count(*) FROM information_schema.tables WHERE table_schema='forex'));" )
    elif command == "tables":
        result = _psql("SELECT COALESCE(json_agg(table_name ORDER BY table_name), '[]'::json) FROM information_schema.tables WHERE table_schema='forex' AND table_type='BASE TABLE';")
    elif command == "schema":
        assert table
        result = _psql(f"SELECT COALESCE(json_agg(json_build_object('column', column_name, 'type', data_type, 'nullable', is_nullable) ORDER BY ordinal_position), '[]'::json) FROM information_schema.columns WHERE table_schema='forex' AND table_name='{table}';")
    elif command in {"read", "preview"}:
        assert table
        result = _psql(f"SELECT COALESCE(json_agg(row_to_json(record)), '[]'::json) FROM (SELECT * FROM forex.{table} ORDER BY {ORDER_BY[table]} {ORDER_DIRECTION[table]} LIMIT {limit}) record;")
    else:
        assert table and payload is not None
        result = _psql(_write_sql(table, payload) + " SELECT json_build_object('written', true, 'table', '" + table + "');")
    if not result["ok"]:
        raise RuntimeError(result["stderr"].strip() or "T480 PostgreSQL operation failed")
    return {"command": command, "table": table, "result": json.loads(result["stdout"] or "null")}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Controlled Forex PostgreSQL administrator adapter.")
    parser.add_argument("command", choices=("status", "tables", "schema", "read", "preview", "write", "export-html"))
    parser.add_argument("--table", choices=TABLES)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--file", type=Path, help="repository-relative JSON row for write")
    parser.add_argument("--approve", action="store_true", help="required for a database write")
    parser.add_argument("--output", type=Path, default=Path("reports/forex_postgres_export.html"), help="repository-relative HTML export path")
    args = parser.parse_args(argv)
    if args.command in {"schema", "read", "preview", "write"} and not args.table:
        parser.error("--table is required for schema, read, preview, and write")
    if args.command == "write" and (not args.file or not args.approve):
        parser.error("write requires --file and --approve")
    if not 1 <= args.limit <= 1000:
        parser.error("--limit must be between 1 and 1000")
    try:
        if args.command == "export-html":
            print(export_html(args.output))
            return 0
        payload = _load_write_payload(args.file) if args.command == "write" else None
        print(json.dumps(run(args.command, args.table, args.limit, payload), indent=2))
    except (RuntimeError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
