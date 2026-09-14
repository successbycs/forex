#!/usr/bin/env python3
"""Render BLS user-unit templates only; never install or activate them."""
import argparse
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]


def local_path(value, *, interpreter=False):
    path = Path(value)
    # Restrict template values rather than interpret systemd quoting, specifiers,
    # environment expansion or shell syntax. Current deployment paths fit this.
    if not path.is_absolute() or not re.fullmatch(r"/[A-Za-z0-9_./-]+", str(path)) or ".." in path.parts:
        raise ValueError("unit paths must be absolute plain paths without traversal or expansion syntax")
    for part in path.parents if interpreter else (path, *path.parents):
        if part.is_symlink():
            raise ValueError("unit paths must not traverse symlinks")
    return path


def render(*, repository, python, store, environment=None):
    repository, store = local_path(repository), local_path(store)
    # Preserve venv argv[0]; resolving its executable symlink silently selects
    # system Python and loses the reviewed environment's dependencies.
    python = local_path(python, interpreter=True)
    if not repository.is_dir() or not store.is_dir() or not python.is_file():
        raise ValueError("repository, interpreter and retained store must exist")
    if not (repository / "scripts/bls_schedule.py").is_file():
        raise ValueError("repository has no BLS scheduling entry point")
    values = {"FOREX_REPOSITORY_ABSOLUTE_PATH": repository,
              "PYTHON_EXECUTABLE_ABSOLUTE_PATH": python,
              "BLS_RETAINED_STORE_ABSOLUTE_PATH": store}
    if environment is not None:
        environment = local_path(environment)
        if not environment.is_file() or environment.stat().st_mode & 0o077:
            raise ValueError("optional environment file must exist with private permissions")
        values["OPTIONAL_T480_ENVIRONMENT_FILE_ABSOLUTE_PATH"] = environment
    result = {}
    for name in ("forex-bls-schedule.service", "forex-bls-schedule.timer"):
        source = (ROOT / "deploy/bls" / name).read_text()
        lines = [line for line in source.splitlines() if not line.startswith("#")]
        if environment is None:
            lines = [line for line in lines if not line.startswith("EnvironmentFile=")]
        source = "\n".join(lines) + "\n"
        for key, value in values.items():
            source = source.replace("{{" + key + "}}", str(value))
        if "{{" in source or "}}" in source:
            raise ValueError("unresolved template placeholder")
        result[name] = source
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=ROOT)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--environment", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        rendered = render(repository=args.repository, python=args.python, store=args.store, environment=args.environment)
        output = local_path(args.output)
        if not output.is_dir() or any(output.iterdir()):
            raise ValueError("output must be an existing empty directory")
        for name, content in rendered.items():
            with (output / name).open("x", encoding="utf-8") as handle:
                handle.write(content)
        print("Rendered only; validate with systemd-analyze --user verify before installation.")
        return 0
    except (OSError, ValueError) as exc:
        print(f"BLS unit rendering refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
