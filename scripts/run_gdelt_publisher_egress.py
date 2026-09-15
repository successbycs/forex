#!/usr/bin/env python3
"""Run the fixed loopback-only GDELT publisher retrieval boundary."""
from __future__ import annotations
import os
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from forex.gdelt_publisher_egress import GDELTEgressConfig, GDELTFetchError, create_server  # noqa: E402

def main() -> int:
    try:
        bearer_path = Path(os.environ.get("FOREX_GDELT_EGRESS_BEARER_FILE", ""))
        signing_key_path = Path(os.environ.get("FOREX_GDELT_CANDIDATE_SIGNING_KEY_FILE", ""))
        bearer_token = bearer_path.read_text(encoding="utf-8").strip()
        candidate_signing_key = signing_key_path.read_text(encoding="utf-8").strip()
        config = GDELTEgressConfig(os.environ.get("FOREX_GDELT_EGRESS_BIND_HOST", "127.0.0.1"),
                                   int(os.environ.get("FOREX_GDELT_EGRESS_PORT", "8092")), bearer_token,
                                   candidate_signing_key,
                                   os.environ.get("FOREX_GDELT_EGRESS_CONTAINER_MODE") == "true")
        server = create_server(config)
    except (GDELTFetchError, OSError, ValueError) as exc:
        print(f"FOREX_GDELT_EGRESS_REFUSED: {exc}", file=sys.stderr); return 2
    print(f"FOREX_GDELT_EGRESS_READY {config.bind_host}:{config.port}", flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: return 0
    finally: server.server_close()
if __name__ == "__main__": raise SystemExit(main())
