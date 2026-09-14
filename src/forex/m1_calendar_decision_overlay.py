"""Pure final-action overlay for an already-selected M1 candidate."""
from __future__ import annotations
import hashlib,json
from typing import Any, Mapping

class M1CalendarOverlayError(ValueError): pass

def _canon(value: Any)->bytes:
 try:return json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()
 except (TypeError,ValueError) as exc:raise M1CalendarOverlayError("overlay input is not finite JSON") from exc

def apply_calendar_overlay(*, candidate: Mapping[str,Any], gate_observation: Mapping[str,Any])->dict[str,Any]:
 """Preserve an existing action unless the prepared gate explicitly refuses it."""
 if not isinstance(candidate,Mapping) or set(candidate)!={"action","proposal_id"} or candidate.get("action") not in {"BUY","SELL","NO_TRADE"} or not isinstance(candidate.get("proposal_id"),str) or not candidate["proposal_id"]:
  raise M1CalendarOverlayError("candidate shape is invalid")
 required={"schema_version","execution_authority","scope","state","new_entry_permitted","reason"}; optional={"event_count"}
 if not isinstance(gate_observation,Mapping) or not required <= set(gate_observation) or set(gate_observation)-required-optional or gate_observation.get("schema_version")!="forex.m1-event-risk-gate.v1" or gate_observation.get("execution_authority") is not False or gate_observation.get("scope")!="NEW_ENTRY_ONLY" or not isinstance(gate_observation.get("reason"),str):
  raise M1CalendarOverlayError("gate observation is invalid")
 permission=gate_observation["new_entry_permitted"]; state=gate_observation["state"]
 if not isinstance(state,str) or not state:
  raise M1CalendarOverlayError("gate observation state is incoherent")
 expected_permissions={
  "ANNOTATION_ONLY_DISABLED":None,
  "NEW_ENTRY_PERMITTED":True,
  "NEW_ENTRY_REFUSED_EVENT_WINDOW":False,
  "FAIL_SAFE_CONTEXT_UNAVAILABLE":False,
  "FAIL_SAFE_CONTEXT_PARTIAL":False,
  "FAIL_SAFE_CONTEXT_AMBIGUOUS":False,
 }
 if state not in expected_permissions or permission is not expected_permissions[state] or ("event_count" in gate_observation and (type(gate_observation["event_count"]) is not int or gate_observation["event_count"]<0)):
  raise M1CalendarOverlayError("gate observation state is incoherent")
 base=dict(candidate); gate=dict(gate_observation)
 refused=base["action"] in {"BUY","SELL"} and gate["new_entry_permitted"] is False
 final="NO_TRADE" if refused else base["action"]
 reason="CALENDAR_NEW_ENTRY_REFUSED:"+gate["reason"] if refused else "BASELINE_CANDIDATE_PRESERVED:"+gate["reason"]
 body={"schema_version":"forex.m1-calendar-decision-overlay.v1","candidate":base,"gate_observation":gate,"final_action":final,"reason":reason,"execution_authority":False}
 return {**body,"overlay_sha256":"sha256:"+hashlib.sha256(_canon(body)).hexdigest()}
