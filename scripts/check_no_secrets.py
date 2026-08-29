#!/usr/bin/env python3
"""Fail when tracked or trackable repository files look secret-bearing."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess
import sys


FORBIDDEN_NAMES = {
    ".env",
    "credentials.json",
    "id_rsa",
    "id_ed25519",
}
FORBIDDEN_SUFFIXES = {".key", ".p12", ".pfx", ".pem"}
ALLOWED_PUBLIC_KEY_FILENAMES = {"evidence_runner_public.pem"}
SECRET_PATTERNS = {
    "private key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "AWS access key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "GitHub token": re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
    "OpenAI key": re.compile(r"sk-[A-Za-z0-9_-]{32,}"),
}


def candidate_files(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace"))
    return [root / item.decode("utf-8") for item in result.stdout.split(b"\0") if item]


def scan_file(path: Path) -> list[str]:
    problems: list[str] = []
    if path.name in FORBIDDEN_NAMES and path.name != ".env.example":
        problems.append("forbidden secret-bearing filename")
    if path.suffix.lower() in FORBIDDEN_SUFFIXES and path.name not in ALLOWED_PUBLIC_KEY_FILENAMES:
        problems.append("forbidden credential/key suffix")
    try:
        content = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return problems
    for label, pattern in SECRET_PATTERNS.items():
        if pattern.search(content):
            problems.append(f"possible {label}")
    if path.name in ALLOWED_PUBLIC_KEY_FILENAMES and "-----BEGIN PUBLIC KEY-----" not in content:
        problems.append("configured public-key file does not contain a public key")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scan tracked and trackable files for likely secrets")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    root = args.root.resolve()
    findings = [
        f"{path.relative_to(root)}: {problem}"
        for path in candidate_files(root)
        for problem in scan_file(path)
    ]
    if findings:
        print("\n".join(findings), file=sys.stderr)
        return 2
    print("FOREX_SECRET_SCAN_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
