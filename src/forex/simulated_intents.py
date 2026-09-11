"""M24 auditable offline intent orchestration; it cannot execute orders."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from forex.simulated_risk import drill, load_policy
from forex.simulated_sizing import drill_sizing


def _utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp needs offset")
    return parsed.astimezone(UTC)


def orchestrate(candidate: dict[str, Any], *, risk: dict[str, Any], sizing: dict[str, Any], flat_by_hour_utc: int) -> dict[str, Any]:
    required={"intent_id","direction","advisory_score","calibration_status","decision_data_at_utc","entry_window_start_utc","entry_window_end_utc","invalidating_conditions","risk_flags"}
    if required-candidate.keys(): raise ValueError("candidate missing required audit fields")
    score=float(candidate['advisory_score']); direction=candidate['direction']
    decision,start,end=(_utc(candidate[key]) for key in ('decision_data_at_utc','entry_window_start_utc','entry_window_end_utc'))
    cutoff=decision.replace(hour=flat_by_hour_utc,minute=0,second=0,microsecond=0)
    reasons=[]
    if direction not in {'BUY','SELL','NO_TRADE'}: reasons.append('INVALID_DIRECTION')
    if not 0<=score<=100: reasons.append('INVALID_ADVISORY_SCORE')
    if candidate['calibration_status'] not in {'CALIBRATED','UNCALIBRATED'}: reasons.append('INVALID_CALIBRATION_STATUS')
    if not decision<=start<end<cutoff: reasons.append('INVALID_ENTRY_OR_EXIT_WINDOW')
    if risk.get('outcome')!='APPROVE_SIMULATION': reasons.append('RISK_REFUSED')
    if sizing.get('outcome')!='SIZE_SIMULATION': reasons.append('SIZING_REFUSED')
    if direction=='NO_TRADE': reasons.append('NO_DIRECTIONAL_INTENT')
    if candidate['risk_flags']: reasons.append('RISK_FLAGS_PRESENT')
    action='NO_TRADE' if reasons else direction
    return {'intent_id':candidate['intent_id'],'action':action,'advisory_score':score,'calibration_status':candidate['calibration_status'],'decision_data_at_utc':decision.isoformat().replace('+00:00','Z'),'entry_window':{'start_utc':start.isoformat().replace('+00:00','Z'),'end_utc':end.isoformat().replace('+00:00','Z')},'mandatory_exit_cutoff_utc':cutoff.isoformat().replace('+00:00','Z'),'invalidating_conditions':list(candidate['invalidating_conditions']),'risk_flags':list(candidate['risk_flags']),'risk_outcome':risk.get('outcome'),'sizing_outcome':sizing.get('outcome'),'simulated_volume_lots':sizing.get('volume_lots') if action!='NO_TRADE' else None,'refusal_reasons':sorted(set(reasons)),'order_submission':'STRUCTURALLY_DISABLED'}


def drill_intents(root: Path) -> dict[str, Any]:
    _,policy_sha=load_policy(root); risks={x['intent_id']:x for x in drill(root)['results']}; sizes={x['intent_id']:x for x in drill_sizing(root)['results']}
    base={'advisory_score':72,'calibration_status':'CALIBRATED','decision_data_at_utc':'2026-09-11T12:00:00Z','entry_window_start_utc':'2026-09-11T12:01:00Z','entry_window_end_utc':'2026-09-11T12:10:00Z','invalidating_conditions':['event blackout','risk refusal'],'risk_flags':[]}
    return {'marker':'FOREX_M24_INTENT_DRILL_OK','policy_sha256':policy_sha,'results':[orchestrate({'intent_id':'buy',**base,'direction':'BUY'},risk=risks['allowed'],sizing=sizes['sized'],flat_by_hour_utc=18),orchestrate({'intent_id':'sell',**base,'direction':'SELL'},risk=risks['allowed'],sizing=sizes['sized'],flat_by_hour_utc=18),orchestrate({'intent_id':'no-trade',**base,'direction':'NO_TRADE'},risk=risks['allowed'],sizing=sizes['sized'],flat_by_hour_utc=18),orchestrate({'intent_id':'risk-refused',**base,'direction':'BUY'},risk=risks['loss'],sizing=sizes['risk-refused'],flat_by_hour_utc=18)]}
