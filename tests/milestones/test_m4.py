from forex.data_contracts import build_dataset_snapshot
from forex.research_data import historical_bars


def test_historical_research_boundary_returns_only_point_in_time_bars():
    source={"contract_version":"forex.historical-data.v1","source_id":"demo","owner":"demo","license":"demo","cost_model":"demo","api_version":"demo","endpoint_allowlist":[],"rate_limit":"demo","retention_rule":"demo","historical_depth":"demo","revision_support":"demo","timezone_policy":"UTC","outage_policy":"demo","approval_status":"DEMO_ONLY","secrets_reference":"NONE","provenance_note":"demo"}
    obs={"contract_version":"forex.historical-data.v1","observation_id":"obs","source_id":"demo","source_revision":"x","observed_at_utc":"2026-01-01T00:00:00Z","available_at_utc":"2026-01-01T02:00:00Z","retrieved_at_utc":"2026-01-01T02:00:00Z","timezone":"UTC","payload_sha256":"sha256:x","payload_path":"x","redacted":True}
    bar={"time_utc":"2026-01-01T01:00:00Z","open":1.0,"high":1.1,"low":0.9,"close":1.0,"volume":1,"raw_observation_id":"obs","available_at_utc":"2026-01-01T02:00:00Z"}
    snapshot=build_dataset_snapshot(snapshot_id="m4",instrument="EUR/USD",timeframe="H1",decision_cutoff_utc="2026-01-01T02:00:00Z",created_at_utc="2026-01-01T02:00:00Z",source_registry=[source],raw_observations=[obs],price_bars=[bar])
    assert historical_bars(snapshot,"2026-01-01T02:00:00Z")==[bar]
