"""Immutable identity checks for the externally owned T480 transport core."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
from typing import Any


_SHA256 = re.compile(r"[a-f0-9]{64}\Z")
_GIT_REVISION = re.compile(r"[a-f0-9]{40}\Z")
_SAFE_RELATIVE = re.compile(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*\Z")


def _git(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments], cwd=root, text=True, capture_output=True, check=False
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_dependency_lock(config: dict[str, Any]) -> dict[str, Any]:
    lock = config.get("shared_core")
    if not isinstance(lock, dict):
        raise ValueError("shared_core must be a dependency-lock object")
    expected_fields = {
        "repository",
        "repository_root",
        "expected_git_revision",
        "require_clean_worktree",
        "require_tracked_files",
        "files",
    }
    if set(lock) != expected_fields:
        raise ValueError("shared_core dependency-lock fields are invalid")
    root = Path(str(lock["repository_root"]))
    if not root.is_absolute():
        raise ValueError("shared_core.repository_root must be absolute")
    if not isinstance(lock["repository"], str) or not lock["repository"].strip():
        raise ValueError("shared_core.repository must identify its owner repository")
    if not _GIT_REVISION.fullmatch(str(lock["expected_git_revision"])):
        raise ValueError("shared_core.expected_git_revision must be a full Git revision")
    if not isinstance(lock["require_clean_worktree"], bool) or lock["require_tracked_files"] is not True:
        raise ValueError("shared_core must declare clean-worktree policy and require tracked files")
    files = lock["files"]
    if not isinstance(files, list) or not files:
        raise ValueError("shared_core.files must be a non-empty dependency lock")
    paths: list[str] = []
    for entry in files:
        if not isinstance(entry, dict) or set(entry) != {"path", "sha256"}:
            raise ValueError("shared_core file lock entries require path and sha256")
        relative = str(entry["path"])
        if not _SAFE_RELATIVE.fullmatch(relative) or relative.startswith("."):
            raise ValueError(f"unsafe shared_core file path: {relative}")
        if not _SHA256.fullmatch(str(entry["sha256"])):
            raise ValueError(f"invalid shared_core SHA-256: {relative}")
        paths.append(relative)
    if len(paths) != len(set(paths)):
        raise ValueError("shared_core dependency lock contains duplicate paths")
    return lock


def inspect_dependency(config: dict[str, Any]) -> dict[str, Any]:
    lock = validate_dependency_lock(config)
    root = Path(lock["repository_root"]).resolve()
    errors: list[str] = []
    revision_result = _git(root, "rev-parse", "HEAD") if root.is_dir() else None
    revision = (
        revision_result.stdout.strip()
        if revision_result is not None and revision_result.returncode == 0
        else "UNAVAILABLE"
    )
    revision_matches = revision == lock["expected_git_revision"]
    if not revision_matches:
        errors.append("owner repository revision does not match the locked revision")
    status_result = (
        _git(root, "status", "--porcelain", "--untracked-files=all") if root.is_dir() else None
    )
    clean = bool(status_result is not None and status_result.returncode == 0 and not status_result.stdout)
    if lock["require_clean_worktree"] and not clean:
        errors.append("owner repository worktree is not clean")
    files: list[dict[str, Any]] = []
    fingerprint = hashlib.sha256()
    for entry in lock["files"]:
        relative = entry["path"]
        path = (root / relative).resolve()
        exists = path.is_relative_to(root) and path.is_file()
        actual_sha = _sha256(path) if exists else None
        tracked_result = _git(root, "ls-files", "--error-unmatch", "--", relative) if root.is_dir() else None
        tracked = bool(tracked_result is not None and tracked_result.returncode == 0)
        matches = actual_sha == entry["sha256"]
        if not exists:
            errors.append(f"locked dependency file is missing: {relative}")
        elif not matches:
            errors.append(f"locked dependency hash mismatch: {relative}")
        if not tracked:
            errors.append(f"locked dependency file is not tracked: {relative}")
        fingerprint.update(relative.encode("utf-8"))
        fingerprint.update(b"\0")
        fingerprint.update(str(actual_sha or "MISSING").encode("ascii"))
        fingerprint.update(b"\0")
        files.append(
            {
                "path": relative,
                "expected_sha256": entry["sha256"],
                "actual_sha256": actual_sha,
                "tracked": tracked,
                "matches": matches,
            }
        )
    return {
        "schema_version": "forex.external-dependency.v1",
        "name": "t480_core",
        "repository": lock["repository"],
        "expected_git_revision": lock["expected_git_revision"],
        "actual_git_revision": revision,
        "revision_matches": revision_matches,
        "clean_worktree": clean,
        "content_fingerprint": f"sha256:{fingerprint.hexdigest()}",
        "files": files,
        "errors": errors,
        "ok": not errors,
    }


def require_dependency(config: dict[str, Any]) -> dict[str, Any]:
    identity = inspect_dependency(config)
    if not identity["ok"]:
        raise ValueError("T480 shared-core dependency check failed: " + "; ".join(identity["errors"]))
    return identity


def canonical_dependency_json(identity: dict[str, Any]) -> str:
    return json.dumps(identity, indent=2, sort_keys=True) + "\n"
