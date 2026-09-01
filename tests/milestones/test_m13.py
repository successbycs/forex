import pytest
from forex.replay import align_at_cutoff


def test_m13_excludes_context_not_available_at_cutoff():
    bars=[{'time_utc':'2026-01-01T00:00:00Z','available_at_utc':'2026-01-01T01:00:00Z'}]
    contexts=[{'available_at_utc':'2026-01-01T01:00:00Z'},{'available_at_utc':'2026-01-01T02:00:00Z'}]
    result=align_at_cutoff(bars,contexts,'2026-01-01T01:00:00Z')
    assert result['context_count']==1 and result['no_lookahead'] is True
    with pytest.raises(ValueError): align_at_cutoff([],contexts,'2026-01-01T01:00:00Z')
