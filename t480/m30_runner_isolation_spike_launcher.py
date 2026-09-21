"""One-shot launcher for the staged M30 runner/audit compatibility spike."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4


def main() -> int:
    if len(sys.argv) != 5:
        raise SystemExit("M30 isolation launcher arguments are invalid")
    runner, output_dir = map(Path, sys.argv[1:3])
    bridge_hash = sys.argv[3]
    mode = sys.argv[4]
    if not runner.is_file() or not bridge_hash.startswith("sha256:"):
        raise SystemExit("M30 isolation launcher payload is invalid")
    config = Path(r"C:\ProgramData\ForexListener\state\m20_demo_listener_service.local.json")
    try:
        values = json.loads(config.read_text(encoding="utf-8-sig"))
        python, terminal = str(values["python_path"]), str(values["terminal_path"])
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise SystemExit("M30 isolation launcher configuration is unavailable") from error
    os.environ["FOREX_M20_POSTGRES_AUDIT_BRIDGE_SHA256"] = bridge_hash
    try:
        expected = {
            "--audit-isolation-spike": "FOREX_M30_AUDIT_ISOLATION_SPIKE_OK",
            "--pre-isolation-readiness": "FOREX_M30_PRE_ISOLATION_READINESS",
            "--quote-identity": "FOREX_M20_DEMO_QUOTE_IDENTITY_OK",
            "--terminal-runtime-binding": "FOREX_M20_TERMINAL_RUNTIME_BINDING",
        }.get(mode)
        if expected is None:
            raise SystemExit("M30 isolation launcher mode is invalid")
        completed = subprocess.run(
            [python, str(runner), terminal, "unused-session", mode],
            text=True, capture_output=True, timeout=45, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise SystemExit("M30 isolation runner did not complete") from error
    if completed.returncode != 0 or len(completed.stdout) > 65_536:
        raise SystemExit("M30 isolation runner failed closed")
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise SystemExit("M30 isolation runner output is invalid") from error
    if result.get("marker") != expected or (
        mode == "--terminal-runtime-binding" and result.get("state") != "MAPPED"
    ):
        raise SystemExit("M30 isolation runner did not confirm compatibility")
    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = "pre-isolation-" if mode == "--pre-isolation-readiness" else "runner-probe-"
    output = output_dir / (prefix + uuid4().hex + ".json")
    with output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, sort_keys=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
