"""Submission-disabled fixed-trial H_SLOW execution request envelope."""
from __future__ import annotations
import hashlib,json
import math,re
from decimal import Decimal, InvalidOperation, localcontext
from typing import Any
from forex.h_slow_initial_trial import HSlowInitialTrialError,validate_initial_trial
from forex.h_slow_broker_preflight import HSlowBrokerPreflightError,validate_broker_preflight
SCHEMA="forex.h-slow.execution-request.v1"
class HSlowExecutionRequestError(ValueError):pass
def _sha(x):return "sha256:"+hashlib.sha256(json.dumps(x,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
def _number(value,label,*,positive=True):
 if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or (value<=0 if positive else value<0):raise HSlowExecutionRequestError(f"preparation {label} is invalid")
 try:number=Decimal(str(value))
 except (InvalidOperation,ValueError) as e:raise HSlowExecutionRequestError(f"preparation {label} is invalid") from e
 if len(number.as_tuple().digits)>18 or (number!=0 and not Decimal("1e-12")<=number<=Decimal("1e12")):raise HSlowExecutionRequestError(f"preparation {label} exceeds supported numeric precision or magnitude")
 return number
def build_execution_request(*,initial_trial:dict[str,Any],preparation:dict[str,Any],broker_preflight:dict[str,Any],expected_broker_timestamp_offset_seconds:int)->dict[str,Any]:
 try:trial=validate_initial_trial(initial_trial)
 except HSlowInitialTrialError as e:raise HSlowExecutionRequestError("initial trial is invalid") from e
 try: preflight=validate_broker_preflight(broker_preflight,expected_broker_timestamp_offset_seconds=expected_broker_timestamp_offset_seconds)
 except HSlowBrokerPreflightError as e:raise HSlowExecutionRequestError("broker preflight is invalid") from e
 raw=preflight["preflight"]
 if raw["open_positions"]!=0:raise HSlowExecutionRequestError("broker preflight is not flat")
 required={"schema_version","outcome","reason","lifecycle_action_id","direction","entry_price","technical_stop_price","executable_stop_price","volume_lots","planned_stop_loss_aud","planned_adverse_cost_allowance_aud","planned_total_loss_aud","planned_notional_usd","planned_margin_aud","plan_sha256","market_inputs_sha256","limits_sha256","edge_sizing_result_sha256","edge_policy_sha256","edge_evidence_sha256","initial_trial_sha256","preparation_input_sha256","execution_authority","submission_status"}
 if not isinstance(preparation,dict) or set(preparation)!=required or preparation.get("schema_version")!="forex.h-slow.order-preparation.v1" or preparation.get("outcome")!="PREPARED_DISABLED" or preparation.get("reason")!="DECLARED_INPUTS_WITHIN_BOUNDED_CAPACITY" or preparation.get("execution_authority") is not False or preparation.get("submission_status")!="DISABLED_NOT_ROUTED" or preparation.get("direction") not in {"BUY","SELL"}:raise HSlowExecutionRequestError("preparation is not a closed fixed-trial PREPARED_DISABLED record")
 if not isinstance(preparation.get("lifecycle_action_id"),str) or re.fullmatch(r"sha256:[0-9a-f]{64}",preparation["lifecycle_action_id"]) is None:raise HSlowExecutionRequestError("preparation lifecycle action is noncanonical")
 if any(preparation.get(field) is not None for field in ("edge_sizing_result_sha256","edge_policy_sha256","edge_evidence_sha256")):raise HSlowExecutionRequestError("fixed initial trial cannot carry edge tier provenance")
 trial_hash=_sha(initial_trial)
 if preparation.get("initial_trial_sha256")!=trial_hash:raise HSlowExecutionRequestError("preparation initial trial provenance is invalid")
 for field in ("plan_sha256","market_inputs_sha256","limits_sha256","preparation_input_sha256"):
  if not isinstance(preparation.get(field),str) or re.fullmatch(r"sha256:[0-9a-f]{64}",preparation[field]) is None:raise HSlowExecutionRequestError("preparation digest is noncanonical")
 numbers={field:_number(preparation.get(field),field) for field in ("entry_price","technical_stop_price","executable_stop_price","volume_lots","planned_stop_loss_aud","planned_total_loss_aud","planned_notional_usd","planned_margin_aud")}
 cost=_number(preparation.get("planned_adverse_cost_allowance_aud"),"planned_adverse_cost_allowance_aud",positive=False)
 if ((preparation["direction"]=="BUY" and not numbers["executable_stop_price"]<numbers["entry_price"]) or (preparation["direction"]=="SELL" and not numbers["executable_stop_price"]>numbers["entry_price"])):raise HSlowExecutionRequestError("preparation stop is on the wrong executable side")
 with localcontext() as calculation_context:
  calculation_context.prec=50
  expected_total=numbers["planned_stop_loss_aud"]+cost
 if numbers["planned_total_loss_aud"]!=expected_total:raise HSlowExecutionRequestError("preparation total loss does not bind loss and cost")
 if numbers["volume_lots"]>Decimal(str(trial["maximum_volume_lots"])) or numbers["planned_total_loss_aud"]>Decimal(str(trial["max_loss_aud"])) or numbers["planned_notional_usd"]>Decimal(str(trial["max_notional_usd"])):raise HSlowExecutionRequestError("preparation exceeds fixed trial caps")
 if numbers["planned_notional_usd"]>Decimal(str(trial["lease_budget_usd"])):raise HSlowExecutionRequestError("preparation exceeds fixed trial lease budget")
 expected_entry=Decimal(str(raw["ask"] if preparation["direction"]=="BUY" else raw["bid"]))
 if numbers["entry_price"]!=expected_entry:raise HSlowExecutionRequestError("preparation entry price does not match preflight side")
 spec=raw["symbol_specification"];volume=numbers["volume_lots"];minimum=Decimal(str(spec["volume_min"]));maximum=Decimal(str(spec["volume_max"]));step=Decimal(str(spec["volume_step"]))
 with localcontext() as volume_context:
  volume_context.prec=50
  volume_steps=volume/step
 if volume<minimum or volume>maximum or volume_steps!=volume_steps.to_integral_value():raise HSlowExecutionRequestError("preparation volume does not match preflight specification")
 content={"schema_version":SCHEMA,"broker_preflight_receipt_sha256":preflight["receipt_sha256"],"trial_sha256":trial_hash,"trial_id":trial["trial_id"],"resume_id":trial["resume_id"],"account_label":trial["account_label"],"server":trial["server"],"instrument":trial["instrument"],"lifecycle_action_id":preparation["lifecycle_action_id"],"direction":preparation["direction"],"entry_price":preparation["entry_price"],"stop_price":preparation["executable_stop_price"],"volume_lots":preparation["volume_lots"],"max_loss_aud":trial["max_loss_aud"],"max_notional_usd":trial["max_notional_usd"],"lease_budget_usd":trial["lease_budget_usd"],"preparation_input_sha256":preparation["preparation_input_sha256"],"preparation_record_sha256":_sha(preparation),"execution_authority":False,"submission_status":"DISABLED_NOT_ROUTED"}
 return {**content,"request_sha256":_sha(content)}
