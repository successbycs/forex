from forex.calendar_events import FRED_RELEASE_ID

def test_m10_free_source_path_has_explicit_time_precision_limits():
    source=open('src/forex/calendar_events.py').read()
    assert FRED_RELEASE_ID == 10
    assert 'DATE_ONLY' in source and 'CET_SCHEDULED_TIME' in source
    assert 'place_order' not in source.lower()
