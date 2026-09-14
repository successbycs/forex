from __future__ import annotations

import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "t480" / "plane-mcp.sh"


def test_wrapper_rejects_non_owner_only_environment(tmp_path: Path):
    env_file = tmp_path / "plane-mcp.env"
    env_file.write_text("PLANE_API_KEY=x\nPLANE_WORKSPACE_SLUG=forex\nPLANE_BASE_URL=http://plane:8090/api\n", encoding="utf-8")
    env_file.chmod(0o640)
    result = subprocess.run([str(WRAPPER)], env={**os.environ, "FOREX_PLANE_MCP_ENV": str(env_file)}, text=True, capture_output=True, check=False)
    assert result.returncode == 2
    assert "mode 0600" in result.stderr
    assert "PLANE_API_KEY" not in result.stderr


def test_wrapper_exports_only_valid_self_hosted_mcp_endpoint(tmp_path: Path):
    env_file = tmp_path / "plane-mcp.env"
    env_file.write_text("PLANE_API_KEY=reused-token\nPLANE_WORKSPACE_SLUG=forex\nPLANE_BASE_URL=http://plane-host:8090/api\n", encoding="utf-8")
    env_file.chmod(0o600)
    fake_bin, output = tmp_path / "bin", tmp_path / "observed"
    fake_bin.mkdir()
    fake_uvx = fake_bin / "uvx"
    fake_uvx.write_text("#!/usr/bin/env bash\nprintf '%s' \"$PLANE_WORKSPACE_SLUG|$PLANE_BASE_URL\" > \"$OUTPUT\"\n", encoding="utf-8")
    fake_uvx.chmod(0o755)
    result = subprocess.run([str(WRAPPER)], env={**os.environ, "FOREX_PLANE_MCP_ENV": str(env_file), "PATH": f"{fake_bin}:{os.environ['PATH']}", "OUTPUT": str(output)}, text=True, capture_output=True, check=False)
    assert result.returncode == 0
    assert output.read_text(encoding="utf-8") == "forex|http://plane-host:8090/api"
    assert "reused-token" not in result.stdout + result.stderr


def test_wrapper_finds_user_uvx_without_login_shell_path(tmp_path: Path):
    env_file = tmp_path / "plane-mcp.env"
    env_file.write_text("PLANE_API_KEY=private-token\nPLANE_WORKSPACE_SLUG=forex\nPLANE_BASE_URL=http://localhost:18090/api\n", encoding="utf-8")
    env_file.chmod(0o600)
    local_bin = tmp_path / ".local" / "bin"
    local_bin.mkdir(parents=True)
    uvx = local_bin / "uvx"
    uvx.write_text("#!/bin/bash\nprintf '%s' \"$*\"\n", encoding="utf-8")
    uvx.chmod(0o755)
    result = subprocess.run([str(WRAPPER)], env={"HOME": str(tmp_path), "PATH": "/usr/bin:/bin", "FOREX_PLANE_MCP_ENV": str(env_file)}, text=True, capture_output=True, check=False)
    assert result.returncode == 0
    assert result.stdout == "--from plane-mcp-server==0.3.2 plane-mcp-server stdio"
    assert "private-token" not in result.stdout + result.stderr


def test_wrapper_reports_missing_client_dependency_without_secrets(tmp_path: Path):
    env_file = tmp_path / "plane-mcp.env"
    env_file.write_text("PLANE_API_KEY=private-token\nPLANE_WORKSPACE_SLUG=forex\nPLANE_BASE_URL=http://localhost:18090/api\n", encoding="utf-8")
    env_file.chmod(0o600)
    result = subprocess.run([str(WRAPPER)], env={"HOME": str(tmp_path), "PATH": "/usr/bin:/bin", "FOREX_PLANE_MCP_ENV": str(env_file)}, text=True, capture_output=True, check=False)
    assert result.returncode == 2
    assert "install uvx on this client" in result.stderr
    assert "private-token" not in result.stdout + result.stderr
