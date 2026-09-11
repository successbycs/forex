"""M26 fail-closed offline pre-execution revalidation model."""
from __future__ import annotations
from datetime import UTC, datetime
from typing import Any

def _utc(v: str) -> datetime:
 p=datetime.fromisoformat(v.replace('Z','+00:00'))
 if p.tzinfo is None: raise ValueError('timestamp needs offset')
 return p.astimezone(UTC)

def revalidate(intent: dict[str,Any], approval: dict[str,Any], observation: dict[str,Any]) -> dict[str,Any]:
 required={'intent_id','action','mandatory_exit_cutoff_utc','risk_outcome','sizing_outcome'}
 if required-intent.keys(): raise ValueError('incomplete intent')
 now=_utc(observation['observed_at_utc']); reasons=[]
 if intent['action'] not in {'BUY','SELL'}: reasons.append('NO_ACTIONABLE_INTENT')
 if intent['risk_outcome']!='APPROVE_SIMULATION' or intent['sizing_outcome']!='SIZE_SIMULATION': reasons.append('RISK_OR_SIZING_CHANGED')
 if approval.get('outcome')!='APPROVED_FOR_FUTURE_REVALIDATION_ONLY': reasons.append('APPROVAL_NOT_VALID')
 elif now>_utc(approval['expires_at_utc']): reasons.append('APPROVAL_EXPIRED')
 quote_at=_utc(observation['quote_at_utc'])
 if (now-quote_at).total_seconds()>10 or quote_at>now: reasons.append('QUOTE_NOT_FRESH')
 if float(observation['spread_points'])>12: reasons.append('SPREAD_LIMIT')
 if observation.get('market_state')!='NORMAL': reasons.append('MARKET_STATE_CHANGED')
 if now>=_utc(intent['mandatory_exit_cutoff_utc']): reasons.append('EXIT_CUTOFF_REACHED')
 return {'intent_id':intent['intent_id'],'outcome':'REVALIDATED_SIMULATION' if not reasons else 'REFUSE','reasons':sorted(set(reasons)),'observed_at_utc':now.isoformat().replace('+00:00','Z'),'order_submission':'STRUCTURALLY_DISABLED'}

def drill_revalidation() -> dict[str,Any]:
 intent={'intent_id':'buy','action':'BUY','mandatory_exit_cutoff_utc':'2026-09-11T18:00:00Z','risk_outcome':'APPROVE_SIMULATION','sizing_outcome':'SIZE_SIMULATION'}; approval={'outcome':'APPROVED_FOR_FUTURE_REVALIDATION_ONLY','expires_at_utc':'2026-09-11T12:10:00Z'}; base={'observed_at_utc':'2026-09-11T12:05:00Z','quote_at_utc':'2026-09-11T12:04:55Z','spread_points':8,'market_state':'NORMAL'}
 return {'marker':'FOREX_M26_REVALIDATION_DRILL_OK','results':{'valid':revalidate(intent,approval,base),'stale':revalidate(intent,approval,{**base,'quote_at_utc':'2026-09-11T12:04:49Z'}),'spread':revalidate(intent,approval,{**base,'spread_points':13}),'market':revalidate(intent,approval,{**base,'market_state':'HALTED'}),'expired':revalidate(intent,{**approval,'expires_at_utc':'2026-09-11T12:04:00Z'},base)}}
