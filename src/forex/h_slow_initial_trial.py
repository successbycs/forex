"""Pure fixed-risk initial H_SLOW Demo trial readiness validation."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
SCHEMA="forex.h-slow.initial-fixed-risk-trial.v1"
FIELDS={"schema_version","stream_id","trial_id","resume_id","account_label","server","instrument","max_loss_aud","max_notional_usd","lease_budget_usd","maximum_volume_lots","max_open_positions","execution_authority","submission_status"}
_FIXED_CEILINGS={"max_loss_aud":1000.0,"max_notional_usd":10000.0,"lease_budget_usd":100000.0,"maximum_volume_lots":0.01}
class HSlowInitialTrialError(ValueError):pass
def validate_initial_trial(value:dict[str,Any])->dict[str,Any]:
 if not isinstance(value,dict) or set(value)!=FIELDS or value.get("schema_version")!=SCHEMA or value.get("stream_id")!="H_SLOW" or value.get("trial_id")!="h1_trial" or value.get("resume_id")!="resume_h1" or value.get("account_label")!="H1_demo" or value.get("server")!="GOMarketsMU-Demo" or value.get("instrument")!="EUR/USD" or value.get("execution_authority") is not False or value.get("submission_status")!="DISABLED_NOT_ROUTED":raise HSlowInitialTrialError("initial trial identity or authority is invalid")
 for field in ("max_loss_aud","max_notional_usd","lease_budget_usd","maximum_volume_lots"):
  if isinstance(value[field],bool) or not isinstance(value[field],(int,float)) or value[field]<=0 or value[field]!=value[field] or value[field] in (float("inf"),float("-inf")) or value[field]>_FIXED_CEILINGS[field]:raise HSlowInitialTrialError("initial trial fixed cap is invalid")
 if type(value["max_open_positions"]) is not int or value["max_open_positions"]!=1:raise HSlowInitialTrialError("initial trial permits exactly one position")
 return dict(value)
def load_initial_trial(path:Path)->dict[str,Any]:
 if not isinstance(path,Path) or path.is_symlink() or not path.is_file():raise HSlowInitialTrialError("trial config path unsafe")
 try:return validate_initial_trial(json.loads(path.read_bytes()))
 except (OSError,json.JSONDecodeError) as e:raise HSlowInitialTrialError("trial config malformed") from e
