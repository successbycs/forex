"""Canonical artifact contract for M0 evidence bundles."""

from __future__ import annotations


M0_EVIDENCE_ARTIFACTS = frozenset(
    {
        "t480-dependency.txt",
        "t480-dependency.stderr.txt",
        "venv.stdout.txt",
        "venv.stderr.txt",
        "install.stdout.txt",
        "install.stderr.txt",
        "governance.stdout.txt",
        "governance.stderr.txt",
        "configuration.stdout.txt",
        "configuration.stderr.txt",
        "tests.stdout.txt",
        "tests.stderr.txt",
        "dependencies.txt",
        "repository-verification.stdout.txt",
        "repository-verification.stderr.txt",
        "exit-codes.txt",
        "summary.txt",
    }
)
