"""Non-active FOMC/ECB timing-source qualification amendment preparation."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from forex.first_party_policy_capture import SOURCES
from forex.first_party_policy_source_verifier import PolicySourceVerificationError,verify_policy_timing_store
from forex.first_party_policy_timing import TIMING_URLS
from forex.primary_event_context import PrimaryEventContextError,qualify_context
SCHEMA="forex.primary-event-policy-timing-amendment-draft.v1";STATUS="DRAFT_NOT_ACTIVE"
_FIELDS={"schema_version","status","execution_authority","human_approval_required","baseline_schema_version","amendments"}
_ROW={"family_id","source_id","calendar_url","timing_url","target_date","matching_policy","coverage_status","unavailable_source_handling","execution_authority"}
_TARGETS={"FOMC_POLICY_DECISION":"2026-09-16","ECB_POLICY_DECISION":"2026-10-29"}
class PolicyTimingAmendmentError(ValueError):pass
def _unique(pairs):
 out={}
 for k,v in pairs:
  if k in out:raise PolicyTimingAmendmentError("duplicate draft JSON field")
  out[k]=v
 return out
def _constant(v):raise PolicyTimingAmendmentError("nonfinite draft JSON value")
def validate_draft(draft:dict[str,Any])->dict[str,Any]:
 if not isinstance(draft,dict) or set(draft)!=_FIELDS:raise PolicyTimingAmendmentError("draft shape is invalid")
 if draft.get("schema_version")!=SCHEMA or draft.get("status")!=STATUS or draft.get("execution_authority") is not False or draft.get("baseline_schema_version")!="forex.primary-event-context.v1" or not isinstance(draft.get("human_approval_required"),str) or not draft["human_approval_required"]:raise PolicyTimingAmendmentError("draft identity or authority is invalid")
 rows=draft.get("amendments")
 if not isinstance(rows,list) or len(rows)!=2:raise PolicyTimingAmendmentError("draft must contain two policy families")
 seen=set()
 for row in rows:
  family=row.get("family_id") if isinstance(row,dict) else None
  if not isinstance(row,dict) or set(row)!=_ROW or family not in _TARGETS or family in seen or row.get("source_id")!=SOURCES[family][0] or row.get("calendar_url")!=SOURCES[family][1] or row.get("timing_url")!=TIMING_URLS[family] or row.get("target_date")!=_TARGETS[family] or row.get("matching_policy")!="EXACT_RETAINED_TIMING_MANIFEST_ONLY" or row.get("coverage_status")!="UNKNOWN" or row.get("unavailable_source_handling")!="UNAVAILABLE" or row.get("execution_authority") is not False:raise PolicyTimingAmendmentError("draft row widens source/timing policy or changes safety semantics")
  seen.add(family)
 return json.loads(json.dumps(draft))
def load_draft(path:Path)->dict[str,Any]:
 if not isinstance(path,Path) or path.is_symlink() or not path.is_file():raise PolicyTimingAmendmentError("draft must be a regular non-symlink file")
 try:return validate_draft(json.loads(path.read_bytes(),object_pairs_hook=_unique,parse_constant=_constant))
 except (OSError,json.JSONDecodeError) as exc:raise PolicyTimingAmendmentError("draft JSON is invalid") from exc
def report_amendment(*,baseline_contract:dict[str,Any],draft:dict[str,Any],store_root:Path)->dict[str,Any]:
 try:qualify_context(contract=baseline_contract,observations=[]);verified=verify_policy_timing_store(store_root)
 except (PrimaryEventContextError,PolicySourceVerificationError) as exc:raise PolicyTimingAmendmentError("baseline or retained timing store is invalid") from exc
 draft=validate_draft(draft);by_family={row["family_id"]:row for row in baseline_contract["required_families"]};bundles={(row["family_id"],row["target_date"]):row for row in verified["bundles"]};delta=[];evidence=[]
 for amendment in sorted(draft["amendments"],key=lambda x:x["family_id"]):
  family=amendment["family_id"];before=by_family.get(family);bundle=bundles.get((family,amendment["target_date"]))
  if before is None or before.get("source_id")!=amendment["source_id"] or before.get("source_url")!=amendment["calendar_url"] or before.get("qualification_state") not in {"PENDING_RETAINED_CAPTURE","RETAINED_TIMING_ACTIVE_COVERAGE_UNKNOWN"}:raise PolicyTimingAmendmentError("baseline non-active family does not match draft")
  if bundle is None or bundle["event_record"]["document_provenance"]["timing"]["source_url"]!=amendment["timing_url"] or bundle["event_record"]["document_provenance"]["calendar"]["source_url"]!=amendment["calendar_url"]:raise PolicyTimingAmendmentError("verified retained timing provenance does not match draft")
  delta.append({"family_id":family,"before_qualification_state":"PENDING_RETAINED_CAPTURE","after_matching_policy":amendment["matching_policy"],"coverage_status":"UNKNOWN","execution_authority":False})
  evidence.append(bundle)
 return {"schema_version":SCHEMA,"status":STATUS,"execution_authority":False,"human_approval_required":draft["human_approval_required"],"activation":"NOT_APPLIED","structural_delta":delta,"verified_retained_bundles":evidence,"limitation":"Verified bundles are shown as evidence only; no source is selected, complete, or qualified by this report."}
