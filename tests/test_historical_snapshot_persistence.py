from __future__ import annotations

import pytest

from forex.closed_bar_snapshot_builder import build_closed_eurusd_snapshot
from forex.historical_snapshot_persistence import HistoricalSnapshotPersistenceError, persist_historical_snapshot


def snapshot():
    raw=b"payload"; import hashlib
    source={"contract_version":"forex.historical-data.v1","source_id":"source","owner":"o","license":"l","cost_model":"none","api_version":"v","endpoint_allowlist":[],"rate_limit":"n/a","retention_rule":"immutable","historical_depth":"unknown","revision_support":"yes","timezone_policy":"UTC-normalised","outage_policy":"none","approval_status":"DEMO_ONLY","secrets_reference":"NONE","provenance_note":"test"}
    bars=[{"time_utc":"2026-01-01T00:00:00Z","open":1.1,"high":1.2,"low":1.0,"close":1.15,"volume":1,"available_at_utc":"2026-01-01T02:00:00Z"}]
    return build_closed_eurusd_snapshot(snapshot_id="s",timeframe="H1",decision_cutoff_utc="2026-01-01T03:00:00Z",capture_available_at_utc="2026-01-01T02:00:00Z",source_registry_entry=source,source_revision="r1",raw_payload=raw,payload_sha256="sha256:"+hashlib.sha256(raw).hexdigest(),parsed_bars=bars)

class Cur:
 def __init__(self,db):self.db=db;self.row=None
 def __enter__(self):return self
 def __exit__(self,*a):return None
 def execute(self,q,p=()):
  self.db.q.append(q); key=(q.split(" ")[2] if q.startswith("INSERT") else q.split(" FROM ")[1].split()[0],tuple(p));self.row=None
  if q.startswith("INSERT"):
   if self.db.fail and len([x for x in self.db.q if x.startswith("INSERT")])==2:raise RuntimeError("db fail")
   if key not in self.db.rows:self.db.rows[key]=tuple(p);self.row=(p[0],)
  elif key in self.db.rows:self.row=self.db.rows[key][1:] if "source_registry" in q or "raw_observation" in q or "dataset_snapshot" in q else self.db.rows[key][1:]
 def fetchone(self):return self.row
class Conn:
 def __init__(self,db,auto=False):self.db=db;self.autocommit=auto
 def __enter__(self):self.db.connections+=1;return self
 def __exit__(self,t,*a):self.db.rolled=t is not None
 def cursor(self):return Cur(self.db)
class DB:
 def __init__(self):self.q=[];self.rows={};self.connections=0;self.rolled=False;self.fail=False
 def connect(self):return Conn(self)

def test_full_write_one_transaction_and_invalid_preio():
 db=DB();r=persist_historical_snapshot(snapshot(),db.connect);assert r["created_count"]==5 and db.connections==1
 bad=snapshot();bad["price_bars"][0]["close"]=0
 with pytest.raises(HistoricalSnapshotPersistenceError):persist_historical_snapshot(bad,db.connect)

def test_autocommit_and_midbatch_failure():
 db=DB()
 with pytest.raises(HistoricalSnapshotPersistenceError):persist_historical_snapshot(snapshot(),lambda:Conn(db,True))
 assert not db.q
 db=DB();db.fail=True
 with pytest.raises(RuntimeError):persist_historical_snapshot(snapshot(),db.connect)
 assert db.rolled
