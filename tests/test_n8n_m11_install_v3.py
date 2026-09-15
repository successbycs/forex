from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("n8n_m11_install", ROOT / "scripts" / "n8n_m11_install.py")
assert SPEC and SPEC.loader
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


def _write_env(path: Path, mode: int = 0o600, *, same: bool = False) -> None:
    bearer = "a" * 32
    signing = bearer if same else "b" * 32
    path.write_text(
        f"FOREX_GDELT_EGRESS_BEARER={bearer}\nFOREX_GDELT_CANDIDATE_SIGNING_KEY={signing}\n",
        encoding="utf-8",
    )
    os.chmod(path, mode)


def test_private_n8n_env_requires_two_distinct_owner_only_secrets(tmp_path: Path):
    path = tmp_path / "gdelt-n8n.env"
    _write_env(path)
    bearer, signing = tmp_path / "bearer", tmp_path / "signing"
    bearer.write_text("a" * 32); signing.write_text("b" * 32)
    os.chmod(bearer, 0o600); os.chmod(signing, 0o600)
    local_secrets = {"FOREX_GDELT_EGRESS_BEARER": bearer, "FOREX_GDELT_CANDIDATE_SIGNING_KEY": signing}
    installer.require_private_gdelt_n8n_env(path, local_secrets)
    _write_env(path, 0o644)
    with pytest.raises(RuntimeError, match="mode 0600"):
        installer.require_private_gdelt_n8n_env(path, local_secrets)
    _write_env(path, same=True)
    with pytest.raises(RuntimeError, match="invalid"):
        installer.require_private_gdelt_n8n_env(path, local_secrets)


def test_installer_refuses_secret_file_that_does_not_match_n8n_environment(tmp_path: Path):
    path = tmp_path / "gdelt-n8n.env"; _write_env(path)
    bearer, signing = tmp_path / "bearer", tmp_path / "signing"
    bearer.write_text("a" * 32); signing.write_text("x" * 32)
    os.chmod(bearer, 0o600); os.chmod(signing, 0o600)
    with pytest.raises(RuntimeError, match="do not match"):
        installer.require_private_gdelt_n8n_env(path, {"FOREX_GDELT_EGRESS_BEARER": bearer, "FOREX_GDELT_CANDIDATE_SIGNING_KEY": signing})


def test_installer_checks_n8n_has_bearer_and_signing_key_without_echoing_them():
    source = (ROOT / "scripts" / "n8n_m11_install.py").read_text(encoding="utf-8")
    assert "process.env.FOREX_GDELT_EGRESS_BEARER" in source
    assert "process.env.FOREX_GDELT_CANDIDATE_SIGNING_KEY" in source
    assert "print(values" not in source
    assert "REFUSED_HOST" in source and "REFUSED_SIGNATURE" in source
    assert "crypto,net" in (ROOT / "deploy/gdelt/compose.n8n.override.yaml").read_text()


def test_egress_image_build_uses_fixed_forex_root_and_proves_the_label(monkeypatch):
    calls = []
    class Result:
        stdout = '{"org.forex.gdelt.build-sha256":"fixed-build-digest"}'
    monkeypatch.setattr(installer, "gdelt_egress_build_sha256", lambda: "fixed-build-digest")
    def run(arguments, **_kwargs):
        calls.append(arguments)
        return Result()
    monkeypatch.setattr(installer.subprocess, "run", run)
    assert installer.build_gdelt_egress_image() == "fixed-build-digest"
    assert calls[0][:3] == ["docker", "build", "--pull=false"]
    assert str(installer.GDELT_EGRESS_DOCKERFILE) in calls[0]
    assert str(installer.ROOT) == calls[0][-1]
    assert calls[1][:3] == ["docker", "image", "inspect"]


def test_egress_copy_contract_and_compose_install_are_bounded_and_rollbackable():
    dockerfile = (ROOT / "deploy/gdelt/Dockerfile").read_text(encoding="utf-8")
    assert (
        "FROM python:3.12-slim@sha256:"
        "78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea"
    ) in dockerfile
    assert "FROM python:3.12-slim\n" not in dockerfile
    assert "COPY src/forex/gdelt_publisher_egress.py" in dockerfile
    assert "COPY src/forex /opt/forex/forex" not in dockerfile
    source = (ROOT / "scripts/n8n_m11_install.py").read_text(encoding="utf-8")
    assert "apply_gdelt_egress_compose()" in source
    assert "n8n retains an outbound network" in source
    assert '"--force-recreate", "n8n"' in source
    assert '"rm", "-sf", "gdelt-egress"' in source
    compose = (ROOT / "deploy/gdelt/compose.yaml").read_text(encoding="utf-8")
    assert "gdelt-private:" in compose and "internal: true" in compose
    assert "networks: [gdelt-private, gdelt-outbound]" in compose


def test_health_probe_uses_merged_compose_and_returns_a_redacted_status_diagnostic(monkeypatch):
    calls = []

    def run(arguments, **_kwargs):
        calls.append(arguments)
        return SimpleNamespace(
            returncode=1,
            stdout='{"probe":"GDELT_EGRESS_CONTRACT_V1","valid":false,"reason":"N8N_SECRET_ENV_INVALID"}',
            stderr="FOREX_GDELT_EGRESS_BEARER=must-not-escape",
        )

    monkeypatch.setattr(installer.subprocess, "run", run)
    with pytest.raises(RuntimeError, match="GDELT_EGRESS_CONTRACT_V1") as failure:
        installer.require_gdelt_egress()
    assert "must-not-escape" not in str(failure.value)
    assert "[REDACTED]" in str(failure.value)
    command = calls[0]
    assert command[:3] == ["docker", "compose", "-f"]
    assert str(installer.GDELT_EGRESS_COMPOSE) in command
    assert str(installer.GDELT_N8N_COMPOSE_OVERRIDE) in command
    assert command[-4:] == ["n8n", "node", "-e", command[-1]]
    assert "http=require('http')" in command[-1]
    assert "GDELT_EGRESS_CONTRACT_V1" in command[-1]


def test_failed_install_captures_redacted_egress_logs_before_removal(monkeypatch):
    calls = []

    def run(arguments, **_kwargs):
        calls.append(arguments)
        if "logs" in arguments:
            return SimpleNamespace(stdout="egress error FOREX_GDELT_CANDIDATE_SIGNING_KEY=must-not-escape", stderr="")
        return SimpleNamespace(stdout="", stderr="", returncode=0)

    monkeypatch.setattr(installer.subprocess, "run", run)
    monkeypatch.setattr(installer, "_verify_private_egress_topology", lambda: None)
    monkeypatch.setattr(installer, "require_gdelt_egress", lambda: (_ for _ in ()).throw(RuntimeError("probe failed")))
    with pytest.raises(RuntimeError, match="rolled back") as failure:
        installer.apply_gdelt_egress_compose()
    rendered = str(failure.value)
    assert "must-not-escape" not in rendered
    assert "[REDACTED]" in rendered
    log_index = next(index for index, call in enumerate(calls) if "logs" in call)
    remove_index = next(index for index, call in enumerate(calls) if "rm" in call and "gdelt-egress" in call)
    assert log_index < remove_index
