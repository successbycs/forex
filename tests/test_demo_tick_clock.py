"""Execute the exact remote read-only payload against controlled MT5 responses."""

import datetime as datetime_module
import json
import sys
from types import SimpleNamespace

import pytest

from scripts import t480_adapter


@pytest.mark.parametrize(
    'offset,age,server,bid,ask,expected',
    [
        (10800, 2, 'GOMarketsMU-Demo', 1.1, 1.1001, 0),
        (7200, 2, 'GOMarketsMU-Demo', 1.1, 1.1001, 0),
        (10800, 0, 'GOMarketsMU-Demo', 1.1, 1.1001, 0),
        (10800, 15, 'GOMarketsMU-Demo', 1.1, 1.1001, 0),
        (10800, 16, 'GOMarketsMU-Demo', 1.1, 1.1001, 3),
        # The previous nearest-offset heuristic turned this stale tick fresh.
        (10800, 3602, 'GOMarketsMU-Demo', 1.1, 1.1001, 3),
        (10800, -1, 'GOMarketsMU-Demo', 1.1, 1.1001, 3),
        (10800, 2, 'GOMarketsMU-Live', 1.1, 1.1001, 3),
        (10800, 2, 'GOMarketsMU-Demo', 1.1, 1.0, 3),
        (10800, 2, 'GOMarketsMU-Demo', 0, 1.1001, 3),
        (10800, 2, 'GOMarketsMU-Demo', float('nan'), 1.1001, 3),
        (10800, 2, 'GOMarketsMU-Demo', 1.1, float('inf'), 3),
    ],
)
def test_fixed_probe_clock(monkeypatch, capsys, offset, age, server, bid, ask, expected):
    now = datetime_module.datetime(2026, 9, 12, tzinfo=datetime_module.timezone.utc)

    class FrozenDatetime(datetime_module.datetime):
        @classmethod
        def now(cls, tz=None):
            return now

    monkeypatch.setattr(datetime_module, 'datetime', FrozenDatetime)
    monkeypatch.setattr(t480_adapter, 'load_configuration', lambda *a, **k: SimpleNamespace(
        mt5=SimpleNamespace(broker_tick_time_offset_seconds=offset)))
    command = t480_adapter._m27_demo_tick_command()
    code = command.split(" -c '", 1)[1].rsplit("' $s.terminal_path", 1)[0].replace("''", "'")
    calls = []

    def quote(symbol):
        calls.append(symbol)
        return SimpleNamespace(bid=bid, ask=ask, time_msc=int((now.timestamp() + offset - age) * 1000))

    fake = SimpleNamespace(
        initialize=lambda **k: True,
        account_info=lambda: SimpleNamespace(server=server),
        symbol_info_tick=quote,
        shutdown=lambda: calls.append('shutdown'),
    )
    monkeypatch.setitem(sys.modules, 'MetaTrader5', fake)
    monkeypatch.setattr(sys, 'argv', ['probe', 'demo-terminal'])
    with pytest.raises(SystemExit) as result:
        exec(compile(code, '<fixed Demo probe>', 'exec'), {})
    assert result.value.code == expected
    payload = json.loads(capsys.readouterr().out)
    assert payload['ok'] is (expected == 0)
    assert payload['broker_timestamp_offset_seconds'] == offset
    assert payload['broker_timestamp_offset_source'] == 'governed_configuration'
    assert calls == (['shutdown'] if server != 'GOMarketsMU-Demo' else ['EURUSD', 'shutdown'])
    if age == 3602:
        assert payload['tick_age_seconds'] == 3602
