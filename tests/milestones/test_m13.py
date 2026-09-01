import pytest
from pathlib import Path
from forex.replay import align_at_cutoff


def test_m13_excludes_context_not_available_at_cutoff():
    bars=[{'time_utc':'2026-01-01T00:00:00Z','available_at_utc':'2026-01-01T01:00:00Z'}]
    contexts=[{'time_utc':'2026-01-01T01:00:00Z','available_at_utc':'2026-01-01T01:00:00Z'},{'time_utc':'2026-01-01T02:00:00Z','available_at_utc':'2026-01-01T00:30:00Z'}]
    result=align_at_cutoff(bars,contexts,'2026-01-01T01:00:00Z')
    assert result['context_count']==1 and result['no_lookahead'] is True
    with pytest.raises(ValueError): align_at_cutoff([],contexts,'2026-01-01T01:00:00Z')


def test_m13_excludes_future_price_timestamp_even_if_available_early():
    bars=[
        {'time_utc':'2026-01-01T00:00:00Z','available_at_utc':'2026-01-01T00:30:00Z'},
        {'time_utc':'2026-01-01T02:00:00Z','available_at_utc':'2026-01-01T00:30:00Z'},
    ]
    result=align_at_cutoff(bars, [], '2026-01-01T01:00:00Z')
    assert result['bar_count']==1
    assert result['latest_bar_utc']=='2026-01-01T00:00:00Z'


def test_m13_fixed_t480_query_requires_daily_alignment_and_lineage():
    query=(Path(__file__).parents[2]/'sql'/'m13_postgres_replay.sql').read_text()
    assert "price_daily AS" in query and "context_daily AS" in query and "aligned AS" in query
    assert "dataset_snapshot_observation" in query
    assert "context_lineage_ok" in query and "future_context_records" in query
