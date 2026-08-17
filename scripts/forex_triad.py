#!/usr/bin/env python3
"""Repository-local entry point for Triad review governance."""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from forex.triad import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
