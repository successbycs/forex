#!/usr/bin/env python3
"""Create the three ignored, owner-only secrets for GDELT publisher egress.

This command is intentionally local to T480.  It never accepts secrets on the
command line and never prints them.  Existing files are left untouched unless
they form a complete valid set, which makes a retry safe.
"""
from __future__ import annotations

import argparse
import os
import secrets
import stat
import tempfile
from pathlib import Path


DEFAULT_DIRECTORY = Path("/home/chris/.config/forex")
ENV_NAME = "gdelt-n8n.env"
BEARER_NAME = "gdelt-egress-bearer"
SIGNING_NAME = "gdelt-candidate-signing-key"
REQUIRED = ("FOREX_GDELT_EGRESS_BEARER", "FOREX_GDELT_CANDIDATE_SIGNING_KEY")


def _read_private(path: Path) -> str:
    metadata = path.lstat()
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o600:
        raise RuntimeError("existing GDELT secret file is not a mode-0600 ordinary file")
    return path.read_text(encoding="utf-8").strip()


def _write_new_private(path: Path, value: str) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(value)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        Path(temporary).unlink(missing_ok=True)
        raise


def provision(directory: Path = DEFAULT_DIRECTORY) -> None:
    """Create a matching complete set or verify an existing matching set."""
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if stat.S_IMODE(directory.stat().st_mode) & 0o077:
        raise RuntimeError("GDELT secret directory must not be group/world accessible")
    paths = {
        "FOREX_GDELT_EGRESS_BEARER": directory / BEARER_NAME,
        "FOREX_GDELT_CANDIDATE_SIGNING_KEY": directory / SIGNING_NAME,
    }
    env_path = directory / ENV_NAME
    existing = [env_path, *paths.values()]
    if any(path.exists() for path in existing):
        if not all(path.exists() for path in existing):
            raise RuntimeError("refusing to mix a partial existing GDELT secret set with new values")
        values = {key: _read_private(path) for key, path in paths.items()}
        env = dict(line.split("=", 1) for line in _read_private(env_path).splitlines() if "=" in line)
        if set(env) != set(REQUIRED) or any(env.get(key) != values[key] for key in REQUIRED):
            raise RuntimeError("existing GDELT secret set does not match")
        return
    values = {key: secrets.token_urlsafe(32) for key in REQUIRED}
    _write_new_private(paths["FOREX_GDELT_EGRESS_BEARER"], values["FOREX_GDELT_EGRESS_BEARER"])
    try:
        _write_new_private(paths["FOREX_GDELT_CANDIDATE_SIGNING_KEY"], values["FOREX_GDELT_CANDIDATE_SIGNING_KEY"])
        _write_new_private(env_path, "".join(f"{key}={values[key]}\n" for key in REQUIRED).rstrip())
    except BaseException:
        # A partial set must be diagnosed rather than silently rotated.
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Create private GDELT egress secrets without printing them")
    parser.add_argument("--directory", type=Path, default=DEFAULT_DIRECTORY)
    args = parser.parse_args()
    try:
        provision(args.directory)
    except (OSError, RuntimeError) as exc:
        print(f"FOREX_GDELT_SECRET_PROVISION_REFUSED: {exc}")
        return 2
    print("FOREX_GDELT_SECRET_PROVISIONED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
