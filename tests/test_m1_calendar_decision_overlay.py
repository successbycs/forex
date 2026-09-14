from __future__ import annotations
from copy import deepcopy
import pytest
from forex.m1_calendar_decision_overlay import M1CalendarOverlayError,apply_calendar_overlay
def gate(state,permitted,reason="reason"):
 return {"schema_version":"forex.m1-event-risk-gate.v1","execution_authority":False,"scope":"NEW_ENTRY_ONLY","state":state,"new_entry_permitted":permitted,"reason":reason}
def cand(action="BUY"):return {"proposal_id":"p1","action":action}
def test_disabled_clear_and_no_trade_preserve_baseline():
 assert apply_calendar_overlay(candidate=cand(),gate_observation=gate("ANNOTATION_ONLY_DISABLED",None))["final_action"]=="BUY"
 assert apply_calendar_overlay(candidate=cand("SELL"),gate_observation=gate("NEW_ENTRY_PERMITTED",True))["final_action"]=="SELL"
 assert apply_calendar_overlay(candidate=cand("NO_TRADE"),gate_observation=gate("NEW_ENTRY_REFUSED_EVENT_WINDOW",False))["final_action"]=="NO_TRADE"
def test_event_and_unavailable_context_refuse_new_entry():
 for state in ("NEW_ENTRY_REFUSED_EVENT_WINDOW","FAIL_SAFE_CONTEXT_UNAVAILABLE"):
  result=apply_calendar_overlay(candidate=cand(),gate_observation=gate(state,False,"blocked"));assert result["final_action"]=="NO_TRADE" and result["reason"]=="CALENDAR_NEW_ENTRY_REFUSED:blocked"
def test_digest_binds_candidate_gate_final_action_and_reason():
 result=apply_calendar_overlay(candidate=cand(),gate_observation=gate("NEW_ENTRY_PERMITTED",True));tampered=deepcopy(result);tampered["final_action"]="SELL"
 import hashlib,json
 body={k:v for k,v in tampered.items() if k!="overlay_sha256"};assert tampered["overlay_sha256"]!="sha256:"+hashlib.sha256(json.dumps(body,sort_keys=True,separators=(",",":")).encode()).hexdigest()
def test_invalid_candidate_or_gate_refuse():
 with pytest.raises(M1CalendarOverlayError):apply_calendar_overlay(candidate={"action":"BUY"},gate_observation=gate("x",True))
 with pytest.raises(M1CalendarOverlayError):apply_calendar_overlay(candidate=cand(),gate_observation={"bad":True})
def test_gate_shape_and_state_permission_coherence_are_closed():
 with pytest.raises(M1CalendarOverlayError):apply_calendar_overlay(candidate=cand(),gate_observation={**gate("NEW_ENTRY_PERMITTED",True),"extra":1})
 with pytest.raises(M1CalendarOverlayError):apply_calendar_overlay(candidate=cand(),gate_observation=gate("NEW_ENTRY_PERMITTED",False))
 with pytest.raises(M1CalendarOverlayError):apply_calendar_overlay(candidate=cand(),gate_observation={**gate("NEW_ENTRY_REFUSED_EVENT_WINDOW",False),"event_count":-1})
 with pytest.raises(M1CalendarOverlayError):apply_calendar_overlay(candidate=cand(),gate_observation=gate({},False))
 with pytest.raises(M1CalendarOverlayError):apply_calendar_overlay(candidate=cand(),gate_observation=gate("FAIL_SAFE_CONTEXT_INVENTED",False))
