"""Typed, schema-validated operator configuration for Forex M0."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker
import yaml


FILES = ("project", "runtime", "mt5", "market_data", "logging")
SAFE_ENV_OVERRIDES = {
    "FOREX_LOG_LEVEL": ("logging", "level"),
}


class ConfigurationError(ValueError):
    """Configuration is malformed or violates a hard safety invariant."""


@dataclass(frozen=True)
class ProjectConfig:
    project: str
    repository: str
    purpose: str
    canonical_instrument: str
    expected_broker_symbol: str
    broker: str
    permitted_mt5_server: str
    forbidden_mt5_server: str
    initial_research_capital_usd: int
    aspirational_monthly_average_usd: int


@dataclass(frozen=True)
class RuntimeConfig:
    environment: str
    runtime_mode: str
    agent_authority_mode: str
    live_trading_enabled: bool
    maximum_concurrent_positions: int


@dataclass(frozen=True)
class MT5Config:
    platform: str
    canonical_instrument: str
    expected_broker_symbol: str
    permitted_server: str
    forbidden_server: str
    allow_order_operations: bool
    allow_live_server: bool
    terminal_path_environment_variable: str


@dataclass(frozen=True)
class MarketDataConfig:
    canonical_instrument: str
    timezone: str
    primary_timeframe: str
    incomplete_bar_policy: str
    tick_stale_after_seconds: int


@dataclass(frozen=True)
class LoggingConfig:
    level: str
    format: str
    output_directory: str
    redacted_fields: tuple[str, ...]


@dataclass(frozen=True)
class ForexConfiguration:
    project: ProjectConfig
    runtime: RuntimeConfig
    mt5: MT5Config
    market_data: MarketDataConfig
    logging: LoggingConfig
    effective_non_secret: dict[str, Any]
    fingerprint: str


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigurationError(f"missing configuration file: {path}") from exc
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"invalid YAML in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ConfigurationError(f"configuration must be a mapping: {path}")
    return value


def _validate_schema(value: dict[str, Any], schema_path: Path, label: str) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(value), key=lambda error: list(error.absolute_path))
    if errors:
        details = "; ".join(
            f"{'.'.join(map(str, error.absolute_path)) or '<root>'}: {error.message}" for error in errors
        )
        raise ConfigurationError(f"{label} configuration failed schema validation: {details}")


def _apply_safe_environment_overrides(values: dict[str, dict[str, Any]], environ: Mapping[str, str]) -> None:
    for variable, (document, field) in SAFE_ENV_OVERRIDES.items():
        if variable in environ and environ[variable]:
            values[document][field] = environ[variable]


def _enforce_safety(values: dict[str, dict[str, Any]]) -> None:
    project = values["project"]
    runtime = values["runtime"]
    mt5 = values["mt5"]
    failures: list[str] = []
    if project["project"] != "Forex" or project["canonical_instrument"] != "EUR/USD":
        failures.append("project identity and canonical instrument are fixed during MVP")
    if project["permitted_mt5_server"] != "GOMarketsMU-Demo":
        failures.append("the only permitted MVP server is GOMarketsMU-Demo")
    if project["forbidden_mt5_server"] != "GOMarketsMU-Live":
        failures.append("GOMarketsMU-Live must remain explicitly forbidden")
    if runtime["runtime_mode"] != "RESEARCH":
        failures.append("M0 runtime mode must remain RESEARCH")
    if runtime["agent_authority_mode"] != "DISABLED":
        failures.append("agent authority must remain DISABLED in M0")
    if runtime["live_trading_enabled"] is not False:
        failures.append("live trading cannot be enabled by configuration")
    if mt5["permitted_server"] != project["permitted_mt5_server"]:
        failures.append("MT5 permitted server must match the project boundary")
    if mt5["forbidden_server"] != project["forbidden_mt5_server"]:
        failures.append("MT5 forbidden server must match the project boundary")
    if mt5["allow_order_operations"] is not False:
        failures.append("order operations must remain unavailable before M27")
    if mt5["allow_live_server"] is not False:
        failures.append("live-server access cannot be enabled by configuration")
    if failures:
        raise ConfigurationError("; ".join(failures))


def load_configuration(root: Path, environ: Mapping[str, str] | None = None) -> ForexConfiguration:
    root = root.resolve()
    values = {name: _load_yaml(root / "config" / f"{name}.yaml") for name in FILES}
    _apply_safe_environment_overrides(values, os.environ if environ is None else environ)
    for name, value in values.items():
        _validate_schema(value, root / "config" / "schemas" / f"{name}.schema.json", name)
    _enforce_safety(values)
    canonical = json.dumps(values, sort_keys=True, separators=(",", ":")).encode("utf-8")
    fingerprint = f"sha256:{hashlib.sha256(canonical).hexdigest()}"
    return ForexConfiguration(
        project=ProjectConfig(**{key: value for key, value in values["project"].items() if key != "schema_version"}),
        runtime=RuntimeConfig(**{key: value for key, value in values["runtime"].items() if key != "schema_version"}),
        mt5=MT5Config(**{key: value for key, value in values["mt5"].items() if key != "schema_version"}),
        market_data=MarketDataConfig(**{key: value for key, value in values["market_data"].items() if key != "schema_version"}),
        logging=LoggingConfig(
            **{
                key: tuple(value) if key == "redacted_fields" else value
                for key, value in values["logging"].items()
                if key != "schema_version"
            }
        ),
        effective_non_secret=values,
        fingerprint=fingerprint,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Forex operator configuration")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        configuration = load_configuration(args.root)
    except (ConfigurationError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 2
    result = {
        "project": configuration.project.project,
        "runtime_mode": configuration.runtime.runtime_mode,
        "live_trading_enabled": configuration.runtime.live_trading_enabled,
        "agent_authority_mode": configuration.runtime.agent_authority_mode,
        "permitted_mt5_server": configuration.mt5.permitted_server,
        "configuration_fingerprint": configuration.fingerprint,
    }
    print(json.dumps(result, indent=2) if args.json else f"Forex configuration valid: {configuration.fingerprint}")
    return 0
