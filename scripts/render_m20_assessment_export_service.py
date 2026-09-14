#!/usr/bin/env python3
"""Render latest-M20-assessment exporter user units only; never install them."""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]


def _path(value: Path, *, interpreter: bool = False) -> Path:
    value = Path(value)
    if not value.is_absolute() or not re.fullmatch(r"/[A-Za-z0-9_./-]+", str(value)) or ".." in value.parts:
        raise ValueError("unit paths must be absolute plain paths without traversal or expansion")
    for item in value.parents if interpreter else (value, *value.parents):
        if item.is_symlink():
            raise ValueError("unit paths must not traverse symlinks")
    return value


def render(*, repository: Path, python: Path, assessments: Path) -> dict[str, str]:
    repository, assessments, python = _path(repository), _path(assessments), _path(python, interpreter=True)
    if not repository.is_dir() or not assessments.is_dir() or not python.is_file():
        raise ValueError("repository, interpreter and assessment root must exist")
    if not (repository / "scripts" / "m20_spool_page_export.py").is_file():
        raise ValueError("repository has no spool-page exporter")
    values = {"REPOSITORY": str(repository), "PYTHON": str(python), "ASSESSMENTS": str(assessments)}
    rendered = {}
    for name in ("forex-m20-assessment-export.service", "forex-m20-assessment-export.timer"):
        body = (ROOT / "deploy" / "m20-assessment-export" / name).read_text(encoding="utf-8")
        for key, value in values.items():
            body = body.replace("{{" + key + "}}", value)
        if "{{" in body or "}}" in body:
            raise ValueError("unresolved template placeholder")
        rendered[name] = body
    return rendered


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=ROOT)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--assessments", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        output = _path(args.output)
        if not output.is_dir() or any(output.iterdir()):
            raise ValueError("output must be an existing empty directory")
        for name, body in render(repository=args.repository, python=args.python, assessments=args.assessments).items():
            (output / name).open("x", encoding="utf-8").write(body)
        print("Rendered only; validate with systemd-analyze --user verify before installation.")
        return 0
    except (OSError, ValueError) as exc:
        print(f"M20 assessment-export unit rendering refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
