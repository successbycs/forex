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
    assert configuration.runtime.runtime_mode == "RESEARCH"
    assert configuration.mt5.allow_order_operations is False
    assert configuration.agent.mode == "OFFLINE_CONTEXT_ONLY"
    assert configuration.models.inference_enabled is False
    assert configuration.fingerprint.startswith("sha256:")


def test_unknown_fields_are_rejected(tmp_path: Path) -> None:
    root = _configuration_copy(tmp_path)
    _rewrite(root, "runtime", unexpected=True)
    with pytest.raises(ConfigurationError, match="Additional properties"):
        load_configuration(root, environ={})


@pytest.mark.parametrize(
    ("document", "change"),
    [
        ("runtime", {"runtime_mode": "LIVE"}),
        ("runtime", {"live_trading_enabled": True}),
        ("mt5", {"permitted_server": "GOMarketsMU-Live"}),
        ("mt5", {"allow_order_operations": True}),
        ("mt5", {"allow_live_server": True}),
    ],
)
def test_unsafe_runtime_and_mt5_changes_are_rejected(
    tmp_path: Path, document: str, change: dict[str, object]
) -> None:
    root = _configuration_copy(tmp_path)
    _rewrite(root, document, **change)
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
    assert configuration.runtime.runtime_mode == "RESEARCH"
    assert configuration.runtime.live_trading_enabled is False


def test_invalid_safe_override_still_fails_schema_validation() -> None:
    with pytest.raises(ConfigurationError):
        load_configuration(ROOT, environ={"FOREX_LOG_LEVEL": "TRACE"})
