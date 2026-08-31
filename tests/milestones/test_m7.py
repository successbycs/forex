import json
from pathlib import Path


ROOT = Path(__file__).parents[2]


def test_m7_candidate_registry_is_explicit_and_non_adopting():
    registry = json.loads((ROOT / "config/source_qualification.json").read_text())
    assert registry["schema_version"] == "forex.source-qualification.v1"
    candidates = {entry["source_id"]: entry for entry in registry["candidates"]}
    assert set(candidates) == {
        "fred-alfred-us-macro",
        "ecb-data-portal-euro-macro",
        "trading-economics-calendar",
        "gdelt-sentiment-prototype",
    }
    assert candidates["trading-economics-calendar"]["decision"] == "NOT_ADOPTED_MVP"
    assert candidates["gdelt-sentiment-prototype"]["decision"] == "EXPERIMENTAL_AGGREGATES_ONLY"
    for candidate in candidates.values():
        assert candidate["endpoint"].startswith("https://")
        assert candidate["licence_constraint"]
        assert candidate["timing_and_revisions"]
        assert candidate["retention"]
        assert candidate["adoption_gate"].startswith("M")


def test_m7_does_not_create_generic_download_or_execution_surface():
    capture = (ROOT / "scripts/capture_m7_evidence.sh").read_text()
    proof = (ROOT / "docs/milestones/M7-proof.md").read_text()
    assert "curl" in capture
    assert "GOMarketsMU-Live" not in capture
    assert "place_order" not in capture.lower()
    assert "not a downloader" in proof
