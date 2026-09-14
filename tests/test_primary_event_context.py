import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from forex.primary_event_context import PrimaryEventContextError, load_contract, qualify_context


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "config" / "primary_event_context.json"


def observation(source_id, *, family_id=None, state="RETAINED", coverage="COMPLETE", digest="a"):
    urls = {item["source_id"]: item["source_url"] for item in load_contract(CONTRACT_PATH)["required_families"]}
    url = "https://www.bls.gov/schedule/2026/09_sched_list.htm" if source_id == "bls-monthly-release-calendar" else urls[source_id]
    result = {"source_id": source_id, "source_url": url, "capture_state": state, "coverage_status": coverage,
            "captured_at_utc": "2026-09-13T00:00:00Z", "source_sha256": "sha256:" + digest * 64}
    return result if family_id is None else {**result, "family_id": family_id}


def complete_observations():
    return [observation("bls-monthly-release-calendar", family_id="US_CPI", digest="a"),
            observation("bls-monthly-release-calendar", family_id="US_EMPLOYMENT_SITUATION", digest="d"),
            observation("federal-reserve-fomc-calendar", digest="b"),
            observation("ecb-monetary-policy-calendar", digest="c")]


def test_contract_declares_complete_first_party_eurusd_set_without_authority():
    contract = load_contract(CONTRACT_PATH)
    assert {item["family_id"] for item in contract["required_families"]} == {
        "US_CPI", "US_EMPLOYMENT_SITUATION", "FOMC_POLICY_DECISION", "ECB_POLICY_DECISION"}
    assert contract["execution_authority"] is False
    assert all(item["source_url"].startswith("https://") for item in contract["required_families"])


def test_context_reports_unavailable_when_fomc_and_ecb_have_no_retained_observation():
    report = qualify_context(contract=load_contract(CONTRACT_PATH), observations=[
        observation("bls-monthly-release-calendar", family_id="US_CPI", coverage="UNKNOWN"),
        observation("bls-monthly-release-calendar", family_id="US_EMPLOYMENT_SITUATION", coverage="UNKNOWN", digest="d")])
    assert report["context_state"] == "UNAVAILABLE"
    states = {item["family_id"]: item["state"] for item in report["families"]}
    assert states == {"US_CPI": "PARTIAL", "US_EMPLOYMENT_SITUATION": "PARTIAL",
                      "FOMC_POLICY_DECISION": "UNAVAILABLE", "ECB_POLICY_DECISION": "UNAVAILABLE"}
    assert report["execution_authority"] is False
    assert not ({"allow", "block", "trade", "action"} & set(report))


def test_context_reports_ambiguous_duplicate_source_observation_fail_closed():
    observations = complete_observations()
    observations.append(observation("federal-reserve-fomc-calendar", digest="d"))
    report = qualify_context(contract=load_contract(CONTRACT_PATH), observations=observations)
    assert report["context_state"] == "AMBIGUOUS"
    assert next(row for row in report["families"] if row["family_id"] == "FOMC_POLICY_DECISION")["reason"] == "MULTIPLE_SOURCE_OBSERVATIONS"


def test_approved_fomc_and_ecb_contract_is_context_only_when_complete_observations_exist():
    report = qualify_context(contract=load_contract(CONTRACT_PATH), observations=complete_observations())
    assert report["context_state"] == "QUALIFIED_CONTEXT_ONLY"
    states = {row["family_id"]: (row["state"], row["reason"]) for row in report["families"]}
    assert states["FOMC_POLICY_DECISION"] == ("QUALIFIED_CONTEXT_ONLY", "RETAINED_COMPLETE_SOURCE_COVERAGE")
    assert states["ECB_POLICY_DECISION"] == ("QUALIFIED_CONTEXT_ONLY", "RETAINED_COMPLETE_SOURCE_COVERAGE")


def test_context_refuses_an_observation_url_that_does_not_match_its_contract_source():
    observations = complete_observations()
    observations[0]["source_url"] = "https://example.invalid/calendar"
    report = qualify_context(contract=load_contract(CONTRACT_PATH), observations=observations)
    cpi = next(row for row in report["families"] if row["family_id"] == "US_CPI")
    assert (cpi["state"], cpi["reason"]) == ("AMBIGUOUS", "SOURCE_URL_DOES_NOT_MATCH_CONTRACT")


@pytest.mark.parametrize("mutate, message", [
    (lambda observations: observations.__setitem__(0, {**observations[0], "source_sha256": "bad"}), "observation identity"),
    (lambda observations: observations.__setitem__(0, {**observations[0], "captured_at_utc": "not-time"}), "timestamp"),
])
def test_context_refuses_malformed_retained_observations(mutate, message):
    observations = complete_observations(); mutate(observations)
    with pytest.raises(PrimaryEventContextError, match=message):
        qualify_context(contract=load_contract(CONTRACT_PATH), observations=observations)


def test_context_refuses_missing_or_duplicate_contract_family(tmp_path):
    contract = load_contract(CONTRACT_PATH)
    broken = copy.deepcopy(contract); broken["required_families"].pop()
    with pytest.raises(PrimaryEventContextError, match="complete EUR/USD"):
        qualify_context(contract=broken, observations=[])
    broken = copy.deepcopy(contract); broken["required_families"].append(copy.deepcopy(broken["required_families"][0]))
    path = tmp_path / "broken.json"; path.write_text(json.dumps(broken))
    with pytest.raises(PrimaryEventContextError, match="family"):
        load_contract(path)


def test_cli_uses_only_supplied_local_observations_and_never_fetches(tmp_path):
    observations = tmp_path / "observations.json"; observations.write_text(json.dumps(complete_observations()))
    script = ROOT / "scripts" / "primary_event_context.py"
    before = observations.read_bytes()
    result = subprocess.run([sys.executable, str(script), "--observations", str(observations)], cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert observations.read_bytes() == before
    assert json.loads(result.stdout)["context_state"] == "QUALIFIED_CONTEXT_ONLY"
    source = script.read_text()
    assert "requests" not in source and "urllib" not in source and "t480_adapter" not in source and "subprocess" not in source
