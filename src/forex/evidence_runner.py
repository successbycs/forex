"""Fixed-job local evidence runner with self-attested OpenSSL signatures."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any


JOB_ID = "m0-clean-environment-capture"
ATTESTATION_NAME = "runner-attestation.json"


class EvidenceRunnerError(RuntimeError):
    """The fixed evidence-runner contract could not be satisfied."""


def canonical_bytes(value: dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_config(root: Path) -> dict[str, Any]:
    config = json.loads((root / "config" / "evidence_runner.json").read_text(encoding="utf-8"))
    required = {"schema_version", "runner_key_id", "public_key_path", "allowed_jobs"}
    if set(config) != required or config["schema_version"] != "forex.evidence-runner.v1":
        raise EvidenceRunnerError("invalid evidence-runner configuration")
    if config["allowed_jobs"] != [JOB_ID]:
        raise EvidenceRunnerError("evidence runner must expose only its fixed M0 job")
    return config


def _openssl(*args: str, data: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
    result = subprocess.run(["openssl", *args], input=data, capture_output=True, check=False)
    if result.returncode:
        raise EvidenceRunnerError(result.stderr.decode("utf-8", errors="replace").strip() or "OpenSSL failed")
    return result


def generate_keypair(private_key: Path, public_key: Path) -> None:
    private_key.parent.mkdir(parents=True, exist_ok=True)
    _openssl("genpkey", "-algorithm", "ED25519", "-out", str(private_key))
    private_key.chmod(0o600)
    _openssl("pkey", "-in", str(private_key), "-pubout", "-out", str(public_key))


def attestation_payload(root: Path, bundle: Path, config: dict[str, Any]) -> dict[str, str]:
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    return {
        "schema_version": "forex.evidence-runner-attestation.v1",
        "job_id": JOB_ID,
        "runner_key_id": config["runner_key_id"],
        "bundle": str(bundle.relative_to(root)),
        "manifest_sha256": sha256_file(bundle / "manifest.json"),
        "git_revision": manifest["git_revision"],
        "configuration_fingerprint": manifest["configuration_fingerprint"],
        "captured_at": manifest["captured_at"],
    }


def sign_bundle(root: Path, bundle: Path, private_key: Path) -> Path:
    config = load_config(root)
    public_key = root / config["public_key_path"]
    if not private_key.is_file() or not public_key.is_file():
        raise EvidenceRunnerError("runner key pair is not provisioned")
    payload = attestation_payload(root, bundle, config)
    with tempfile.NamedTemporaryFile() as payload_file, tempfile.NamedTemporaryFile() as signature:
        Path(payload_file.name).write_bytes(canonical_bytes(payload))
        _openssl("pkeyutl", "-sign", "-inkey", str(private_key), "-rawin", "-in", payload_file.name, "-out", signature.name)
        signature_bytes = Path(signature.name).read_bytes()
    attestation = {"payload": payload, "signature_base64": base64.b64encode(signature_bytes).decode("ascii")}
    path = bundle / ATTESTATION_NAME
    path.write_text(json.dumps(attestation, indent=2) + "\n", encoding="utf-8")
    return path


def verify_bundle(root: Path, bundle: Path) -> None:
    config = load_config(root)
    path = bundle / ATTESTATION_NAME
    if not path.is_file():
        raise EvidenceRunnerError("runner attestation is missing")
    attestation = json.loads(path.read_text(encoding="utf-8"))
    if set(attestation) != {"payload", "signature_base64"} or not isinstance(attestation["payload"], dict):
        raise EvidenceRunnerError("runner attestation is malformed")
    expected = attestation_payload(root, bundle, config)
    if attestation["payload"] != expected:
        raise EvidenceRunnerError("runner attestation payload does not match the evidence bundle")
    try:
        signature = base64.b64decode(attestation["signature_base64"], validate=True)
    except (TypeError, ValueError) as exc:
        raise EvidenceRunnerError("runner attestation signature is invalid") from exc
    with tempfile.NamedTemporaryFile() as payload_file, tempfile.NamedTemporaryFile() as signature_file:
        Path(payload_file.name).write_bytes(canonical_bytes(expected))
        Path(signature_file.name).write_bytes(signature)
        _openssl("pkeyutl", "-verify", "-pubin", "-inkey", str(root / config["public_key_path"]), "-rawin", "-in", payload_file.name, "-sigfile", signature_file.name)


def run_m0(root: Path, private_key: Path) -> Path:
    config = load_config(root)
    if JOB_ID not in config["allowed_jobs"]:
        raise EvidenceRunnerError("M0 capture job is not allowed")
    result = subprocess.run(["bash", "scripts/capture_m0_evidence.sh"], cwd=root, text=True, capture_output=True, check=False)
    if result.returncode:
        raise EvidenceRunnerError(result.stderr.strip() or result.stdout.strip() or "M0 capture failed")
    bundle = Path(result.stdout.strip().splitlines()[-1]).resolve()
    sign_bundle(root, bundle, private_key)
    return bundle


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fixed-job self-attested Forex evidence runner")
    parser.add_argument("--root", type=Path, default=Path("."))
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate-keypair")
    generate.add_argument("--private-key", type=Path, required=True)
    generate.add_argument("--public-key", type=Path, required=True)
    run = commands.add_parser("run-m0")
    run.add_argument("--private-key", type=Path, default=Path(".evidence-runner/m0-runner-private.pem"))
    verify = commands.add_parser("verify-m0")
    verify.add_argument("--bundle", type=Path, required=True)
    try:
        args = parser.parse_args(argv)
        root = args.root.resolve()
        if args.command == "generate-keypair":
            generate_keypair(args.private_key.resolve(), args.public_key.resolve())
            print(args.public_key.resolve())
        elif args.command == "run-m0":
            print(run_m0(root, args.private_key.resolve()))
        else:
            verify_bundle(root, args.bundle.resolve())
            print("FOREX_M0_RUNNER_ATTESTATION_VERIFIED")
        return 0
    except (EvidenceRunnerError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
