from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from forex.t480_dependency import inspect_dependency


ROOT = Path(__file__).resolve().parents[1]


def _run(*argv: str, cwd: Path) -> str:
    return subprocess.run(
        list(argv), cwd=cwd, text=True, capture_output=True, check=True
    ).stdout.strip()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _fixture(tmp_path: Path) -> tuple[Path, Path]:
    dependency_root = tmp_path / "shared"
    dependency_root.mkdir()
    _run("git", "init", "-q", cwd=dependency_root)
    dependency_paths = [
        "t480_core/__init__.py",
        "t480_core/core.py",
        "t480/transport-config.json",
    ]
    for index, relative in enumerate(dependency_paths):
        path = dependency_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"dependency-{index}\n", encoding="utf-8")
    _run("git", "add", "--", *dependency_paths, cwd=dependency_root)
    _run(
        "git",
        "-c",
        "user.name=Forex Test",
        "-c",
        "user.email=forex-test@example.invalid",
        "commit",
        "-qm",
        "dependency fixture",
        cwd=dependency_root,
    )
    dependency_revision = _run("git", "rev-parse", "HEAD", cwd=dependency_root)
    adapter_config = {
        "shared_core": {
            "repository": "fixture/shared",
            "repository_root": str(dependency_root),
            "expected_git_revision": dependency_revision,
            "require_clean_worktree": True,
            "require_tracked_files": True,
            "files": [
                {"path": relative, "sha256": _sha256(dependency_root / relative)}
                for relative in dependency_paths
            ],
        }
    }

    root = tmp_path / "forex"
    (root / "scripts").mkdir(parents=True)
    shutil.copy2(ROOT / "scripts" / "verify_m0_evidence.sh", root / "scripts")
    module = root / "src" / "forex" / "t480_dependency.py"
    module.parent.mkdir(parents=True)
    shutil.copy2(ROOT / "src" / "forex" / "t480_dependency.py", module)
    (module.parent / "__init__.py").write_text("", encoding="utf-8")
    _write_json(root / "config" / "t480.json", adapter_config)
    _write_json(
        root / "project_state.json",
        {"governed_configuration_paths": ["config/t480.json"]},
    )
    _write_json(
        root / "milestone_registry.json",
        {
            "milestones": [
                {
                    "milestone_id": "M0",
                    "real_world_proof": {
                        "surface": "fresh temporary Python environment",
                        "freshness_hours": 24,
                        "success_markers": ["FOREX_M0_PROOF_OK"],
                    },
                }
            ]
        },
    )
    _run("git", "init", "-q", cwd=root)
    _run("git", "add", ".", cwd=root)
    _run(
        "git",
        "-c",
        "user.name=Forex Test",
        "-c",
        "user.email=forex-test@example.invalid",
        "commit",
        "-qm",
        "verifier fixture",
        cwd=root,
    )

    bundle = root / "runs" / "evidence" / "M0" / "fixture"
    bundle.mkdir(parents=True)
    (bundle / "summary.txt").write_text("FOREX_M0_PROOF_OK\n", encoding="utf-8")
    (bundle / "exit-codes.txt").write_text(
        "\n".join(
            [
                "t480_dependency=0",
                "venv=0",
                "install=0",
                "governance=0",
                "configuration=0",
                "tests=0",
                "repository_verification=0",
                "overall=0",
                "",
            ]
        ),
        encoding="utf-8",
    )
    dependency = inspect_dependency(adapter_config)
    (bundle / "t480-dependency.txt").write_text(
        json.dumps(dependency, indent=2) + "\n", encoding="utf-8"
    )
    fingerprint = hashlib.sha256()
    fingerprint.update(b"config/t480.json\0")
    fingerprint.update((root / "config" / "t480.json").read_bytes())
    fingerprint.update(b"\0")
    manifest = {
        "schema_version": "1.0.0",
        "milestone_id": "M0",
        "captured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "git_revision": _run("git", "rev-parse", "HEAD", cwd=root),
        "dirty_worktree": False,
        "configuration_fingerprint": f"sha256:{fingerprint.hexdigest()}",
        "surface": "fresh temporary Python environment",
        "operation": "black-box verifier fixture",
        "expected_result": "Verifier accepts only an intact bundle.",
        "observed_result": "FOREX_M0_PROOF_OK",
        "exit_code": 0,
        "redactions": [],
        "summary": "FOREX_M0_PROOF_OK",
        "external_dependencies": [dependency],
        "artifacts": [
            {"path": path.name, "sha256": _sha256(path)}
            for path in sorted(bundle.glob("*.txt"))
        ],
    }
    _write_json(bundle / "manifest.json", manifest)
    return root, bundle


def _verify(root: Path, bundle: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(root / "scripts" / "verify_m0_evidence.sh"), str(bundle)],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )


def _manifest(bundle: Path) -> dict:
    return json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))


def _save_manifest(bundle: Path, manifest: dict) -> None:
    _write_json(bundle / "manifest.json", manifest)


def test_black_box_verifier_accepts_bound_bundle(tmp_path: Path) -> None:
    root, bundle = _fixture(tmp_path)
    result = _verify(root, bundle)
    assert result.returncode == 0, result.stderr
    assert "FOREX_M0_EVIDENCE_VERIFIED" in result.stdout


@pytest.mark.parametrize(
    ("mutation", "expected_error"),
    [
        ("missing", "missing or unsafe artifact"),
        ("stale", "outside the declared freshness window"),
        ("dirty", "captured worktree was dirty"),
        ("revision", "Git revision mismatch"),
        ("configuration", "configuration fingerprint mismatch"),
        ("marker", "missing success marker"),
        ("exit_code", "required exit codes"),
        ("path_escape", "missing or unsafe artifact"),
    ],
)
def test_black_box_verifier_rejects_invalid_bundles(
    tmp_path: Path, mutation: str, expected_error: str
) -> None:
    root, bundle = _fixture(tmp_path)
    manifest = _manifest(bundle)
    if mutation == "missing":
        (bundle / "summary.txt").unlink()
    elif mutation == "stale":
        manifest["captured_at"] = "2000-01-01T00:00:00+00:00"
    elif mutation == "dirty":
        manifest["dirty_worktree"] = True
    elif mutation == "revision":
        manifest["git_revision"] = "0" * 40
    elif mutation == "configuration":
        manifest["configuration_fingerprint"] = "sha256:" + "0" * 64
    elif mutation == "marker":
        summary = bundle / "summary.txt"
        summary.write_text("NO_SUCCESS\n", encoding="utf-8")
        next(item for item in manifest["artifacts"] if item["path"] == "summary.txt")[
            "sha256"
        ] = _sha256(summary)
    elif mutation == "exit_code":
        exits = bundle / "exit-codes.txt"
        exits.write_text(exits.read_text(encoding="utf-8").replace("tests=0", "tests=1"), encoding="utf-8")
        next(item for item in manifest["artifacts"] if item["path"] == "exit-codes.txt")[
            "sha256"
        ] = _sha256(exits)
    elif mutation == "path_escape":
        manifest["artifacts"][0]["path"] = "../../outside.txt"
    _save_manifest(bundle, manifest)
    result = _verify(root, bundle)
    assert result.returncode != 0
    assert expected_error in result.stderr
