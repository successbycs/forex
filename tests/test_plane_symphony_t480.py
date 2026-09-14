from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
PROJECT_ID = "11111111-1111-4111-8111-111111111111"


def state_id(number: int) -> str:
    return f"22222222-2222-4222-8222-{number:012d}"


SPEC = importlib.util.spec_from_file_location("plane_symphony_t480", ROOT / "scripts" / "plane_symphony_t480.py")
assert SPEC and SPEC.loader
runtime = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runtime)


def make_env(tmp_path: Path, **overrides: str) -> Path:
    values = {
        "FOREX_PLANE_URL": "http://127.0.0.1:8080",
        "FOREX_PLANE_API_TOKEN": "plane-secret-token",
        "FOREX_PLANE_WORKSPACE": "Forex",
        "FOREX_PLANE_PROJECT": "Forex-Delivery",
        "FOREX_SYMPHONY_BASELINE_REVISION": "a" * 40,
    }
    values.update(overrides)
    path = tmp_path / "symphony-h5.env"
    path.write_text("\n".join(f"{key}={value}" for key, value in values.items()) + "\n", encoding="utf-8")
    path.chmod(0o600)
    return path


class Response:
    def __init__(self, payload=b'{"results": []}', status=200): self.payload, self.status = payload, status
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def getcode(self): return self.status
    def read(self): return self.payload


opener_requests: list[object] = []


def fake_opener(request, timeout):
    opener_requests.append(request)
    assert timeout == 10
    assert "/projects/" in request.full_url
    return Response()


def test_local_env_requires_exact_mode_and_allows_no_extra_keys(tmp_path: Path):
    path = make_env(tmp_path)
    assert runtime.load_local_env(path)["FOREX_PLANE_WORKSPACE"] == "Forex"
    path.chmod(0o640)
    with pytest.raises(runtime.H5RuntimeError, match="mode 0600"):
        runtime.load_local_env(path)
    path = make_env(tmp_path, EXTRA="not-permitted")
    with pytest.raises(runtime.H5RuntimeError, match="unsupported"):
        runtime.load_local_env(path)


@pytest.mark.parametrize("url", ["https://user:pass@plane.example", "file:///tmp/plane", "https://plane.example/path"])
def test_plane_settings_refuse_non_origin_urls(url: str):
    with pytest.raises(runtime.H5RuntimeError):
        runtime.validate_plane_settings({
            "FOREX_PLANE_URL": url, "FOREX_PLANE_API_TOKEN": "secret",
            "FOREX_PLANE_WORKSPACE": "Forex", "FOREX_PLANE_PROJECT": "Forex-Delivery",
        })


def test_fixed_v1_client_uses_only_work_items_and_redacts_token():
    opener_requests.clear()
    settings = {"FOREX_PLANE_URL": "http://127.0.0.1:8080", "FOREX_PLANE_API_TOKEN": "secret-token",
                "FOREX_PLANE_WORKSPACE": "Forex", "FOREX_PLANE_PROJECT": "Forex-Delivery", "FOREX_SYMPHONY_BASELINE_REVISION": "a" * 40}
    client = runtime.PlaneWorkItemsV1(settings, fake_opener, project_id=PROJECT_ID)
    assert client.probe() == {"endpoint": "v1-work-items", "status": "PASS", "item_count": 0}
    request = opener_requests[-1]
    assert request.full_url.endswith(f"/api/v1/workspaces/Forex/projects/{PROJECT_ID}/work-items/?expand=state&per_page=100")
    assert request.get_method() == "GET"
    assert request.get_header("X-api-key") == "secret-token"
    assert "secret-token" not in str(runtime.redact({"api_token": "secret-token"}))


def test_work_item_identity_store_binds_exact_ids_and_refuses_identity_drift(tmp_path: Path):
    state_dir = tmp_path / "state"; state_dir.mkdir(mode=0o700)
    settings = {"FOREX_PLANE_URL": "http://127.0.0.1:8080", "FOREX_PLANE_API_TOKEN": "secret-token",
                "FOREX_PLANE_WORKSPACE": "Forex", "FOREX_PLANE_PROJECT": "Forex-Delivery", "FOREX_SYMPHONY_BASELINE_REVISION": "a" * 40}
    client = runtime.PlaneWorkItemsV1(settings, project_id=PROJECT_ID, state_dir=state_dir)
    h5_id = "33333333-3333-4333-8333-333333333333"
    name = "[FOREX:H5] Plane connectivity"
    client._items = lambda: [{"id": h5_id, "name": name, "state": {"name": "Blocked"}}]  # type: ignore[method-assign]
    assert client.find_issue("FOREX:H5", name)["id"] == h5_id
    assert runtime.WorkItemIdentityStore(PROJECT_ID, state_dir).read() == {"FOREX:H5": h5_id}
    client._items = lambda: [{"id": "44444444-4444-4444-8444-444444444444", "name": name, "state": {"name": "Ready"}}]  # type: ignore[method-assign]
    with pytest.raises(runtime.H5RuntimeError, match="identity mismatch"):
        client.find_issue("FOREX:H5", name)


def test_work_item_identity_refuses_duplicate_exact_names_but_ignores_prefix_lookalikes(tmp_path: Path):
    state_dir = tmp_path / "state"; state_dir.mkdir(mode=0o700)
    settings = {"FOREX_PLANE_URL": "http://127.0.0.1:8080", "FOREX_PLANE_API_TOKEN": "secret-token",
                "FOREX_PLANE_WORKSPACE": "Forex", "FOREX_PLANE_PROJECT": "Forex-Delivery", "FOREX_SYMPHONY_BASELINE_REVISION": "a" * 40}
    client = runtime.PlaneWorkItemsV1(settings, project_id=PROJECT_ID, state_dir=state_dir)
    name = "[FOREX:H5] Plane connectivity"
    client._items = lambda: [{"id": "33333333-3333-4333-8333-333333333333", "name": "[FOREX:H5] copied", "state": {"name": "Ready"}}]  # type: ignore[method-assign]
    assert client.find_issue("FOREX:H5", name) is None
    client._items = lambda: [
        {"id": "33333333-3333-4333-8333-333333333333", "name": name, "state": {"name": "Ready"}},
        {"id": "44444444-4444-4444-8444-444444444444", "name": name, "state": {"name": "Ready"}},
    ]  # type: ignore[method-assign]
    with pytest.raises(runtime.H5RuntimeError, match="ambiguous"):
        client.find_issue("FOREX:H5", name)


@pytest.mark.parametrize("payload", [b"[]", b'{"results": {}}', b"not-json"])
def test_fixed_v1_client_refuses_unexpected_or_invalid_payload(payload: bytes):
    settings = {"FOREX_PLANE_URL": "http://127.0.0.1:8080", "FOREX_PLANE_API_TOKEN": "secret",
                "FOREX_PLANE_WORKSPACE": "Forex", "FOREX_PLANE_PROJECT": "Forex-Delivery", "FOREX_SYMPHONY_BASELINE_REVISION": "a" * 40}
    with pytest.raises(runtime.H5RuntimeError):
        runtime.PlaneWorkItemsV1(settings, lambda *_args, **_kwargs: Response(payload), project_id=PROJECT_ID).probe()


def fake_run_factory(*, dirty=False):
    calls: list[list[str]] = []
    def run(args, **_kwargs):
        args = list(args); calls.append(args)
        if args[:3] == ["git", "status", "--porcelain=v1"]:
            return subprocess.CompletedProcess(args, 0, " M tracked\n" if dirty else "", "")
        if args[:2] == ["git", "rev-parse"]:
            return subprocess.CompletedProcess(args, 0, "a" * 40 + "\n", "")
        return subprocess.CompletedProcess(args, 0, "ok\n", "")
    return run, calls


def test_preflight_checks_resources_commands_plane_and_clean_baseline(tmp_path: Path):
    env_file = make_env(tmp_path)
    meminfo = tmp_path / "meminfo"
    meminfo.write_text("MemAvailable:       5242880 kB\n", encoding="utf-8")
    run, calls = fake_run_factory()
    adapter = runtime.RuntimeAdapter(run=run, disk_usage=lambda _: SimpleNamespace(free=16 * 1024**3),
        meminfo_path=meminfo, env_file=env_file, opener=fake_opener)
    report = adapter.preflight()
    assert report["status"] == "PASS"
    assert report["baseline_revision"] == "a" * 40
    assert {tuple(call[:2]) for call in calls} >= {("git", "--version"), ("systemctl", "--user"), ("codex", "app-server")}
    assert {(call[2], call[3]) for call in calls if call[:2] == ["git", "cat-file"]} == {
        ("-e", f"{'a' * 40}:{path}") for path in runtime.DEPLOYABLE_H5_PATHS
    }


def test_preflight_refuses_clean_baseline_without_every_h5_runtime_path(tmp_path: Path):
    env_file = make_env(tmp_path)
    meminfo = tmp_path / "meminfo"
    meminfo.write_text("MemAvailable:       5242880 kB\n", encoding="utf-8")
    run, _ = fake_run_factory()
    def missing_package_path(args, **kwargs):
        result = run(args, **kwargs)
        if list(args)[:3] == ["git", "cat-file", "-e"]:
            return subprocess.CompletedProcess(args, 1, "", "absent")
        return result
    observed = []
    adapter = runtime.RuntimeAdapter(run=missing_package_path, disk_usage=lambda _: SimpleNamespace(free=16 * 1024**3),
        meminfo_path=meminfo, env_file=env_file, opener=lambda *_args, **_kwargs: observed.append(True))
    with pytest.raises(runtime.H5RuntimeError, match="DEPLOYABLE_REVISION_REQUIRED"):
        adapter.preflight()
    assert observed == []


def test_dirty_or_under_capacity_preflight_fails_closed_before_http(tmp_path: Path):
    env_file = make_env(tmp_path)
    meminfo = tmp_path / "meminfo"
    meminfo.write_text("MemAvailable:       1024 kB\n", encoding="utf-8")
    run, _ = fake_run_factory(dirty=True)
    called = []
    adapter = runtime.RuntimeAdapter(run=run, disk_usage=lambda _: SimpleNamespace(free=1), meminfo_path=meminfo,
        env_file=env_file, opener=lambda *_args, **_kwargs: called.append(True))
    with pytest.raises(runtime.H5RuntimeError, match="memory"):
        adapter.preflight()
    assert called == []


def test_install_refuses_dirty_baseline_without_writing_a_service(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    env_file = make_env(tmp_path)
    meminfo = tmp_path / "meminfo"
    meminfo.write_text("MemAvailable:       5242880 kB\n", encoding="utf-8")
    run, _ = fake_run_factory(dirty=True)
    user_unit = tmp_path / "systemd"
    monkeypatch.setattr(runtime, "USER_UNIT_DIR", user_unit)
    adapter = runtime.RuntimeAdapter(run=run, disk_usage=lambda _: SimpleNamespace(free=16 * 1024**3),
        meminfo_path=meminfo, env_file=env_file, opener=fake_opener)
    with pytest.raises(runtime.H5RuntimeError, match="dirty"):
        adapter.install()
    assert not user_unit.exists()


def test_controller_and_systemd_operations_are_a_fixed_allowlist(tmp_path: Path):
    env_file = make_env(tmp_path)
    run, calls = fake_run_factory()
    adapter = runtime.RuntimeAdapter(run=run, disk_usage=lambda _: SimpleNamespace(free=16 * 1024**3),
        meminfo_path=(tmp_path / "no-memory"), env_file=env_file, opener=fake_opener)
    with pytest.raises(runtime.H5RuntimeError, match="unsupported"):
        adapter.systemctl("restart")
    with pytest.raises(runtime.H5RuntimeError, match="unsupported"):
        adapter.controller_once("generic-shell")
    assert calls == []



def test_service_contract_is_a_user_service_with_bounded_two_worker_limits():
    service = (ROOT / "t480" / "forex-symphony-h5.service").read_text(encoding="utf-8")
    assert "--user" not in service  # systemd invokes a user unit, no privileged wrapper.
    assert "run-once --loop" in service
    assert "CPUQuota=200%" in service and "MemoryMax=3G" in service and "TasksMax=256" in service
    assert "NoNewPrivileges=true" in service and "Docker" not in service


def test_runner_uses_private_clone_and_individual_systemd_limits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repository, state = tmp_path / "repository", tmp_path / "state"
    repository.mkdir()
    monkeypatch.setattr(runtime, "REPOSITORY_DIR", repository)
    monkeypatch.setattr(runtime, "STATE_DIR", state)
    calls: list[list[str]] = []
    def run(args, **_kwargs):
        calls.append(list(args)); return subprocess.CompletedProcess(args, 0, "", "")
    runner = runtime.CodexAppServerRunner(baseline_revision="a" * 40, run=run, wait_for_socket=lambda _path: True)
    worktree = tmp_path / "worktrees" / "h5"
    run_id = runner.start(task_id="H5", worktree=worktree, prompt="safe task", limits={"cpu": 1, "memory_mib": 1536, "pids": 128}, idempotency_key="b" * 32)
    assert run_id == "b" * 32
    assert calls[0][:5] == ["git", "-C", str(repository), "worktree", "add"]
    host, worker = calls[1], calls[2]
    assert "app-server" in host and any(value.startswith("unix://") for value in host)
    assert "--property=PrivateNetwork=yes" not in host
    assert "--property=RuntimeMaxSec=1800" in host
    assert "--config" in host
    assert host[host.index("--config") + 1] == "sandbox_workspace_write.network_access=false"
    host_read_only = next(value for value in host if value.startswith("--property=BindReadOnlyPaths="))
    worker_read_only = next(value for value in worker if value.startswith("--property=BindReadOnlyPaths="))
    assert str(Path.home() / ".codex") in host_read_only
    assert str(Path.home() / ".codex") not in worker_read_only
    run_dir, ipc_dir = state / "runs" / ("b" * 32), state / "runs" / ("b" * 32) / "ipc"
    assert f"--property=BindPaths={worktree} {ipc_dir}" in host
    assert f"--property=ReadWritePaths={worktree} {ipc_dir}" in host
    assert f"--property=BindPaths={worktree} {run_dir}" not in host
    assert f"--property=BindPaths={worktree} {run_dir}" in worker
    assert any(value == f"unix://{ipc_dir / 'app-server.sock'}" for value in host)
    assert "--property=CPUQuota=100%" in worker
    assert "--property=MemoryMax=1536M" in worker
    assert "--property=TasksMax=128" in worker
    assert "--property=RuntimeMaxSec=1800" in worker
    assert "--property=NoNewPrivileges=yes" in worker
    assert "--property=PrivateNetwork=yes" in worker
    assert "--property=ProtectHome=tmpfs" in worker
    assert "/usr/bin/env" in worker and "-i" in worker
    assert not any("symphony-h5.env" in value or "plane-mcp.env" in value for value in host + worker)
    assert str(ROOT / "t480" / "plane_symphony_agent.py") in worker
    assert "--app-server-socket" in worker


def test_runner_stops_host_if_worker_launch_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repository, state = tmp_path / "repository", tmp_path / "state"
    repository.mkdir()
    monkeypatch.setattr(runtime, "REPOSITORY_DIR", repository)
    monkeypatch.setattr(runtime, "STATE_DIR", state)
    calls: list[list[str]] = []
    def run(args, **_kwargs):
        calls.append(list(args))
        return subprocess.CompletedProcess(args, 1 if args[0] == "systemd-run" and any("forex-symphony-h5-" in value and "host" not in value for value in args) else 0, "", "")
    runner = runtime.CodexAppServerRunner(baseline_revision="a" * 40, run=run, wait_for_socket=lambda _path: True)
    with pytest.raises(runtime.H5RuntimeError):
        runner.start(task_id="H5", worktree=tmp_path / "worktrees" / "h5", prompt="safe task", limits={"cpu": 1, "memory_mib": 1536, "pids": 128}, idempotency_key="b" * 32)
    assert ["systemctl", "--user", "stop", "forex-symphony-h5-host-" + "b" * 32] in calls


def test_redactor_suppresses_secret_shaped_plain_strings():
    assert runtime.redact("plane-secret-token") == "[REDACTED]"


def test_plane_html_description_is_normalized_before_idempotency_comparison():
    assert runtime.plain_plane_description("<p>Repository-governed&nbsp;task.</p>") == "Repository-governed task."
    assert runtime.plain_plane_description('<a href="https://example.invalid">Repository-governed task.</a>') != "Repository-governed task."


def test_runner_keeps_capacity_for_transitional_systemd_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(runtime, "STATE_DIR", tmp_path)
    def run(args, **_kwargs):
        return subprocess.CompletedProcess(args, 3, "activating\n", "")
    runner = runtime.CodexAppServerRunner(baseline_revision="a" * 40, run=run)
    assert runner.inspect(task_id="H5", idempotency_key="b" * 32, agent_run_id="b" * 32)["status"] == "RUNNING"


class BoardAPI:
    """Stateful fake Plane API for the intentionally tiny board bootstrap surface."""
    def __init__(self, projects=None, states=None):
        self.projects = list(projects or [])
        self.states = list(states or [])
        self.requests: list[object] = []

    def __call__(self, request, timeout):
        assert timeout == 10
        self.requests.append(request)
        url, method = request.full_url, request.get_method()
        if "/projects/" in url and "/states/" not in url:
            if method == "GET": return Response(json.dumps({"results": self.projects}).encode())
            body = json.loads(request.data.decode())
            assert body["external_source"] == runtime.BOARD_SOURCE
            assert body["external_id"] == runtime.BOARD_EXTERNAL_ID
            assert body["network"] == runtime.BOARD_NETWORK
            project = {"id": PROJECT_ID, **body}
            self.projects.append(project)
            return Response(json.dumps(project).encode(), 201)
        if "/states/" in url:
            if method == "GET": return Response(json.dumps({"results": self.states}).encode())
            body = json.loads(request.data.decode())
            assert body["color"] == runtime.REQUIRED_STATES[body["name"]]["color"]
            state = {"id": state_id(len(self.states)), **body}
            self.states.append(state)
            return Response(json.dumps(state).encode(), 201)
        raise AssertionError(f"unexpected Plane request: {method} {url}")


def test_board_bootstrap_creates_approved_fixed_project_states_and_persists_uuid(tmp_path: Path):
    settings = runtime.load_local_env(make_env(tmp_path))
    api = BoardAPI()
    report = runtime.PlaneBoardBootstrap(settings, api, tmp_path / "state").ensure()
    assert report["created_project"] is True
    assert report["project"] == {"id": PROJECT_ID, "name": "Forex Delivery", "identifier": "FXD"}
    assert report["states"] == ["Blocked", "Done", "In progress", "Ready", "Review"]
    created = [json.loads(request.data.decode()) for request in api.requests if request.get_method() == "POST"]
    assert created[0] == {"name": "Forex Delivery", "identifier": "FXD", "external_source": "forex-h5", "external_id": "forex-delivery-v1", "network": runtime.BOARD_NETWORK}
    assert {item["name"]: {"group": item["group"], "color": item["color"]} for item in created[1:]} == runtime.REQUIRED_STATES
    state_path = tmp_path / "state" / "plane-board.json"
    assert stat.S_IMODE(state_path.stat().st_mode) == 0o600
    board = runtime.load_board_state(settings, tmp_path / "state")
    assert board["project_id"] == PROJECT_ID
    assert "/projects/11111111-1111-4111-8111-111111111111/work-items/" in runtime.PlaneWorkItemsV1(settings, api, project_id=board["project_id"]).work_items_url()


def test_board_bootstrap_reuses_exact_managed_board_idempotently(tmp_path: Path):
    project = {"id": PROJECT_ID, "name": runtime.BOARD_NAME, "identifier": runtime.BOARD_IDENTIFIER,
               "external_source": runtime.BOARD_SOURCE, "external_id": runtime.BOARD_EXTERNAL_ID, "network": runtime.BOARD_NETWORK}
    states = [{"id": state_id(number), "name": name, **specification}
              for number, (name, specification) in enumerate(runtime.REQUIRED_STATES.items())]
    api = BoardAPI([project], states)
    settings = runtime.load_local_env(make_env(tmp_path))
    report = runtime.PlaneBoardBootstrap(settings, api, tmp_path / "state").ensure()
    assert report["created_project"] is False
    assert all(request.get_method() == "GET" for request in api.requests)
    assert runtime.load_board_state(settings, tmp_path / "state")["project_id"] == PROJECT_ID


def test_worker_board_verification_refuses_replacement_without_rewriting_retained_uuid(tmp_path: Path):
    settings = runtime.load_local_env(make_env(tmp_path))
    state_dir = tmp_path / "state"; state_dir.mkdir(mode=0o700)
    runtime.write_board_state(settings, PROJECT_ID, state_dir)
    replacement = {"id": "33333333-3333-4333-8333-333333333333", "name": runtime.BOARD_NAME,
                   "identifier": runtime.BOARD_IDENTIFIER, "external_source": runtime.BOARD_SOURCE,
                   "external_id": runtime.BOARD_EXTERNAL_ID, "network": runtime.BOARD_NETWORK}
    states = [{"id": state_id(number), "name": name, **specification}
              for number, (name, specification) in enumerate(runtime.REQUIRED_STATES.items())]
    with pytest.raises(runtime.H5RuntimeError, match="retained board identity mismatch"):
        runtime.PlaneBoardBootstrap(settings, BoardAPI([replacement], states), state_dir).verify_existing()
    assert runtime.load_board_state(settings, state_dir)["project_id"] == PROJECT_ID


def test_board_bootstrap_refuses_conflicting_or_ambiguous_identity(tmp_path: Path):
    settings = runtime.load_local_env(make_env(tmp_path))
    conflict = {"id": "33333333-3333-4333-8333-333333333333", "name": runtime.BOARD_NAME, "identifier": "OTHER", "network": runtime.BOARD_NETWORK}
    with pytest.raises(runtime.H5RuntimeError, match="conflicting"):
        runtime.PlaneBoardBootstrap(settings, BoardAPI([conflict]), tmp_path / "state").ensure()
    managed = {"id": PROJECT_ID, "name": runtime.BOARD_NAME, "identifier": runtime.BOARD_IDENTIFIER, "external_source": runtime.BOARD_SOURCE, "external_id": runtime.BOARD_EXTERNAL_ID, "network": runtime.BOARD_NETWORK}
    managed_two = {**managed, "id": "44444444-4444-4444-8444-444444444444"}
    with pytest.raises(runtime.H5RuntimeError, match="multiple"):
        runtime.PlaneBoardBootstrap(settings, BoardAPI([managed, managed_two]), tmp_path / "state").ensure()


def test_board_bootstrap_rejects_existing_required_state_with_wrong_group(tmp_path: Path):
    project = {"id": PROJECT_ID, "name": runtime.BOARD_NAME, "identifier": runtime.BOARD_IDENTIFIER, "external_source": runtime.BOARD_SOURCE, "external_id": runtime.BOARD_EXTERNAL_ID, "network": runtime.BOARD_NETWORK}
    api = BoardAPI([project], [{"id": state_id(1), "name": "Ready", "group": "completed", "color": runtime.REQUIRED_STATES["Ready"]["color"]}])
    settings = runtime.load_local_env(make_env(tmp_path))
    with pytest.raises(runtime.H5RuntimeError, match="wrong group"):
        runtime.PlaneBoardBootstrap(settings, api, tmp_path / "state").ensure()


def test_board_discovery_consumes_paginated_project_lists(tmp_path: Path):
    project = {"id": PROJECT_ID, "name": runtime.BOARD_NAME, "identifier": runtime.BOARD_IDENTIFIER,
               "external_source": runtime.BOARD_SOURCE, "external_id": runtime.BOARD_EXTERNAL_ID, "network": runtime.BOARD_NETWORK}
    states = [{"id": state_id(number), "name": name, **specification}
              for number, (name, specification) in enumerate(runtime.REQUIRED_STATES.items())]

    class PaginatedBoardAPI(BoardAPI):
        def __call__(self, request, timeout):
            if request.get_method() == "GET" and "/projects/?" in request.full_url and "cursor=" not in request.full_url:
                self.requests.append(request)
                return Response(b'{"results":[],"next_page_results":true,"next_cursor":"page-two"}')
            return super().__call__(request, timeout)

    settings = runtime.load_local_env(make_env(tmp_path))
    report = runtime.PlaneBoardBootstrap(settings, PaginatedBoardAPI([project], states), tmp_path / "state").ensure()
    assert report["created_project"] is False


def test_protected_board_state_binds_the_normalized_plane_origin(tmp_path: Path):
    state_dir = tmp_path / "state"
    settings = runtime.load_local_env(make_env(tmp_path))
    runtime.write_board_state(settings, PROJECT_ID, state_dir)
    compatible = dict(settings, FOREX_PLANE_URL="http://127.0.0.1:8080/")
    assert runtime.load_board_state(compatible, state_dir)["plane_origin"] == "http://127.0.0.1:8080"
    changed = dict(settings, FOREX_PLANE_URL="http://127.0.0.1:8081")
    with pytest.raises(runtime.H5RuntimeError, match="does not match"):
        runtime.load_board_state(changed, state_dir)


def test_protected_board_state_refuses_symlinked_directory_file_or_temp_target(tmp_path: Path):
    settings = runtime.load_local_env(make_env(tmp_path))
    target = tmp_path / "target"
    target.mkdir(mode=0o700)
    link_dir = tmp_path / "state-link"
    link_dir.symlink_to(target, target_is_directory=True)
    with pytest.raises(runtime.H5RuntimeError, match="directory"):
        runtime.write_board_state(settings, PROJECT_ID, link_dir)

    state_dir = tmp_path / "state"
    state_dir.mkdir(mode=0o700)
    (state_dir / "plane-board.json").symlink_to(state_dir / "missing")
    with pytest.raises(runtime.H5RuntimeError, match="target must not be symlink"):
        runtime.write_board_state(settings, PROJECT_ID, state_dir)
    (state_dir / "plane-board.json").unlink()
    (state_dir / "plane-board.json.tmp").symlink_to(state_dir / "missing-tmp")
    with pytest.raises(runtime.H5RuntimeError, match="temporary"):
        runtime.write_board_state(settings, PROJECT_ID, state_dir)


def test_board_bootstrap_refuses_native_identity_drift(tmp_path: Path):
    settings = runtime.load_local_env(make_env(tmp_path))
    wrong_source = {"id": PROJECT_ID, "name": runtime.BOARD_NAME, "identifier": runtime.BOARD_IDENTIFIER,
                    "external_source": "other", "external_id": runtime.BOARD_EXTERNAL_ID, "network": runtime.BOARD_NETWORK}
    with pytest.raises(runtime.H5RuntimeError, match="conflicting"):
        runtime.PlaneBoardBootstrap(settings, BoardAPI([wrong_source]), tmp_path / "source-state").ensure()


def test_board_bootstrap_preserves_existing_default_state_colors(tmp_path: Path):
    settings = runtime.load_local_env(make_env(tmp_path))
    project = {"id": PROJECT_ID, "name": runtime.BOARD_NAME, "identifier": runtime.BOARD_IDENTIFIER,
               "external_source": runtime.BOARD_SOURCE, "external_id": runtime.BOARD_EXTERNAL_ID, "network": runtime.BOARD_NETWORK}
    states = [{"id": state_id(number), "name": name, "group": specification["group"], "color": "#000000"}
              for number, (name, specification) in enumerate(runtime.REQUIRED_STATES.items())]
    api = BoardAPI([project], states)
    runtime.PlaneBoardBootstrap(settings, api, tmp_path / "state").ensure()
    assert all(request.get_method() == "GET" for request in api.requests)
    assert all(state["color"] == "#000000" for state in api.states)


def test_discovery_verifies_empty_workspace_using_only_authenticated_projects(tmp_path: Path):
    settings = runtime.load_local_env(make_env(tmp_path, FOREX_PLANE_WORKSPACE="forex"))
    api = BoardAPI()
    report = runtime.PlaneBoardBootstrap(settings, api, tmp_path / "state").discover()
    assert report["workspace"] == "forex" and report["project_count"] == 0
    assert len(api.requests) == 1
    request = api.requests[0]
    assert request.full_url.endswith("/api/v1/workspaces/forex/projects/?per_page=100")
    assert request.get_method() == "GET"
    assert request.get_header("X-api-key") == settings["FOREX_PLANE_API_TOKEN"]
    assert not (tmp_path / "state").exists()


@pytest.mark.parametrize("status", [401, 403, 404, 500])
def test_workspace_discovery_http_failure_prevents_bootstrap_writes(tmp_path: Path, status: int):
    settings = runtime.load_local_env(make_env(tmp_path))
    calls = []
    def deny(request, timeout):
        calls.append(request)
        return Response(b'{"detail":"denied"}', status)
    with pytest.raises(runtime.H5RuntimeError, match="status"):
        runtime.PlaneBoardBootstrap(settings, deny, tmp_path / "state").ensure()
    assert len(calls) == 1 and calls[0].get_method() == "GET"
    assert not (tmp_path / "state").exists()


@pytest.mark.parametrize("payload", [b"[]", b'{"slug":"forex"}', b'{"results":["invalid"]}'])
def test_workspace_discovery_rejects_invalid_collection_without_writes(tmp_path: Path, payload: bytes):
    settings = runtime.load_local_env(make_env(tmp_path))
    with pytest.raises(runtime.H5RuntimeError, match="shape"):
        runtime.PlaneBoardBootstrap(settings, lambda *_args, **_kwargs: Response(payload), tmp_path / "state").ensure()
    assert not (tmp_path / "state").exists()
