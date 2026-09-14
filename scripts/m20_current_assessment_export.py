#!/usr/bin/env python3
"""Capture one fixed read-only latest M20 assessment into local immutable storage."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from forex.m20_current_export import (  # noqa: E402
    CurrentAssessmentExportError,
    OPERATION,
    parse_adapter_result,
    retain,
)


def run_once(*, root: Path, timeout_seconds: int = 30) -> dict:
    command = [sys.executable, str(ROOT / "scripts" / "t480_adapter.py"), "execute", "--operation", OPERATION]
    completed = subprocess.run(command, capture_output=True, timeout=timeout_seconds, check=False)
    if completed.returncode != 0:
        raise CurrentAssessmentExportError("fixed latest-assessment adapter operation failed")
    record = parse_adapter_result(completed.stdout)
    if record["state"] == "ASSESSMENT_ABSENT":
        return {"schema_version": "forex.m20.current-assessment-export-command.v1", **record}
    from forex.m20_current_export import _coverage
    record["coverage"] = _coverage(root, record)
    path, publication = retain(root, record)
    return {
        "schema_version": "forex.m20.current-assessment-export-command.v1",
        "state": "RETAINED",
        "publication": publication,
        "capture_path": str(path),
        "assessment_raw_sha256": record["assessment_raw_sha256"],
        "assessment_sequence": record["assessment_sequence"],
        **record["coverage"],
        "execution_authority": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(run_once(root=args.root), sort_keys=True, allow_nan=False))
        return 0
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print("current M20 assessment export refused; inspect the fixed adapter result and local store", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
