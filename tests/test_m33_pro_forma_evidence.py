from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import pytest

from scripts import m33_pro_forma_evidence as evidence


def _bundle(tmp_path: Path) -> tuple[Path, dict]:
    bundle = tmp_path / "m33"
    bundle.mkdir()
    artifacts = []
    for name in sorted(evidence.REQUIRED_ARTIFACTS):
        content = f"fixture:{name}\n".encode()
        (bundle / name).write_bytes(content)
        artifacts.append({"path": name, "sha256": hashlib.sha256(content).hexdigest()})
    manifest = {
        "schema_version": "1.0.0",
        "milestone_id": "M33",
        "captured_at": "2026-09-24T03:00:00Z",
        "git_revision": "a" * 40,
        "configuration_fingerprint": "sha256:" + "b" * 64,
        "surface": evidence.SURFACE,
        "operation": evidence.OPERATION,
        "expected_result": evidence.MARKER,
        "observed_result": evidence.MARKER,
        "exit_code": 0,
        "dirty_worktree": False,
        "summary": evidence.MARKER,
        "redactions": [evidence.REDACTION],
        "artifacts": artifacts,
    }
    (bundle / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return bundle, manifest


def _validate(bundle: Path, manifest: dict) -> None:
    evidence.validate_manifest(
        bundle,
        manifest,
        current_revision="a" * 40,
        current_fingerprint="sha256:" + "b" * 64,
        now=datetime(2026, 9, 24, 3, 1, tzinfo=timezone.utc),
    )


def test_m33_manifest_accepts_only_the_complete_capture_contract(tmp_path):
    bundle, manifest = _bundle(tmp_path)
    _validate(bundle, manifest)


@pytest.mark.parametrize("mutation", ["extra-key", "external-path", "extra-file", "wrong-fingerprint"])
def test_m33_manifest_fails_closed_when_bindings_drift(tmp_path, mutation):
    bundle, manifest = _bundle(tmp_path)
    if mutation == "extra-key":
        manifest["unbound"] = True
    elif mutation == "external-path":
        manifest["artifacts"][0]["path"] = "../outside.txt"
    elif mutation == "extra-file":
        (bundle / "unlisted.txt").write_text("unexpected", encoding="utf-8")
    else:
        manifest["configuration_fingerprint"] = "sha256:" + "c" * 64
    with pytest.raises(RuntimeError):
        _validate(bundle, manifest)
