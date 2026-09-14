"""Atomic fixed-query persistence for validated H1/D1 historical snapshots."""
from __future__ import annotations

import json
from typing import Any, Callable, Protocol

from forex.data_contracts import ContractError, validate_dataset_snapshot


class HistoricalSnapshotPersistenceError(ValueError): pass

class _Cursor(Protocol):
    def execute(self, query: str, params: tuple[Any, ...] = ...) -> Any: ...
    def fetchone(self) -> Any: ...
    def __enter__(self) -> "_Cursor": ...
    def __exit__(self, *args: Any) -> None: ...
class _Connection(Protocol):
    autocommit: bool
    def cursor(self) -> _Cursor: ...
    def __enter__(self) -> "_Connection": ...
    def __exit__(self,*args:Any)->None: ...

def _put(cursor: _Cursor, insert: str, select: str, params: tuple[Any,...], expected: tuple[Any,...], lookup: tuple[Any,...] | None = None) -> bool:
    cursor.execute(insert, params)
    if cursor.fetchone() is not None: return True
    cursor.execute(select, (params[0],) if lookup is None else lookup)
    row = cursor.fetchone()
    if row is None or tuple(row) != expected:
        raise HistoricalSnapshotPersistenceError("existing immutable row conflicts or disappeared")
    return False

def persist_historical_snapshot(snapshot: Any, connection_factory: Callable[[], _Connection]) -> dict[str, Any]:
    try: checked = validate_dataset_snapshot(snapshot)
    except ContractError as exc: raise HistoricalSnapshotPersistenceError("snapshot is invalid") from exc
    if checked["timeframe"] not in {"H1","D1"}: raise HistoricalSnapshotPersistenceError("only H1/D1 snapshots are permitted")
    if not callable(connection_factory): raise HistoricalSnapshotPersistenceError("connection_factory must be callable")
    # Validate all serialisable parameters before opening the connection.
    sources, raws, bars = checked["source_registry"], checked["raw_observations"], checked["price_bars"]
    try: json.dumps(checked, sort_keys=True, separators=(",",":"), allow_nan=False)
    except (TypeError,ValueError) as exc: raise HistoricalSnapshotPersistenceError("snapshot is not finite JSON") from exc
    created=existing=0
    with connection_factory() as conn:
        if getattr(conn,"autocommit",None) is not False: raise HistoricalSnapshotPersistenceError("connection must expose autocommit=False")
        with conn.cursor() as cur:
            for s in sources:
                p=(s["source_id"],s["contract_version"],s["owner"],s["license"],s["cost_model"],s["api_version"],json.dumps(s["endpoint_allowlist"]),s["rate_limit"],s["retention_rule"],s["historical_depth"],s["revision_support"],s["timezone_policy"],s["outage_policy"],s["approval_status"],s["secrets_reference"],s["provenance_note"])
                made=_put(cur,"INSERT INTO forex.source_registry (source_id,contract_version,owner,license,cost_model,api_version,endpoint_allowlist,rate_limit,retention_rule,historical_depth,revision_support,timezone_policy,outage_policy,approval_status,secrets_reference,provenance_note) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (source_id) DO NOTHING RETURNING source_id","SELECT contract_version,owner,license,cost_model,api_version,endpoint_allowlist::text,rate_limit,retention_rule,historical_depth,revision_support,timezone_policy,outage_policy,approval_status,secrets_reference,provenance_note FROM forex.source_registry WHERE source_id=%s",p,(p[1],*p[2:6],p[6],*p[7:]))
                created+=made; existing+=not made
            for r in raws:
                p=tuple(r[k] for k in ("observation_id","contract_version","source_id","source_revision","observed_at_utc","available_at_utc","retrieved_at_utc","timezone","payload_sha256","payload_path","redacted"))
                made=_put(cur,"INSERT INTO forex.raw_observation (observation_id,contract_version,source_id,source_revision,observed_at_utc,available_at_utc,retrieved_at_utc,timezone,payload_sha256,payload_path,redacted) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (observation_id) DO NOTHING RETURNING observation_id","SELECT contract_version,source_id,source_revision,observed_at_utc,available_at_utc,retrieved_at_utc,timezone,payload_sha256,payload_path,redacted FROM forex.raw_observation WHERE observation_id=%s",p,p[1:]); created+=made; existing+=not made
            p=tuple(checked[k] for k in ("snapshot_id","contract_version","instrument","timeframe","decision_cutoff_utc","created_at_utc","artifact_sha256","no_lookahead"))
            made=_put(cur,"INSERT INTO forex.dataset_snapshot (snapshot_id,contract_version,instrument,timeframe,decision_cutoff_utc,created_at_utc,artifact_sha256,no_lookahead) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (snapshot_id) DO NOTHING RETURNING snapshot_id","SELECT contract_version,instrument,timeframe,decision_cutoff_utc,created_at_utc,artifact_sha256,no_lookahead FROM forex.dataset_snapshot WHERE snapshot_id=%s",p,p[1:]); created+=made; existing+=not made
            for r in raws:
                p=(checked["snapshot_id"],r["observation_id"]); made=_put(cur,"INSERT INTO forex.dataset_snapshot_observation (snapshot_id,observation_id) VALUES (%s,%s) ON CONFLICT DO NOTHING RETURNING snapshot_id","SELECT observation_id FROM forex.dataset_snapshot_observation WHERE snapshot_id=%s AND observation_id=%s",p,(p[1],),p); created+=made; existing+=not made
            for b in bars:
                p=(checked["snapshot_id"],b["time_utc"],b["open"],b["high"],b["low"],b["close"],b["volume"],b["raw_observation_id"],b["available_at_utc"])
                made=_put(cur,"INSERT INTO forex.price_bar (snapshot_id,time_utc,open,high,low,close,volume,raw_observation_id,available_at_utc) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (snapshot_id,time_utc) DO NOTHING RETURNING snapshot_id","SELECT time_utc,open,high,low,close,volume,raw_observation_id,available_at_utc FROM forex.price_bar WHERE snapshot_id=%s AND time_utc=%s",p,p[1:],p[:2]); created+=made; existing+=not made
    return {"snapshot_id":checked["snapshot_id"],"created_count":created,"existing_count":existing,"execution_authority":False}
