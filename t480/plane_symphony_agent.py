#!/usr/bin/env python3
"""One bounded Codex App Server worker, launched only by the H5 adapter.

The status file intentionally records only lifecycle and IDs: never model text,
tool output, credentials, raw evidence, or a repository diff.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


def worker_environment(home: Path | None = None) -> dict[str, str]:
    """Return the entire fixed worker environment, never inherited secrets."""
    base_home = home or Path.home()
    return {
        "HOME": str(base_home),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": f"{base_home}/.local/bin:/usr/local/bin:/usr/bin:/bin",
    }


def write_status(path: Path, status: str, run_id: str) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps({"status": status, "run_id": run_id}, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(temporary, 0o600); os.replace(temporary, path)


def request(process: subprocess.Popen[str], request_id: int, method: str, params: dict[str, Any]) -> dict[str, Any]:
    assert process.stdin and process.stdout
    process.stdin.write(json.dumps({"id": request_id, "method": method, "params": params}) + "\n"); process.stdin.flush()
    while True:
        line = process.stdout.readline()
        if not line: raise RuntimeError("Codex App Server closed before response")
        message = json.loads(line)
        if message.get("id") == request_id:
            if "error" in message: raise RuntimeError("Codex App Server rejected fixed request")
            return message["result"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worktree", type=Path, required=True); parser.add_argument("--prompt-file", type=Path, required=True)
    parser.add_argument("--status-file", type=Path, required=True); parser.add_argument("--run-id", required=True)
    parser.add_argument("--app-server-socket", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if not args.worktree.is_dir() or args.prompt_file.is_symlink() or not args.prompt_file.is_file(): raise RuntimeError("worker inputs are invalid")
        prompt = args.prompt_file.read_text(encoding="utf-8")
        write_status(args.status_file, "RUNNING", args.run_id)
        if args.app_server_socket.is_symlink() or not args.app_server_socket.is_socket():
            raise RuntimeError("fixed Codex App Server socket is unavailable")
        process = subprocess.Popen(
            ["codex", "app-server", "proxy", "--sock", str(args.app_server_socket)], cwd=args.worktree, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
            env=worker_environment(),
        )
        request(process, 1, "initialize", {"clientInfo": {"name": "forex-h5", "version": "1"}})
        thread = request(process, 2, "thread/start", {"cwd": str(args.worktree), "sandbox": "workspace-write", "approvalPolicy": "never", "developerInstructions": "Follow AGENTS.md. Never trade, use brokers or MT5, commit, push, or close formal proof. Do not execute external operations: the fixed controller owns them after preflight."})
        thread_id = thread["thread"]["id"]
        request(process, 3, "turn/start", {"threadId": thread_id, "input": [{"type": "text", "text": prompt}], "cwd": str(args.worktree), "approvalPolicy": "never"})
        # A completed notification is the only completion surface we retain.
        assert process.stdout
        for line in process.stdout:
            message = json.loads(line)
            if message.get("method") == "turn/completed":
                turn = message.get("params", {}).get("turn", {})
                if turn.get("status") != "completed":
                    raise RuntimeError("Codex turn did not complete successfully")
                write_status(args.status_file, "COMPLETED", args.run_id); return 0
        raise RuntimeError("Codex App Server closed before completion")
    except Exception:
        write_status(args.status_file, "FAILED", args.run_id); return 2


if __name__ == "__main__": raise SystemExit(main())
