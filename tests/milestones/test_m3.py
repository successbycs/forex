import json
from pathlib import Path

from scripts import t480_adapter


ROOT = Path(__file__).resolve().parents[2]


def test_m3_history_depth_probe_is_fixed_read_only_and_demo_only():
    probe = (ROOT / "t480" / "m3_mt5_history_depth_probe.py").read_text(encoding="utf-8")
    assert 'SYMBOL = "EURUSD"' in probe
    assert 'TIMEFRAME_NAME = "H1"' in probe
    assert "REQUESTED_CLOSED_BARS = 100_000" in probe
    assert 'account.server != "GOMarketsMU-Demo"' in probe
    assert "copy_rates_from_pos(SYMBOL, TIMEFRAME, 1, REQUESTED_CLOSED_BARS)" in probe
    assert "order_send" not in probe
    assert "symbol_info_tick" not in probe
    assert "account_info()" in probe


def test_m3_adapter_operation_has_no_argument_or_command_surface():
    operation = t480_adapter.OPERATIONS["m3_mt5_history_depth_probe"]
    command = operation.powershell_command or ""
    assert operation.approval_required is False
    assert "forex-m3-probe" in command
    assert "m3_mt5_history_depth_probe.py" in command
    assert "--command" not in t480_adapter.parser().format_help()
    assert "--script" not in t480_adapter.parser().format_help()


def test_m3_result_schema_binds_the_only_permitted_query():
    schema = json.loads((ROOT / "config" / "schemas" / "mt5-probe-result.schema.json").read_text(encoding="utf-8"))
    assert schema["properties"]["server"]["const"] == "GOMarketsMU-Demo"
    assert schema["properties"]["symbol"]["const"] == "EURUSD"
    assert schema["properties"]["timeframe"]["const"] == "H1"
    assert schema["properties"]["requested_closed_bars"]["const"] == 100000


def test_m3_local_example_includes_windows_terminal_and_python_paths():
    config = json.loads((ROOT / "t480" / "mt5.local.example.json").read_text(encoding="utf-8"))
    assert config["schema_version"] == "forex.mt5-local.v3"
    assert config["terminal_path"].lower().endswith("terminal64.exe")
    assert config["python_path"].lower().endswith("python.exe")
