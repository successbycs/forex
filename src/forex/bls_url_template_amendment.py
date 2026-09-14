"""Pure validation/reporting for a non-active BLS URL-template draft."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from forex.primary_event_context import PrimaryEventContextError, load_contract


SCHEMA = "forex.primary-event-context-url-template-amendment-draft.v1"
STATUS = "DRAFT_NOT_ACTIVE"
TEMPLATE = "https://www.bls.gov/schedule/{year}/{month:02d}_sched_list.htm"
_URL = re.compile(r"https://www\.bls\.gov/schedule/(20\d{2})/(0[1-9]|1[0-2])_sched_list\.htm\Z")
_FIELDS = {"schema_version", "status", "execution_authority", "human_approval_required", "baseline_schema_version", "amendments"}
_AMENDMENT_FIELDS = {"family_id", "source_id", "source_url_template", "matching_policy", "coverage_status", "unavailable_source_handling", "execution_authority"}
_FAMILIES = {"US_CPI", "US_EMPLOYMENT_SITUATION"}


class BLSURLTemplateAmendmentError(ValueError):
    """The candidate is not the bounded, inactive amendment draft."""


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise BLSURLTemplateAmendmentError("duplicate draft JSON field")
        result[key] = value
    return result


def _constant(value: str) -> None:
    raise BLSURLTemplateAmendmentError("nonfinite draft JSON value")


def load_draft(path: Path) -> dict[str, Any]:
    if not isinstance(path, Path) or not path.is_file() or path.is_symlink():
        raise BLSURLTemplateAmendmentError("draft must be a regular non-symlink file")
    try:
        draft = json.loads(path.read_bytes(), object_pairs_hook=_unique, parse_constant=_constant)
    except (OSError, json.JSONDecodeError) as exc:
        raise BLSURLTemplateAmendmentError("draft JSON is invalid") from exc
    return validate_draft(draft)


def validate_draft(draft: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(draft, dict) or set(draft) != _FIELDS:
        raise BLSURLTemplateAmendmentError("draft shape is invalid")
    if (draft.get("schema_version") != SCHEMA or draft.get("status") != STATUS
            or draft.get("execution_authority") is not False
            or draft.get("baseline_schema_version") != "forex.primary-event-context.v1"
            or not isinstance(draft.get("human_approval_required"), str) or not draft["human_approval_required"]):
        raise BLSURLTemplateAmendmentError("draft identity or authority is invalid")
    amendments = draft.get("amendments")
    if not isinstance(amendments, list) or len(amendments) != 2:
        raise BLSURLTemplateAmendmentError("draft must define exactly the two BLS primary families")
    seen: set[str] = set()
    for row in amendments:
        if not isinstance(row, dict) or set(row) != _AMENDMENT_FIELDS:
            raise BLSURLTemplateAmendmentError("draft amendment shape is invalid")
        if (row.get("family_id") not in _FAMILIES or row["family_id"] in seen
                or row.get("source_id") != "bls-monthly-release-calendar"
                or row.get("source_url_template") != TEMPLATE
                or row.get("matching_policy") != "EXACT_BLS_MONTHLY_URL_TEMPLATE_ONLY"
                or row.get("coverage_status") != "UNKNOWN"
                or row.get("unavailable_source_handling") != "UNAVAILABLE"
                or row.get("execution_authority") is not False):
            raise BLSURLTemplateAmendmentError("draft amendment widens matching or changes safety semantics")
        seen.add(row["family_id"])
    if seen != _FAMILIES:
        raise BLSURLTemplateAmendmentError("draft family set is invalid")
    return json.loads(json.dumps(draft))


def matches_candidate(*, amendment: dict[str, Any], observation: dict[str, Any]) -> bool:
    """Check only the exact bounded monthly URL/source pairing in a candidate."""
    validate_draft({"schema_version": SCHEMA, "status": STATUS, "execution_authority": False,
                    "human_approval_required": "validation wrapper", "baseline_schema_version": "forex.primary-event-context.v1",
                    "amendments": [amendment, {**amendment, "family_id": "US_EMPLOYMENT_SITUATION" if amendment.get("family_id") == "US_CPI" else "US_CPI"}]})
    return (isinstance(observation, dict) and observation.get("source_id") == amendment["source_id"]
            and isinstance(observation.get("source_url"), str) and _URL.fullmatch(observation["source_url"]) is not None
            and observation.get("coverage_status") == "UNKNOWN" and observation.get("capture_state") == "RETAINED")


def report_amendment(*, baseline_contract: dict[str, Any], draft: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """Display a proposed structural delta; never activate or modify either input."""
    try:
        # Existing public validator is intentionally used on direct values.
        from forex.primary_event_context import qualify_context
        qualify_context(contract=baseline_contract, observations=[])
    except PrimaryEventContextError as exc:
        raise BLSURLTemplateAmendmentError("baseline contract is invalid") from exc
    draft = validate_draft(draft)
    if not isinstance(candidates, list) or not all(isinstance(row, dict) for row in candidates):
        raise BLSURLTemplateAmendmentError("candidate observations must be a list")
    baseline = {row["family_id"]: row for row in baseline_contract["required_families"]}
    delta = []
    matches = []
    for amendment in sorted(draft["amendments"], key=lambda item: item["family_id"]):
        source = baseline.get(amendment["family_id"])
        if source is None or source.get("source_id") != amendment["source_id"] or source.get("source_url") != TEMPLATE:
            raise BLSURLTemplateAmendmentError("baseline BLS family does not match bounded draft target")
        delta.append({"family_id": amendment["family_id"], "before_source_url": source["source_url"],
                      "after_matching_policy": amendment["matching_policy"], "after_source_url_template": TEMPLATE,
                      "coverage_status": "UNKNOWN", "execution_authority": False})
        for candidate in candidates:
            if candidate.get("family_id") == amendment["family_id"] and matches_candidate(amendment=amendment, observation=candidate.get("observation", {})):
                matches.append({"family_id": amendment["family_id"], "event_id": candidate.get("event_id"), "source_url": candidate["observation"]["source_url"], "matched": True})
    return {"schema_version": SCHEMA, "status": STATUS, "execution_authority": False,
            "human_approval_required": draft["human_approval_required"], "structural_delta": delta,
            "matching_candidates": matches, "activation": "NOT_APPLIED"}
