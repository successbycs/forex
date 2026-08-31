from pathlib import Path


ROOT = Path(__file__).parents[2]


def test_m6_fixed_probe_covers_declared_closed_timeframes_only():
    probe = (ROOT / "t480" / "m6_mt5_multi_timeframe_probe.py").read_text()
    assert 'TIMEFRAMES = (("M15", mt5.TIMEFRAME_M15, 720), ("H1", mt5.TIMEFRAME_H1, 720), ("D1", mt5.TIMEFRAME_D1, 365))' in probe
    assert 'copy_rates_from_pos(SYMBOL, timeframe, 1, count)' in probe
    assert 'GOMarketsMU-Demo' in probe
    assert 'order' not in probe.lower()
