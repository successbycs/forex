"""M25 scoped, expiring offline approval records with no execution surface."""
from __future__ import annotations
import hashlib, json
from datetime import UTC, datetime
from typing import Any

def _utc(value: str) -> datetime:
 p=datetime.fromisoformat(value.replace('Z','+00:00'))
 if p.tzinfo is None: raise ValueError('timestamp needs offset')
 return p.astimezone(UTC)

def intent_hash(intent: dict[str, Any]) -> str:
 required={'intent_id','action','advisory_score','entry_window','mandatory_exit_cutoff_utc','risk_outcome','sizing_outcome'}
 if required-intent.keys(): raise ValueError('intent lacks required approval fields')
 return 'sha256:'+hashlib.sha256(json.dumps(intent,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def evaluate_approval(intent: dict[str, Any], approval: dict[str, Any], now_utc: str) -> dict[str, Any]:
 required={'approval_id','intent_sha256','decision','operator','decided_at_utc','expires_at_utc'}
 if required-approval.keys(): return {'outcome':'REFUSE','reason':'INCOMPLETE_APPROVAL','order_submission':'STRUCTURALLY_DISABLED'}
 now,decided,expires=(_utc(x) for x in (now_utc,approval['decided_at_utc'],approval['expires_at_utc']))
 if approval['intent_sha256']!=intent_hash(intent): reason='INTENT_MISMATCH'
 elif approval['decision']!='ACCEPT': reason='HUMAN_REJECTED'
 elif not approval['operator'].strip(): reason='MISSING_OPERATOR'
 elif expires<=decided or now>expires: reason='APPROVAL_EXPIRED'
 elif intent['action'] not in {'BUY','SELL'}: reason='NO_ACTIONABLE_INTENT'
 else: return {'outcome':'APPROVED_FOR_FUTURE_REVALIDATION_ONLY','approval_id':approval['approval_id'],'intent_sha256':approval['intent_sha256'],'expires_at_utc':expires.isoformat().replace('+00:00','Z'),'order_submission':'STRUCTURALLY_DISABLED'}
 return {'outcome':'REFUSE','reason':reason,'order_submission':'STRUCTURALLY_DISABLED'}

def drill_approvals() -> dict[str, Any]:
 intent={'intent_id':'m24-buy','action':'BUY','advisory_score':72,'entry_window':{'start_utc':'2026-09-11T12:01:00Z','end_utc':'2026-09-11T12:10:00Z'},'mandatory_exit_cutoff_utc':'2026-09-11T18:00:00Z','risk_outcome':'APPROVE_SIMULATION','sizing_outcome':'SIZE_SIMULATION'}; digest=intent_hash(intent); base={'intent_sha256':digest,'operator':'Chris','decided_at_utc':'2026-09-11T12:00:00Z','expires_at_utc':'2026-09-11T12:15:00Z'}
 return {'marker':'FOREX_M25_APPROVAL_DRILL_OK','results':{'accepted':evaluate_approval(intent,{'approval_id':'accepted',**base,'decision':'ACCEPT'},'2026-09-11T12:05:00Z'),'rejected':evaluate_approval(intent,{'approval_id':'rejected',**base,'decision':'REJECT'},'2026-09-11T12:05:00Z'),'expired':evaluate_approval(intent,{'approval_id':'expired',**base,'decision':'ACCEPT'},'2026-09-11T12:16:00Z'),'mismatch':evaluate_approval({**intent,'action':'SELL'},{'approval_id':'mismatch',**base,'decision':'ACCEPT'},'2026-09-11T12:05:00Z')}}
