#!/usr/bin/env python3
"""Run the machine-local authenticated BLS n8n retention service."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from forex.bls_n8n_service import BLSN8nServiceConfig, BLSN8nServiceConfigError, create_server  # noqa: E402


def main() -> int:
    try:
        config = BLSN8nServiceConfig.from_environ()
        server = create_server(config)
    except (BLSN8nServiceConfigError, OSError, ValueError) as exc:
        print(f"FOREX_BLS_N8N_SERVICE_REFUSED: {exc}", file=sys.stderr)
        return 2
    print(f"FOREX_BLS_N8N_SERVICE_READY {config.bind_host}:{config.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
