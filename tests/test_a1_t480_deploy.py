import json
import os
import shutil
import subprocess
import tarfile

import pytest

from scripts import a1_t480_deploy as deploy


def test_package_is_deterministic_regular_files_and_binds_manifest(tmp_path, monkeypatch):
    first = tmp_path / "first.tar"
    second = tmp_path / "second.tar"
    one = deploy.build_package(first)
    two = deploy.build_package(second)
    assert first.read_bytes() == second.read_bytes()
    assert one["archive_sha256"] == two["archive_sha256"]
    with tarfile.open(first) as archive:
        assert all(member.isfile() and not member.issym() and not member.islnk() for member in archive.getmembers())
        names = archive.getnames()
        assert names == sorted(names)
        assert all(not name.startswith("/") and ".." not in name.split("/") for name in names)
        data = json.load(archive.extractfile(deploy.MANIFEST_NAME))
    assert data == deploy.manifest()


def test_package_includes_relative_forex_import_closure():
    paths = {path.relative_to(deploy.ROOT).as_posix() for path in deploy.allowed_paths()}
    assert "src/forex/event_capture_recovery.py" in paths


def test_manifest_refuses_symlinked_source(monkeypatch, tmp_path):
    unsafe = tmp_path / "unsafe.py"
    unsafe.symlink_to(deploy.ROOT / "src" / "forex" / "bls_n8n_service.py")
    monkeypatch.setattr(deploy, "allowed_paths", lambda: (unsafe,))
    with pytest.raises(deploy.A1DeployError, match="regular repository file"):
        deploy.manifest()


def test_read_package_refuses_extra_or_changed_members(monkeypatch, tmp_path):
    archive = tmp_path / "package.tar"
    deploy.build_package(archive)
    monkeypatch.setattr(deploy, "ARCHIVE", archive)
    with tarfile.open(archive, "a") as handle:
        info = tarfile.TarInfo("unexpected.txt")
        info.size = 1
        handle.addfile(info, __import__("io").BytesIO(b"x"))
    with pytest.raises(deploy.A1DeployError, match="unsafe members|exactly match"):
        deploy._read_package()


@pytest.mark.parametrize("cpu,memory,pids", [("0.04", 64, 32), ("0.50", 63, 32), ("0.50", 64, 257), ("1", 64, 32)])
def test_limits_are_bounded(cpu, memory, pids):
    with pytest.raises(deploy.A1DeployError):
        deploy.validate_limits(cpu, memory, pids)


def test_remote_program_has_only_fixed_deploy_surface(tmp_path, monkeypatch):
    package = deploy.build_package(tmp_path / "package.tar")
    monkeypatch.setattr(deploy, "ARCHIVE", tmp_path / "package.tar")
    script = deploy._remote_script(package, cpu="0.25", memory_mib=128, pids=64, deploy=True)
    assert "--network 'container:cs-ai-lab-n8n-1'" in script
    assert "--read-only --cap-drop ALL --security-opt no-new-privileges" in script
    assert "-p " not in script and "--publish" not in script
    assert "openssl rand -hex 32" in script
    assert "unset token" in script
    assert "docker container inspect 'forex-bls-retention'" in script
    assert "$(dirname \"$env_file\")" in script
    assert "eval" not in script
    assert "base_url='http://127.0.0.1:5678'" in script
    assert '"$base_url/api/v1/credentials"' in script
    assert '"$base_url/api/v1/workflows"' in script
    assert "--data-binary @\"$workflow_file\"" in script
    assert "docker build" in script and ">/dev/null" in script
    assert "--user 0:0" in script and "chown 65532:65532 /data" in script
    assert "--cap-add CHOWN --cap-add FOWNER" in script
    assert "stat -c '%u:%g:%a'" in script
    assert "python3 - \"$archive\" \"$expected_manifest\"" in script
    assert len(script) < 20_000


def test_chunk_uses_actual_shared_windows_encoding_under_limit(tmp_path, monkeypatch):
    monkeypatch.setenv("T480_SSH_TARGET", "chris@t480")
    package = deploy.build_package(tmp_path / "package.tar")
    monkeypatch.setattr(deploy, "ARCHIVE", tmp_path / "package.tar")
    program = deploy._remote_script(package, cpu="0.25", memory_mib=128, pids=64, deploy=True).encode()
    scripts = (deploy._staging_scripts(deploy.ARCHIVE.read_bytes(), deploy.REMOTE_ARCHIVE)
               + deploy._staging_scripts(program, deploy.REMOTE_ROOT + "/deploy.sh")
               + [deploy._invoke_program(program)])
    assert deploy.TRANSFER_CHUNK_BYTES == 512
    assert max(map(deploy._shared_windows_argument_length, scripts)) <= deploy.WINDOWS_ARGUMENT_LIMIT
    assert deploy._shared_windows_argument_length(program.decode()) > deploy.WINDOWS_ARGUMENT_LIMIT


@pytest.mark.parametrize("optimization", ["0", "1"])
def test_fixed_program_stages_and_executes_only_when_hash_matches(tmp_path, monkeypatch, optimization):
    monkeypatch.setenv("PYTHONOPTIMIZE", optimization)
    root = tmp_path / "remote"
    monkeypatch.setattr(deploy, "REMOTE_ROOT", str(root))
    monkeypatch.setattr(deploy, "REMOTE_ARCHIVE", str(root / "package.tar"))
    monkeypatch.setattr(deploy, "REMOTE_ENV", str(tmp_path / "service.env"))
    monkeypatch.setattr(deploy, "REMOTE_STORE", str(tmp_path / "store"))
    program = b"printf 'staged-ok\\n'\n" + b"# padding\n" * 120
    class LocalShell:
        def execute_remote(self, script):
            result = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
            return {"ok": result.returncode == 0, "stdout": result.stdout}
    deploy._run_staging(LocalShell(), deploy._staging_scripts(program, str(root / "deploy.sh")))
    assert (root / "deploy.sh").read_bytes() == program
    assert (root / "deploy.sh").stat().st_mode & 0o777 == 0o600
    invocation = deploy._invoke_program(program)
    result = LocalShell().execute_remote(invocation)
    assert result["ok"] and "staged-ok" in result["stdout"]
    (root / "deploy.sh").write_bytes(program + b"# tampered\n")
    result = LocalShell().execute_remote(invocation)
    assert not result["ok"] and not result["stdout"]


@pytest.mark.parametrize("optimization", ["0", "1"])
def test_chunk_hash_offset_and_final_hash_are_verified(tmp_path, monkeypatch, optimization):
    monkeypatch.setenv("PYTHONOPTIMIZE", optimization)
    import base64
    root = tmp_path / "remote"
    monkeypatch.setattr(deploy, "REMOTE_ROOT", str(root))
    monkeypatch.setattr(deploy, "REMOTE_ARCHIVE", str(root / "package.tar"))
    monkeypatch.setattr(deploy, "REMOTE_ENV", str(tmp_path / "service.env"))
    monkeypatch.setattr(deploy, "REMOTE_STORE", str(tmp_path / "store"))
    scripts = deploy._staging_scripts(b"expected", str(root / "package.tar"))
    run = lambda script: subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    assert run(scripts[0]).returncode == 0
    corrupt = scripts[1].replace(base64.b64encode(b"expected").decode(), base64.b64encode(b"tampered").decode())
    assert run(corrupt).returncode != 0
    partial = root / "package.tar.partial"
    assert partial.read_bytes() == b""
    assert run(scripts[1]).returncode == 0
    assert run(scripts[1]).returncode != 0
    assert partial.read_bytes() == b"expected"
    partial.write_bytes(b"tampered")
    assert run(scripts[-1]).returncode != 0
    assert not (root / "package.tar").exists()


def test_long_configured_target_is_counted_and_refused_before_transport(tmp_path, monkeypatch):
    package = deploy.build_package(tmp_path / "package.tar")
    monkeypatch.setattr(deploy, "_read_package", lambda: package)
    monkeypatch.setattr(deploy, "ARCHIVE", tmp_path / "package.tar")
    monkeypatch.setattr(deploy, "_shared", lambda: object())
    monkeypatch.setenv("T480_SSH_TARGET", "chris@" + "a" * 30_000)
    assert deploy._shared_windows_argument_length("true") > deploy.WINDOWS_ARGUMENT_LIMIT
    with pytest.raises(deploy.A1DeployError, match="Windows argument limit"):
        deploy.deploy("0.25", 128, 64)


@pytest.mark.parametrize("linked", ["root", "build", "partial", "store", "ancestor"])
def test_remote_paths_refuse_symlinks_before_staging_or_deployment(tmp_path, monkeypatch, linked):
    package = deploy.build_package(tmp_path / "package.tar")
    monkeypatch.setattr(deploy, "ARCHIVE", tmp_path / "package.tar")
    root = tmp_path / "parent" / "root"
    store = tmp_path / "store"
    monkeypatch.setattr(deploy, "REMOTE_ROOT", str(root))
    monkeypatch.setattr(deploy, "REMOTE_ARCHIVE", str(root / "package.tar"))
    monkeypatch.setattr(deploy, "REMOTE_STORE", str(store))
    monkeypatch.setattr(deploy, "REMOTE_ENV", str(tmp_path / "service.env"))
    target = {"root": root, "build": root / "build", "partial": root / "package.tar.partial",
              "store": store, "ancestor": root.parent}[linked]
    target.parent.mkdir(parents=True, exist_ok=True)
    victim = tmp_path / "victim"
    victim.mkdir()
    marker = victim / "untouched"
    marker.write_text("preserve")
    target.symlink_to(victim, target_is_directory=True)
    class LocalShell:
        def execute_remote(self, script):
            result = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
            assert result.returncode == 61
            return {"ok": False}
    with pytest.raises(deploy.A1DeployError, match="staging setup failed"):
        deploy._stage_package(LocalShell(), package)
    script = deploy._remote_script(package, cpu="0.25", memory_mib=128, pids=64, deploy=True)
    result = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    assert result.returncode == 61
    assert list(victim.iterdir()) == [marker]
    assert marker.read_text() == "preserve"


@pytest.mark.parametrize("fail_at", [1, 3])
def test_remote_partial_failure_persists_transaction_and_refuses_retry(tmp_path, monkeypatch, fail_at):
    package = deploy.build_package(tmp_path / "package.tar")
    remote_root = tmp_path / "remote"
    remote_archive = remote_root / "package.tar"
    remote_root.mkdir()
    shutil.copyfile(tmp_path / "package.tar", remote_archive)
    monkeypatch.setattr(deploy, "REMOTE_ROOT", str(remote_root))
    monkeypatch.setattr(deploy, "REMOTE_ARCHIVE", str(remote_archive))
    monkeypatch.setattr(deploy, "REMOTE_ENV", str(tmp_path / "service.env"))
    monkeypatch.setattr(deploy, "REMOTE_STORE", str(tmp_path / "store"))
    tools = tmp_path / "tools"
    tools.mkdir()
    (tools / "docker").write_text("#!/bin/sh\nexit 0\n")
    (tools / "curl").write_text("#!/bin/sh\nn=$(cat \"$TEST_CURL_COUNT\" 2>/dev/null || echo 0); n=$((n+1)); echo \"$n\" > \"$TEST_CURL_COUNT\"; [ \"$n\" = \"$TEST_FAIL_AT\" ] && exit 77; [ \"$n\" = 1 ] && { printf '%s' '{\"id\":\"cred-1\"}'; exit 0; }; [ \"$n\" = 2 ] && { printf '%s' '{\"id\":\"workflow-1\"}'; exit 0; }; exit 77\n")
    os.chmod(tools / "docker", 0o755); os.chmod(tools / "curl", 0o755)
    env = {**os.environ, "PATH": str(tools) + os.pathsep + os.environ["PATH"], "TEST_CURL_COUNT": str(tmp_path / "curl-count"), "TEST_FAIL_AT": str(fail_at)}
    key = tmp_path / "n8n-key"
    key.write_text("test-key")
    script = deploy._remote_script(package, cpu="0.25", memory_mib=128, pids=64, deploy=True)
    script = script.replace("key_file='/home/chris/.config/cs-ai-lab/n8n-api-key'", f"key_file='{key}'")
    result = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True)
    assert result.returncode == 77
    state_file = remote_root / "deployment-state.json"
    state = json.loads(state_file.read_text())
    assert state_file.stat().st_mode & 0o777 == 0o600
    if fail_at == 1:
        assert state["phase"] == "credential-create-requested"
    else:
        assert state["phase"] == "workflow-created"
        assert state["credential_id"] == "cred-1" and state["workflow_id"] == "workflow-1"
    assert not (tmp_path / "service.env").exists()
    retry = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True)
    assert retry.returncode == 58
    assert int((tmp_path / "curl-count").read_text()) == fail_at
    assert json.loads(state_file.read_text()) == state


def test_deploy_response_does_not_include_remote_secret(monkeypatch, tmp_path):
    package = deploy.build_package(tmp_path / "package.tar")
    monkeypatch.setattr(deploy, "ARCHIVE", tmp_path / "package.tar")
    monkeypatch.setattr(deploy, "_read_package", lambda: package)

    class Shared:
        def __init__(self):
            self.calls = []
        def execute_remote(self, script):
            self.calls.append(script)
            assert "super-secret" not in script
            if "subprocess.run(" in script:
                return {"ok": True, "stdout": '{"status":"running","ports":{}}'}
            if "docker container inspect" in script:
                return {"ok": True, "stdout": '{"exists":false}'}
            return {"ok": True, "stdout": ""}
    shared = Shared()
    monkeypatch.setattr(deploy, "_shared", lambda: shared)
    result = deploy.deploy("0.25", 128, 64)
    assert result["secret_returned"] is False
    assert result["service"]["status"] == "running"
    assert "token" not in json.dumps(result).lower()
    assert all(len(script) < 20_000 for script in shared.calls)


def test_existing_service_is_reported_before_package_stage(monkeypatch, tmp_path):
    package = deploy.build_package(tmp_path / "package.tar")
    monkeypatch.setattr(deploy, "ARCHIVE", tmp_path / "package.tar")
    monkeypatch.setattr(deploy, "_read_package", lambda: package)
    class Shared:
        def execute_remote(self, script):
            assert "install -d" not in script
            return {"ok": True, "stdout": '{"exists":true,"status":"running","ports":{}}'}
    monkeypatch.setattr(deploy, "_shared", lambda: Shared())
    result = deploy.deploy("0.25", 128, 64)
    assert result["created"] is False and result["service"]["status"] == "running"


def test_inspect_reports_name_conflict_without_mutation(monkeypatch, tmp_path):
    package = deploy.build_package(tmp_path / "package.tar")
    monkeypatch.setattr(deploy, "ARCHIVE", tmp_path / "package.tar")
    monkeypatch.setattr(deploy, "_read_package", lambda: package)
    class Shared:
        def execute_remote(self, script):
            assert "docker run" not in script
            return {"ok": True, "stdout": '{"exists":true,"status":"running","ports":{}}'}
    monkeypatch.setattr(deploy, "_shared", lambda: Shared())
    assert deploy.inspect()["service"]["exists"] is True
