#!/usr/bin/env python3
"""Capture one fixed read-only all-Demo-history response into immutable local storage."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from forex.m20_history_capture import HistoryCaptureError, retain_history_response  # noqa: E402


def run_once(*, root: Path, timeout_seconds: int = 130) -> dict[str, object]:
    command = [sys.executable, str(ROOT / "scripts" / "t480_adapter.py"), "execute",
               "--operation", "m20_all_demo_history_export"]
    completed = subprocess.run(command, capture_output=True, timeout=timeout_seconds, check=False)
    if completed.returncode != 0:
        raise HistoryCaptureError("fixed all-history adapter operation failed")
    path, publication, report = retain_history_response(root=root, adapter_response_raw=completed.stdout)
    return {"schema_version": "forex.m20.all-history-capture-command.v1", "state": "RETAINED",
            "publication": publication, "capture_path": str(path),
            "adapter_response_sha256": report["source_sha256"],
            "closed_position_count": report["closed_position_count"],
            "net_realized_aud": report["net_realized_aud"], "execution_authority": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    arguments = parser.parse_args(argv)
    try:
        print(json.dumps(run_once(root=arguments.root), sort_keys=True, allow_nan=False))
        return 0
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print("all-Demo-history capture refused; inspect the fixed adapter response and local store", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
