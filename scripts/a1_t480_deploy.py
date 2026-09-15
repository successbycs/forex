#!/usr/bin/env python3
"""Fixed package and T480 deployment adapter for the A1 retention service.

This is deliberately not a general Docker or SSH wrapper.  It accepts only the
reviewed A1 source set, one fixed service name, and bounded resource limits.
The bearer secret is made by the T480 script and is never copied back here.
"""
from __future__ import annotations

import argparse
import ast
import base64
import hashlib
import io
import json
import os
import re
import shlex
import subprocess
import sys
import tarfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEPLOY_ROOT = ROOT / "deploy" / "bls-n8n"
ARCHIVE = ROOT / "runs" / "local" / "a1-t480-retention.tar"
MANIFEST_NAME = "a1-t480-retention.manifest.json"
SERVICE_NAME = "forex-bls-retention"
N8N_CONTAINER = "cs-ai-lab-n8n-1"
IMAGE_REPOSITORY = "forex-bls-retention"
PYTHON_IMAGE = "python@sha256:528257d48c1da0dcecc2e725d1ae34498d60c965f1241e39cd6a85a8859bdf84"
REMOTE_ROOT = "/home/chris/.local/share/forex/a1-t480-retention"
REMOTE_ARCHIVE = REMOTE_ROOT + "/package.tar"
REMOTE_ENV = "/home/chris/.config/forex/bls-n8n-retention.env"
REMOTE_STORE = "/home/chris/.local/share/forex/bls-n8n-store"
TRANSFER_CHUNK_BYTES = 512
# A real T480 read-only probe passed at 8,343 outer command characters but
# failed at 22,903 with "The command line is too long." Windows SSH has another
# shell hop below CreateProcess's limit. Bound the whole outer command to 7,500
# characters, keeping every nested command below the 8,191-character shell cap.
WINDOWS_ARGUMENT_LIMIT = 7_500
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")


class A1DeployError(RuntimeError):
    pass


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _relative(path: Path) -> str:
    if path.is_symlink():
        raise A1DeployError("deployment source must be a regular repository file")
    resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(ROOT.resolve()):
        raise A1DeployError("deployment source must be a regular repository file")
    return resolved.relative_to(ROOT).as_posix()


def _python_dependencies(path: Path, seen: set[Path]) -> None:
    """Add the exact current `forex.*` import closure, refusing unsafe modules."""
    path = path.resolve(strict=True)
    if path in seen:
        return
    if path.is_symlink() or not path.is_relative_to((ROOT / "src" / "forex").resolve()):
        raise A1DeployError("A1 module import is outside src/forex")
    seen.add(path)
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, UnicodeDecodeError, SyntaxError) as exc:
        raise A1DeployError("unable to inspect A1 Python dependency") from exc
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.level == 1 and node.module:
            # The deployed closure is rooted at the flat forex package.  A
            # relative import such as ``from .event_capture_recovery import``
            # must be included just as an absolute ``forex.*`` import is.
            name = node.module
        elif node.level == 0 and node.module and node.module.startswith("forex."):
            name = node.module.removeprefix("forex.")
        else:
            continue
        if "." in name or not name.replace("_", "").isalnum():
            raise A1DeployError("A1 uses an unsupported relative Forex import")
        candidate = ROOT / "src" / "forex" / (name + ".py")
        if not candidate.is_file():
            raise A1DeployError("A1 imported Forex module is absent")
        _python_dependencies(candidate, seen)


def allowed_paths() -> tuple[Path, ...]:
    """The complete fixed deployment closure; callers cannot add a file."""
    fixed = [
        DEPLOY_ROOT / "Dockerfile", DEPLOY_ROOT / "Dockerfile.dockerignore", DEPLOY_ROOT / "image.env",
        ROOT / "scripts" / "run_bls_n8n_service.py", ROOT / "n8n" / "forex-bls-calendar-retention.json",
        ROOT / "src" / "forex" / "__init__.py", ROOT / "src" / "forex" / "bls_n8n_service.py",
    ]
    closure: set[Path] = set()
    _python_dependencies(ROOT / "src" / "forex" / "bls_n8n_service.py", closure)
    result = [*fixed, *sorted(closure)]
    for path in result:
        _relative(path)
    return tuple(sorted(set(result), key=_relative))


def manifest() -> dict[str, Any]:
    files = []
    for path in allowed_paths():
        raw = path.read_bytes()
        files.append({"path": _relative(path), "sha256": _sha(raw), "bytes": len(raw)})
    return {"schema_version": "forex.a1-t480-package.v1", "python_image": PYTHON_IMAGE, "files": files}


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _validate_package_archive(path: Path, expected_manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    """Reject archive additions, links, and byte changes before any extraction."""
    try:
        with tarfile.open(path, "r") as archive:
            members = archive.getmembers()
            names = [member.name for member in members]
            if (not members or names != sorted(names) or len(names) != len(set(names))
                    or any(not member.isfile() or member.issym() or member.islnk()
                           or member.name.startswith("/") or ".." in Path(member.name).parts for member in members)):
                raise A1DeployError("A1 package has unsafe members")
            manifest_member = archive.getmember(MANIFEST_NAME)
            handle = archive.extractfile(manifest_member)
            if handle is None:
                raise A1DeployError("A1 package has no manifest")
            raw_manifest = handle.read()
            value = json.loads(raw_manifest)
            if not isinstance(value, dict) or set(value) != {"schema_version", "python_image", "files"}:
                raise A1DeployError("A1 package manifest is invalid")
            files = value["files"]
            if not isinstance(files, list) or not all(isinstance(entry, dict) and set(entry) == {"path", "sha256", "bytes"}
                                                    for entry in files):
                raise A1DeployError("A1 package file manifest is invalid")
            expected_names = [MANIFEST_NAME] + [entry["path"] for entry in files]
            if names != sorted(expected_names) or len(expected_names) != len(set(expected_names)):
                raise A1DeployError("A1 package members do not exactly match manifest")
            for entry in files:
                name, digest, size = entry["path"], entry["sha256"], entry["bytes"]
                if (not isinstance(name, str) or name.startswith("/") or ".." in Path(name).parts
                        or not isinstance(digest, str) or not _DIGEST.fullmatch(digest)
                        or not isinstance(size, int) or size < 0):
                    raise A1DeployError("A1 package file entry is invalid")
                handle = archive.extractfile(name)
                if handle is None:
                    raise A1DeployError("A1 package member is missing")
                raw = handle.read()
                if len(raw) != size or _sha(raw) != digest:
                    raise A1DeployError("A1 package member does not match manifest")
    except (OSError, tarfile.TarError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise A1DeployError("A1 package cannot be verified") from exc
    if expected_manifest is not None and value != expected_manifest:
        raise A1DeployError("existing A1 package does not bind current reviewed files")
    return value


def build_package(destination: Path = ARCHIVE) -> dict[str, Any]:
    """Create a deterministic, regular-file-only tar archive at a fixed path."""
    package_manifest = manifest()
    manifest_raw = _canonical(package_manifest)
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if destination.exists() and destination.is_symlink():
        raise A1DeployError("package destination must not be a symlink")
    with tarfile.open(destination, "w", format=tarfile.USTAR_FORMAT) as archive:
        entries = [(MANIFEST_NAME, manifest_raw)] + [
            (entry["path"], (ROOT / entry["path"]).read_bytes()) for entry in package_manifest["files"]
        ]
        for name, raw in sorted(entries):
            if name.startswith("/") or ".." in Path(name).parts:
                raise A1DeployError("package entry is unsafe")
            info = tarfile.TarInfo(name)
            info.size, info.mode, info.uid, info.gid, info.mtime = len(raw), 0o644, 0, 0, 0
            archive.addfile(info, io.BytesIO(raw))
    _validate_package_archive(destination, package_manifest)
    raw = destination.read_bytes()
    return {"archive": str(destination), "archive_sha256": _sha(raw), "manifest_sha256": _sha(manifest_raw), "manifest": package_manifest}


def _read_package() -> dict[str, Any]:
    if not ARCHIVE.is_file() or ARCHIVE.is_symlink():
        return build_package()
    expected = manifest()
    value = _validate_package_archive(ARCHIVE, expected)
    return {"archive": str(ARCHIVE), "archive_sha256": _sha(ARCHIVE.read_bytes()), "manifest_sha256": _sha(_canonical(value)), "manifest": value}


def validate_limits(cpu: str, memory_mib: int, pids: int) -> tuple[str, int, int]:
    try:
        cpu_value = float(cpu)
    except ValueError as exc:
        raise A1DeployError("cpu must be a decimal") from exc
    if not 0.05 <= cpu_value <= 1.00 or cpu != f"{cpu_value:.2f}":
        raise A1DeployError("cpu must be between 0.05 and 1.00 with two decimals")
    if not 64 <= memory_mib <= 512:
        raise A1DeployError("memory-mib must be between 64 and 512")
    if not 32 <= pids <= 256:
        raise A1DeployError("pids must be between 32 and 256")
    return cpu, memory_mib, pids


def _shared() -> Any:
    from n8n_forex_adapter import shared_n8n
    return shared_n8n()


def _shared_windows_argument_length(script: str) -> int:
    """Measure the exact PowerShell/SSH argument encoding used by shared T480 transport."""
    shared_root = Path("/home/chris/projects/cs-ai-lab-infra")
    sys.path.insert(0, str(shared_root))
    try:
        from t480_core import build_ssh_command, build_wsl_powershell_command, load_transport_settings, resolve_ssh_target
        settings = load_transport_settings(shared_root / "t480" / "transport-config.json")
        # These are the same settings, config source and resolver used by the
        # shared n8n adapter's configured_target()/execute_remote() transport.
        target = resolve_ssh_target(settings, [shared_root / ".env.t480.local"])
        command = build_ssh_command(target, build_wsl_powershell_command(script, settings), settings)
        return len(subprocess.list2cmdline(command)) + 1
    finally:
        sys.path.remove(str(shared_root))


def _remote_path_guard() -> str:
    """Refuse symlinks in every fixed mutation target and its ancestors."""
    paths = [REMOTE_ROOT, REMOTE_ARCHIVE, REMOTE_ENV, REMOTE_STORE]
    return ("python3 - " + " ".join(shlex.quote(path) for path in paths)
            + " <<'PATH_GUARD'\nimport pathlib, sys\nr,a,e,s=sys.argv[1:]\npaths=[r,a,a+'.partial',e,s]+[r+'/'+n for n in ('build','deployment-state.json','configured-workflow.json','deploy.sh','deploy.sh.partial')]\nfor value in paths:\n p=pathlib.Path(value)\n if not p.is_absolute() or '..' in p.parts: raise SystemExit(61)\n if any(x.is_symlink() for x in (p,*p.parents)): raise SystemExit(61)\nPATH_GUARD\n")


def _service_preflight_script() -> str:
    return (
        "set -euo pipefail\n"
        "docker container inspect '" + SERVICE_NAME + "' --format "
        "'{\"exists\":true,\"status\":\"{{.State.Status}}\",\"image\":\"{{.Config.Image}}\",\"network\":\"{{.HostConfig.NetworkMode}}\",\"ports\":{{json .NetworkSettings.Ports}}}' "
        "2>/dev/null || printf '{\"exists\":false}\\n'"
    )


def _staging_scripts(raw: bytes, destination: str) -> list[str]:
    """Generate hash-checked transfers for the two fixed application artifacts."""
    if destination not in {REMOTE_ARCHIVE, REMOTE_ROOT + "/deploy.sh"}:
        raise A1DeployError("A1 staging destination is not a fixed artifact")
    prefix = "set -euo pipefail\n" + _remote_path_guard()
    partial = shlex.quote(destination + ".partial")
    scripts = [prefix + "umask 077; install -d -m 0700 " + shlex.quote(REMOTE_ROOT)
               + "; : > " + partial + "; chmod 0600 " + partial]
    for offset in range(0, len(raw), TRANSFER_CHUNK_BYTES):
        chunk = raw[offset:offset + TRANSFER_CHUNK_BYTES]
        encoded = base64.b64encode(chunk).decode("ascii")
        check = "import hashlib,pathlib,sys;b=sys.stdin.buffer.read();p=pathlib.Path(sys.argv[1])\nif p.stat().st_size!=int(sys.argv[2]) or hashlib.sha256(b).hexdigest()!=sys.argv[3]: raise SystemExit(62)\np.open('ab').write(b)"
        scripts.append(prefix + "printf %s '" + encoded + "' | base64 -d | python3 -c "
                       + shlex.quote(check) + " " + partial + " " + str(offset) + " " + _sha(chunk))
    finish = "import hashlib,pathlib,sys;p=pathlib.Path(sys.argv[1])\nif hashlib.sha256(p.read_bytes()).hexdigest()!=sys.argv[3]: raise SystemExit(62)\np.replace(sys.argv[2])"
    scripts.append(prefix + "python3 -c " + shlex.quote(finish) + " " + partial + " "
                   + shlex.quote(destination) + " " + _sha(raw))
    return scripts


def _validate_commands(scripts: list[str]) -> None:
    if any(_shared_windows_argument_length(script) > WINDOWS_ARGUMENT_LIMIT for script in scripts):
        raise A1DeployError("A1 command exceeds the shared Windows argument limit")


def _run_staging(adapter: Any, scripts: list[str]) -> None:
    _validate_commands(scripts)
    for index, script in enumerate(scripts):
        if not adapter.execute_remote(script).get("ok"):
            phase = "setup" if index == 0 else "finalisation" if index == len(scripts) - 1 else "chunk"
            raise A1DeployError("T480 package staging " + phase + " failed")


def _stage_package(adapter: Any, package: dict[str, Any]) -> None:
    raw = ARCHIVE.read_bytes()
    if _sha(raw) != package["archive_sha256"]:
        raise A1DeployError("A1 package changed after verification")
    _run_staging(adapter, _staging_scripts(raw, REMOTE_ARCHIVE))


def _invoke_program(program: bytes) -> str:
    check = "import hashlib,pathlib,subprocess,sys;b=pathlib.Path(sys.argv[1]).read_bytes()\nif hashlib.sha256(b).hexdigest()!=sys.argv[2]: raise SystemExit(62)\nsubprocess.run(['bash','-c',b.decode()],check=True)"
    return ("set -euo pipefail\n" + _remote_path_guard() + "python3 -c " + shlex.quote(check)
            + " " + shlex.quote(REMOTE_ROOT + "/deploy.sh") + " " + _sha(program))


def _remote_script(package: dict[str, Any], *, cpu: str, memory_mib: int, pids: int, deploy: bool) -> str:
    """Return a fixed remote program; all variable data is verified fixed data."""
    cpu, memory_mib, pids = validate_limits(cpu, memory_mib, pids)
    image_tag = IMAGE_REPOSITORY + ":sha256-" + package["manifest_sha256"][:16]
    # Values here are derived from constants, package hashes, or bounded limits.
    # The caller never contributes a shell fragment, URL, path, image, or command.
    lines = [
        "set -euo pipefail",
        _remote_path_guard(),
        f"root='{REMOTE_ROOT}'", f"archive='{REMOTE_ARCHIVE}'", f"env_file='{REMOTE_ENV}'", f"store='{REMOTE_STORE}'",
        f"expected_archive='{package['archive_sha256']}'", f"expected_manifest='{package['manifest_sha256']}'", f"image='{image_tag}'", f"cpu='{cpu}'", f"memory_mib='{memory_mib}'", f"pids='{pids}'",
        "key_file='/home/chris/.config/cs-ai-lab/n8n-api-key'", "base_url='http://127.0.0.1:5678'",
        "[[ -f \"$archive\" && ! -L \"$archive\" ]] || exit 50",
        "test \"$(sha256sum \"$archive\" | awk '{print $1}')\" = \"$expected_archive\"",
        "python3 - \"$archive\" \"$expected_manifest\" <<'PY'\nimport hashlib, json, pathlib, sys, tarfile\narchive, expected = sys.argv[1:]\nwith tarfile.open(archive, 'r') as tar:\n members=tar.getmembers(); names=[m.name for m in members]\n if not members or names != sorted(names) or len(names) != len(set(names)) or any(not m.isfile() or m.issym() or m.islnk() or m.name.startswith('/') or '..' in pathlib.PurePosixPath(m.name).parts for m in members): raise SystemExit(51)\n manifest=tar.extractfile('a1-t480-retention.manifest.json')\n if manifest is None: raise SystemExit(52)\n raw=manifest.read(); value=json.loads(raw)\n if hashlib.sha256(raw).hexdigest()!=expected or set(value)!={'schema_version','python_image','files'} or not isinstance(value['files'],list): raise SystemExit(53)\n expected_names=['a1-t480-retention.manifest.json']\n for item in value['files']:\n  if not isinstance(item,dict) or set(item)!={'path','sha256','bytes'} or not isinstance(item['path'],str) or item['path'].startswith('/') or '..' in pathlib.PurePosixPath(item['path']).parts or not isinstance(item['sha256'],str) or len(item['sha256'])!=64 or any(c not in '0123456789abcdef' for c in item['sha256']) or not isinstance(item['bytes'],int) or item['bytes']<0: raise SystemExit(54)\n  expected_names.append(item['path']); member=tar.extractfile(item['path'])\n  if member is None: raise SystemExit(55)\n  body=member.read()\n  if len(body)!=item['bytes'] or hashlib.sha256(body).hexdigest()!=item['sha256']: raise SystemExit(56)\n if names != sorted(expected_names) or len(expected_names)!=len(set(expected_names)): raise SystemExit(57)\nPY",
        "rm -rf \"$root/build\"; mkdir -m 0700 \"$root/build\"; tar -xf \"$archive\" -C \"$root/build\" --no-same-owner --no-same-permissions",
        "docker build --pull=false --build-arg PYTHON_IMAGE='" + PYTHON_IMAGE + "' -f \"$root/build/deploy/bls-n8n/Dockerfile\" -t \"$image\" \"$root/build\" >/dev/null",
        "install -d -m 0700 \"$(dirname \"$env_file\")\" \"$store\"",
    ]
    if deploy:
        lines += [
            "state=\"$root/deployment-state.json\"; [[ ! -e \"$state\" && ! -L \"$state\" && ! -e \"$env_file\" && ! -L \"$env_file\" ]] || { printf 'existing A1 transaction requires explicit recovery' >&2; exit 58; }",
            "token=$(openssl rand -hex 32)",
            "[[ -r \"$key_file\" ]] || { printf 'n8n API key unavailable' >&2; exit 42; }",
            "umask 077; set -C; printf '{\"schema_version\":\"forex.a1-deployment-state.v1\",\"phase\":\"credential-create-requested\",\"package_sha256\":\"%s\"}\\n' \"$expected_archive\" > \"$state\"; set +C",
            "credential_file=$(mktemp); workflow_file=$(mktemp); response_file=$(mktemp); trap 'rm -f \"$credential_file\" \"$workflow_file\" \"$response_file\"' EXIT",
            "FOREX_A1_TOKEN=\"$token\" python3 - > \"$credential_file\" <<'PY'\nimport json, os\nprint(json.dumps({'name':'Forex A1 BLS handoff','type':'httpHeaderAuth','data':{'name':'Authorization','value':'Bearer '+os.environ['FOREX_A1_TOKEN']}}, separators=(',',':')))\nPY",
            "curl --fail-with-body --silent --show-error --max-time 30 -X POST -H 'content-type: application/json' -H \"X-N8N-API-KEY: $(<\"$key_file\")\" --data-binary @\"$credential_file\" \"$base_url/api/v1/credentials\" > \"$response_file\"",
            "credential_id=$(python3 -c 'import json,re,sys; v=json.load(open(sys.argv[1])).get(\"id\")\nif not isinstance(v,str) or not re.fullmatch(r\"[A-Za-z0-9_-]+\",v): raise SystemExit(43)\nprint(v)' \"$response_file\") || { printf 'n8n credential creation failed' >&2; exit 43; }",
            "state_tmp=$(mktemp \"$root/.state.XXXXXX\"); umask 077; printf '{\"schema_version\":\"forex.a1-deployment-state.v1\",\"phase\":\"credential-created\",\"package_sha256\":\"%s\",\"credential_id\":\"%s\"}\\n' \"$expected_archive\" \"$credential_id\" > \"$state_tmp\"; chmod 0600 \"$state_tmp\"; test ! -L \"$state\"; mv -f \"$state_tmp\" \"$state\"",
            "FOREX_A1_CREDENTIAL_ID=\"$credential_id\" python3 - \"$root/build/n8n/forex-bls-calendar-retention.json\" > \"$workflow_file\" <<'PY'\nimport json, os, sys\nw=json.load(open(sys.argv[1]))\nfor n in w['nodes']:\n if n.get('id')=='retain': n['credentials']={'httpHeaderAuth':{'id':os.environ['FOREX_A1_CREDENTIAL_ID'],'name':'Forex A1 BLS handoff'}}\nprint(json.dumps({k:w[k] for k in ('name','nodes','connections','settings')},separators=(',',':')))\nPY",
            "workflow_sha=$(sha256sum \"$workflow_file\" | awk '{print $1}')",
            "curl --fail-with-body --silent --show-error --max-time 30 -X POST -H 'content-type: application/json' -H \"X-N8N-API-KEY: $(<\"$key_file\")\" --data-binary @\"$workflow_file\" \"$base_url/api/v1/workflows\" > \"$response_file\"",
            "workflow_id=$(python3 -c 'import json,re,sys; v=json.load(open(sys.argv[1])).get(\"id\")\nif not isinstance(v,str) or not re.fullmatch(r\"[A-Za-z0-9_-]+\",v): raise SystemExit(44)\nprint(v)' \"$response_file\") || { printf 'n8n workflow creation failed' >&2; exit 44; }",
            "state_tmp=$(mktemp \"$root/.state.XXXXXX\"); umask 077; printf '{\"schema_version\":\"forex.a1-deployment-state.v1\",\"phase\":\"workflow-created\",\"package_sha256\":\"%s\",\"credential_id\":\"%s\",\"workflow_id\":\"%s\"}\\n' \"$expected_archive\" \"$credential_id\" \"$workflow_id\" > \"$state_tmp\"; chmod 0600 \"$state_tmp\"; test ! -L \"$state\"; mv -f \"$state_tmp\" \"$state\"",
            "export_file=\"$root/configured-workflow.json\"; [[ ! -e \"$export_file\" && ! -L \"$export_file\" ]] || { printf 'configured workflow export requires explicit recovery' >&2; exit 59; }",
            "curl --fail-with-body --silent --show-error --max-time 30 -H \"X-N8N-API-KEY: $(<\"$key_file\")\" \"$base_url/api/v1/workflows/$workflow_id\" > \"$export_file\"",
            "workflow_sha=$(sha256sum \"$export_file\" | awk '{print $1}')",
            "state_tmp=$(mktemp \"$root/.state.XXXXXX\"); umask 077; printf '{\"schema_version\":\"forex.a1-deployment-state.v1\",\"phase\":\"workflow-created\",\"package_sha256\":\"%s\",\"credential_id\":\"%s\",\"workflow_id\":\"%s\",\"workflow_sha256\":\"sha256:%s\"}\\n' \"$expected_archive\" \"$credential_id\" \"$workflow_id\" \"$workflow_sha\" > \"$state_tmp\"; chmod 0600 \"$state_tmp\"; test ! -L \"$state\"; mv -f \"$state_tmp\" \"$state\"",
            "umask 077; set -C; { printf '%s\\n' 'FOREX_BLS_N8N_BIND_HOST=127.0.0.1' 'FOREX_BLS_N8N_PORT=8091' 'FOREX_BLS_N8N_STORE=/data'; printf 'FOREX_BLS_N8N_HANDOFF_TOKEN=%s\\n' \"$token\"; printf 'FOREX_BLS_N8N_WORKFLOW_ID=%s\\n' \"$workflow_id\"; printf 'FOREX_BLS_N8N_WORKFLOW_SHA256=sha256:%s\\n' \"$workflow_sha\"; } > \"$env_file\"; set +C; chmod 0600 \"$env_file\"",
            "unset token",
            "docker run --rm --network none --read-only --cap-drop ALL --cap-add CHOWN --cap-add FOWNER --security-opt no-new-privileges --user 0:0 --mount type=bind,src=\"$store\",dst=/data \"$image\" /bin/sh -c 'chown 65532:65532 /data && chmod 0700 /data' >/dev/null",
            "test \"$(stat -c '%u:%g:%a' \"$store\")\" = '65532:65532:700'",
            "docker run -d --name '" + SERVICE_NAME + "' --network 'container:" + N8N_CONTAINER + "' --read-only --cap-drop ALL --security-opt no-new-privileges --cpus \"$cpu\" --memory \"${memory_mib}m\" --pids-limit \"$pids\" --env-file \"$env_file\" --mount type=bind,src=\"$store\",dst=/data \"$image\" >/dev/null",
            "docker container inspect '" + SERVICE_NAME + "' --format '{\"status\":\"{{.State.Status}}\",\"image\":\"{{.Config.Image}}\",\"network\":\"{{.HostConfig.NetworkMode}}\",\"ports\":{{json .NetworkSettings.Ports}}}'",
        ]
    return "\n".join(lines)


def inspect() -> dict[str, Any]:
    package = _read_package()
    adapter = _shared()
    result = adapter.execute_remote(_service_preflight_script())
    if not result.get("ok"):
        raise A1DeployError("T480 deployment inspection failed")
    return {"tool_id": "forex_a1_t480_deploy", "operation": "inspect", "package": {k: package[k] for k in ("archive_sha256", "manifest_sha256")}, "service": json.loads(result["stdout"])}


def deploy(cpu: str, memory_mib: int, pids: int) -> dict[str, Any]:
    validate_limits(cpu, memory_mib, pids)
    package = _read_package()
    adapter = _shared()
    program = _remote_script(package, cpu=cpu, memory_mib=memory_mib, pids=pids, deploy=True).encode()
    raw = ARCHIVE.read_bytes()
    if _sha(raw) != package["archive_sha256"]:
        raise A1DeployError("A1 package changed after verification")
    archive_scripts = _staging_scripts(raw, REMOTE_ARCHIVE)
    program_scripts = _staging_scripts(program, REMOTE_ROOT + "/deploy.sh")
    invocation = _invoke_program(program)
    _validate_commands([*archive_scripts, *program_scripts, invocation, _service_preflight_script()])
    preflight = adapter.execute_remote(_service_preflight_script())
    if not preflight.get("ok"):
        raise A1DeployError("T480 service preflight failed")
    existing = json.loads(preflight["stdout"])
    if existing.get("exists") is True:
        return {"tool_id": "forex_a1_t480_deploy", "operation": "deploy", "package": {k: package[k] for k in ("archive_sha256", "manifest_sha256")}, "service": existing, "created": False, "secret_returned": False}
    _run_staging(adapter, archive_scripts)
    _run_staging(adapter, program_scripts)
    result = adapter.execute_remote(invocation)
    # The secret is never included in this response, even if a remote error was verbose.
    if not result.get("ok"):
        raise A1DeployError("T480 deployment failed; inspect the T480 service locally")
    return {"tool_id": "forex_a1_t480_deploy", "operation": "deploy", "package": {k: package[k] for k in ("archive_sha256", "manifest_sha256")}, "service": json.loads(result["stdout"]), "secret_returned": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fixed A1 T480 BLS retention deployer")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("package")
    sub.add_parser("inspect")
    deploy_parser = sub.add_parser("deploy")
    deploy_parser.add_argument("--approve", action="store_true")
    deploy_parser.add_argument("--cpu", required=True)
    deploy_parser.add_argument("--memory-mib", type=int, required=True)
    deploy_parser.add_argument("--pids", type=int, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "package":
            result = {"tool_id": "forex_a1_t480_deploy", "operation": "package", **build_package()}
        elif args.command == "inspect":
            result = inspect()
        else:
            if not args.approve:
                parser.error("deploy requires --approve")
            result = deploy(args.cpu, args.memory_mib, args.pids)
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0
    except (A1DeployError, OSError, ValueError, tarfile.TarError, json.JSONDecodeError) as exc:
        print(json.dumps({"tool_id": "forex_a1_t480_deploy", "ok": False, "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
