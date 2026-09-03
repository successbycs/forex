from __future__ import annotations

from pathlib import Path
import shutil

import pytest
import yaml

from forex.config import ConfigurationError, FILES, load_configuration


ROOT = Path(__file__).resolve().parents[1]


def _configuration_copy(tmp_path: Path) -> Path:
    (tmp_path / "config").mkdir()
    for name in FILES:
        shutil.copy2(ROOT / "config" / f"{name}.yaml", tmp_path / "config" / f"{name}.yaml")
    shutil.copytree(ROOT / "config" / "schemas", tmp_path / "config" / "schemas")
    return tmp_path


def _rewrite(root: Path, name: str, **changes: object) -> None:
    path = root / "config" / f"{name}.yaml"
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    value.update(changes)
    path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")


def test_all_initial_configuration_loads_as_typed_models() -> None:
    configuration = load_configuration(ROOT, environ={})
    assert configuration.project.canonical_instrument == "EUR/USD"
    assert configuration.runtime.runtime_mode == "DEMO_TRADING"
    assert configuration.runtime.agent_authority_mode == "DEMO_SESSION_BOUNDED"
    assert configuration.mt5.allow_demo_order_operations is True
    assert configuration.mt5.allow_live_server is False
    assert configuration.mt5.demo_credentials_environment_variable == "FOREX_MT5_DEMO_CREDENTIALS"
    assert configuration.mt5.broker_tick_time_offset_seconds == 10800
    limits = configuration.runtime.demo_session_limits
    assert limits.maximum_trades == 10
    assert limits.maximum_duration_minutes == 60
    assert limits.maximum_open_positions == 1
    assert limits.maximum_notional_per_trade_usd == 10000
    assert limits.maximum_cumulative_notional_usd == 100000
    assert limits.maximum_loss_per_trade_aud == 100
    assert limits.require_persisted_proposal is True
    assert limits.require_idempotency_key is True
    assert configuration.agent.mode == "DEMO_SESSION_CONTEXT"
    assert configuration.agent.allowed_context_sections == (
        "fresh_tick",
        "closed_m1_candles",
        "closed_m5_candles",
        "research_features",
        "demo_session_limits",
    )
    assert configuration.agent.forbidden_context_sections == (
        "future_bars",
        "account",
        "credentials",
        "mt5_control",
        "generic_mt5",
        "shell",
        "order",
        "execution",
    )
    assert configuration.models.provider == "OLLAMA"
    assert configuration.models.model_id == "qwen2.5:3b"
    assert configuration.models.inference_enabled is True
    assert configuration.fingerprint.startswith("sha256:")


def test_unknown_fields_are_rejected(tmp_path: Path) -> None:
    root = _configuration_copy(tmp_path)
    _rewrite(root, "runtime", unexpected=True)
    with pytest.raises(ConfigurationError, match="Additional properties"):
        load_configuration(root, environ={})


@pytest.mark.parametrize(
    ("document", "change"),
    [
        ("runtime", {"runtime_mode": "RESEARCH"}),
        ("runtime", {"agent_authority_mode": "DISABLED"}),
        ("runtime", {"live_trading_enabled": True}),
        ("mt5", {"permitted_server": "GOMarketsMU-Live"}),
        ("mt5", {"allow_live_server": True}),
        ("mt5", {"broker_tick_time_offset_seconds": 50401}),
        ("agent", {"mode": "OFFLINE_CONTEXT_ONLY"}),
    ],
)
def test_unsafe_runtime_and_mt5_changes_are_rejected(
    tmp_path: Path, document: str, change: dict[str, object]
) -> None:
    root = _configuration_copy(tmp_path)
    _rewrite(root, document, **change)
    with pytest.raises(ConfigurationError):
        load_configuration(root, environ={})


@pytest.mark.parametrize(
    ("change"),
    [
        {"maximum_trades": 11},
        {"maximum_duration_minutes": 61},
        {"maximum_open_positions": 2},
        {"maximum_notional_per_trade_usd": 10001},
        {"maximum_cumulative_notional_usd": 100001},
        {"maximum_loss_per_trade_aud": 101},
        {"require_persisted_proposal": False},
        {"require_idempotency_key": False},
    ],
)
def test_demo_session_limits_fail_closed_at_the_m20_caps(tmp_path: Path, change: dict[str, object]) -> None:
    root = _configuration_copy(tmp_path)
    runtime_path = root / "config" / "runtime.yaml"
    runtime = yaml.safe_load(runtime_path.read_text(encoding="utf-8"))
    runtime["demo_session_limits"].update(change)
    runtime_path.write_text(yaml.safe_dump(runtime, sort_keys=False), encoding="utf-8")
    with pytest.raises(ConfigurationError):
        load_configuration(root, environ={})


def test_demo_session_cumulative_notional_must_cover_one_trade(tmp_path: Path) -> None:
    root = _configuration_copy(tmp_path)
    runtime_path = root / "config" / "runtime.yaml"
    runtime = yaml.safe_load(runtime_path.read_text(encoding="utf-8"))
    runtime["demo_session_limits"]["maximum_cumulative_notional_usd"] = 99
    runtime_path.write_text(yaml.safe_dump(runtime, sort_keys=False), encoding="utf-8")
    with pytest.raises(ConfigurationError, match="cumulative notional"):
        load_configuration(root, environ={})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("allowed_context_sections", ["fresh_tick", "closed_m1_candles", "closed_m5_candles", "research_features", "account"]),
        ("forbidden_context_sections", ["future_bars", "account", "credentials", "mt5_control", "generic_mt5", "shell", "order"]),
    ],
)
def test_demo_agent_context_rejects_account_and_generic_control_surface(
    tmp_path: Path, field: str, value: list[str]
) -> None:
    root = _configuration_copy(tmp_path)
    _rewrite(root, "agent", **{field: value})
    with pytest.raises(ConfigurationError):
        load_configuration(root, environ={})


def test_only_documented_safe_environment_override_is_applied() -> None:
    configuration = load_configuration(
        ROOT,
        environ={
            "FOREX_LOG_LEVEL": "ERROR",
            "FOREX_RUNTIME_MODE": "LIVE",
            "FOREX_LIVE_TRADING_ENABLED": "true",
        },
    )
    assert configuration.logging.level == "ERROR"
    assert configuration.runtime.runtime_mode == "DEMO_TRADING"
    assert configuration.runtime.live_trading_enabled is False


def test_invalid_safe_override_still_fails_schema_validation() -> None:
    with pytest.raises(ConfigurationError):
        load_configuration(ROOT, environ={"FOREX_LOG_LEVEL": "TRACE"})


@pytest.mark.parametrize(
    ("change"),
    [
        {"model_id": "qwen2.5:7b"},
        {"provider": "OTHER"},
        {"inference_enabled": False},
        {"training_enabled": True},
    ],
)
def test_only_the_fixed_m18_local_model_configuration_is_allowed(tmp_path: Path, change: dict[str, object]) -> None:
    root = _configuration_copy(tmp_path)
    _rewrite(root, "models", **change)
    with pytest.raises(ConfigurationError):
        load_configuration(root, environ={})
