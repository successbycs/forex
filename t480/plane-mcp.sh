#!/usr/bin/env bash
# Forex-owned stdio Plane MCP launcher. Credentials remain outside Git.
set -euo pipefail

env_file="${FOREX_PLANE_MCP_ENV:-$HOME/.config/forex/plane-mcp.env}"
if [[ -L "$env_file" || ! -f "$env_file" ]]; then
  echo "FOREX_PLANE_MCP_REFUSED: protected environment file is missing" >&2
  exit 2
fi
if [[ "$(stat -c '%u:%a' "$env_file")" != "$(id -u):600" ]]; then
  echo "FOREX_PLANE_MCP_REFUSED: protected environment file must be owner-only mode 0600" >&2
  exit 2
fi

set -a
# shellcheck disable=SC1090
. "$env_file"
set +a
if [[ -z "${PLANE_API_KEY:-}" || "${PLANE_WORKSPACE_SLUG:-}" != "forex" || ! "${PLANE_BASE_URL:-}" =~ ^https?://[^/]+(:[0-9]+)?/api$ ]]; then
  echo "FOREX_PLANE_MCP_REFUSED: Plane MCP settings are invalid" >&2
  exit 2
fi

# GUI-launched Codex does not necessarily inherit the login shell's PATH.
# Use the operator's own installation; never borrow another project's tools.
uvx_command="$(command -v uvx || true)"
if [[ -z "$uvx_command" && -x "$HOME/.local/bin/uvx" ]]; then
  uvx_command="$HOME/.local/bin/uvx"
fi
if [[ -z "$uvx_command" ]]; then
  echo "FOREX_PLANE_MCP_REFUSED: install uvx on this client (PATH or ~/.local/bin/uvx); see docs/plane-integration.md" >&2
  exit 2
fi

exec "$uvx_command" --from 'plane-mcp-server==0.3.2' plane-mcp-server stdio
