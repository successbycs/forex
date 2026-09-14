"""Pure validation of the fixed h_slow_demo_preflight operation result."""
from __future__ import annotations
import hashlib,json,math,re
from datetime import UTC,datetime
from typing import Any
FIELDS={"ok","status","captured_at_utc","account_label","account_scope_sha256","server","currency","symbol","bid","ask","tick_time_msc","broker_timestamp_offset_seconds","tick_age_seconds","open_positions","symbol_specification"}
SPEC={"name","point","trade_tick_size","trade_tick_value_loss","trade_contract_size","volume_min","volume_max","volume_step","trade_stops_level","trade_freeze_level"}
class HSlowBrokerPreflightError(ValueError):pass
def validate_broker_preflight(value:dict[str,Any],*,expected_broker_timestamp_offset_seconds:int)->dict[str,Any]:
 if type(expected_broker_timestamp_offset_seconds) is not int or not 0<=expected_broker_timestamp_offset_seconds<=86400:raise HSlowBrokerPreflightError("expected broker offset invalid")
 if not isinstance(value,dict) or set(value)!=FIELDS or value.get("ok") is not True or value.get("status")!="PREFLIGHT_OK" or value.get("account_label")!="H1_demo" or value.get("server")!="GOMarketsMU-Demo" or value.get("currency")!="AUD" or value.get("symbol")!="EURUSD":raise HSlowBrokerPreflightError("preflight identity/status invalid")
 if not isinstance(value.get("account_scope_sha256"),str) or re.fullmatch(r"sha256:[0-9a-f]{64}",value["account_scope_sha256"]) is None:raise HSlowBrokerPreflightError("scope digest invalid")
 try:t=datetime.fromisoformat(value["captured_at_utc"].replace("Z","+00:00"))
 except Exception as e:raise HSlowBrokerPreflightError("captured timestamp invalid") from e
 if t.tzinfo is None or t.astimezone(UTC).isoformat().replace("+00:00","Z")!=value["captured_at_utc"]:raise HSlowBrokerPreflightError("captured timestamp invalid")
 if type(value.get("tick_time_msc")) is not int or value["tick_time_msc"]<=0 or type(value.get("open_positions")) is not int or not 0<=value["open_positions"]<=1:raise HSlowBrokerPreflightError("tick/position invalid")
 for k in ("broker_timestamp_offset_seconds","tick_age_seconds","bid","ask"):
  if isinstance(value.get(k),bool) or not isinstance(value.get(k),(int,float)) or not math.isfinite(value[k]) or value[k]<0:raise HSlowBrokerPreflightError("quote/offset invalid")
 if value["broker_timestamp_offset_seconds"]!=expected_broker_timestamp_offset_seconds:raise HSlowBrokerPreflightError("broker offset mismatch")
 expected=t.timestamp()-value["tick_time_msc"]/1000+value["broker_timestamp_offset_seconds"]
 if value["tick_age_seconds"]>15 or value["tick_age_seconds"]<0 or expected<0 or expected>15 or abs(value["tick_age_seconds"]-expected)>.001 or value["bid"]<=0 or value["ask"]<value["bid"]:raise HSlowBrokerPreflightError("quote freshness invalid")
 s=value.get("symbol_specification")
 if not isinstance(s,dict) or set(s)!=SPEC or s.get("name")!="EURUSD":raise HSlowBrokerPreflightError("symbol specification invalid")
 for k in SPEC-{"name","trade_stops_level","trade_freeze_level"}:
  if isinstance(s[k],bool) or not isinstance(s[k],(int,float)) or not math.isfinite(s[k]) or s[k]<=0:raise HSlowBrokerPreflightError("symbol specification numeric invalid")
 for k in ("trade_stops_level","trade_freeze_level"):
  if isinstance(s[k],bool) or not isinstance(s[k],(int,float)) or not math.isfinite(s[k]) or s[k]<0:raise HSlowBrokerPreflightError("symbol protection specification invalid")
 if s["volume_min"]>s["volume_max"] or s["volume_step"]>s["volume_min"] or abs((s["volume_min"]/s["volume_step"])-round(s["volume_min"]/s["volume_step"]))>1e-8 or abs((s["volume_max"]/s["volume_step"])-round(s["volume_max"]/s["volume_step"]))>1e-8:raise HSlowBrokerPreflightError("symbol volume lattice invalid")
 raw=json.loads(json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False));return {"preflight":raw,"instrument":"EUR/USD","receipt_sha256":"sha256:"+hashlib.sha256(json.dumps(raw,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()}
