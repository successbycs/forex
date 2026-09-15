"""Authenticated local HTTP boundary for the fixed n8n BLS handoff.

All deployment values come from machine-local environment variables. The
service never fetches a URL or accepts a workflow identity from HTTP clients.
"""
from __future__ import annotations

import hmac
import ipaddress
import json
import os
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from forex.bls_n8n_envelope import BLSN8nEnvelopeError, MAX_HANDOFF_JSON_BYTES, build_observation, parse_handoff_json
from forex.bls_n8n_retention import retain, validate_workflow_binding
from forex.event_capture_store import EventCaptureStoreError


HANDOFF_PATH = "/forex/a1/retain-bls"
HEALTH_PATH = "/healthz"


class BLSN8nServiceConfigError(ValueError):
    pass


@dataclass(frozen=True)
class BLSN8nServiceConfig:
    bind_host: str
    port: int
    store: Path
    token: str
    workflow_id: str
    workflow_sha256: str

    @classmethod
    def from_environ(cls, environ: dict[str, str] | None = None) -> "BLSN8nServiceConfig":
        values = os.environ if environ is None else environ
        required = ("FOREX_BLS_N8N_BIND_HOST", "FOREX_BLS_N8N_PORT", "FOREX_BLS_N8N_STORE",
                    "FOREX_BLS_N8N_HANDOFF_TOKEN", "FOREX_BLS_N8N_WORKFLOW_ID", "FOREX_BLS_N8N_WORKFLOW_SHA256")
        if any(not values.get(name) for name in required):
            raise BLSN8nServiceConfigError("BLS n8n service configuration is incomplete")
        host = values["FOREX_BLS_N8N_BIND_HOST"]
        try:
            address = ipaddress.ip_address(host)
        except ValueError as exc:
            raise BLSN8nServiceConfigError("BLS n8n bind host must be an explicit IP address") from exc
        if not address.is_loopback:
            raise BLSN8nServiceConfigError("BLS n8n bind host must be loopback")
        try:
            port = int(values["FOREX_BLS_N8N_PORT"])
        except ValueError as exc:
            raise BLSN8nServiceConfigError("BLS n8n port is invalid") from exc
        if not 1 <= port <= 65535:
            raise BLSN8nServiceConfigError("BLS n8n port is invalid")
        store = Path(values["FOREX_BLS_N8N_STORE"])
        if not store.is_absolute() or any(part in {"", ".", ".."} for part in store.parts):
            raise BLSN8nServiceConfigError("BLS n8n store must be an absolute normal path")
        if store.exists() and store.is_symlink():
            raise BLSN8nServiceConfigError("BLS n8n store must not be a symlink")
        token = values["FOREX_BLS_N8N_HANDOFF_TOKEN"]
        if len(token) < 32:
            raise BLSN8nServiceConfigError("BLS n8n handoff token is too short")
        workflow_id, workflow_sha256 = values["FOREX_BLS_N8N_WORKFLOW_ID"], values["FOREX_BLS_N8N_WORKFLOW_SHA256"]
        try:
            validate_workflow_binding(workflow_id, workflow_sha256)
        except ValueError as exc:
            raise BLSN8nServiceConfigError("BLS n8n workflow binding is invalid") from exc
        return cls(host, port, store, token, workflow_id, workflow_sha256)


def _handler(config: BLSN8nServiceConfig) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "ForexBLSRetention/1"
        sys_version = ""

        def log_message(self, _format: str, *_args: object) -> None:
            # Request contents and bearer tokens must never be logged.
            return

        def _send(self, status: HTTPStatus, value: dict[str, Any]) -> None:
            raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self) -> None:  # noqa: N802
            if self.path != HEALTH_PATH:
                self._send(HTTPStatus.NOT_FOUND, {"status": "NOT_FOUND", "execution_authority": False})
                return
            self._send(HTTPStatus.OK, {"status": "OK", "execution_authority": False})

        def do_POST(self) -> None:  # noqa: N802
            if self.path != HANDOFF_PATH:
                self._send(HTTPStatus.NOT_FOUND, {"status": "NOT_FOUND", "execution_authority": False})
                return
            if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
                self._send(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"status": "REFUSED_CONTENT_TYPE", "execution_authority": False})
                return
            supplied = self.headers.get("Authorization", "")
            expected = "Bearer " + config.token
            if not hmac.compare_digest(supplied, expected):
                self._send(HTTPStatus.UNAUTHORIZED, {"status": "REFUSED_AUTHENTICATION", "execution_authority": False})
                return
            lengths = self.headers.get_all("Content-Length") or []
            if len(lengths) != 1 or self.headers.get_all("Transfer-Encoding"):
                self._send(HTTPStatus.BAD_REQUEST, {"status": "REFUSED_FRAMING", "execution_authority": False})
                return
            length = lengths[0]
            try:
                requested = int(length) if length is not None else -1
            except ValueError:
                requested = -1
            if not 0 < requested <= MAX_HANDOFF_JSON_BYTES:
                self._send(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"status": "REFUSED_SIZE", "execution_authority": False})
                return
            self.connection.settimeout(5)
            try:
                raw = self.rfile.read(requested)
            except OSError:
                self._send(HTTPStatus.REQUEST_TIMEOUT, {"status": "REFUSED_TIMEOUT", "execution_authority": False})
                return
            if len(raw) != requested:
                self._send(HTTPStatus.BAD_REQUEST, {"status": "REFUSED_BODY", "execution_authority": False})
                return
            try:
                handoff = parse_handoff_json(raw)
                capture_id, observation = build_observation(handoff)
                result = retain(config.store, capture_id=capture_id, observation=observation,
                                year=handoff["year"], month=handoff["month"],
                                workflow_id=config.workflow_id, workflow_sha256=config.workflow_sha256)
            except (BLSN8nEnvelopeError, EventCaptureStoreError, ValueError, OSError):
                self._send(HTTPStatus.BAD_REQUEST, {"status": "REFUSED_HANDOFF", "execution_authority": False})
                return
            self._send(HTTPStatus.OK, {"status": "RETAINED", "capture_id": capture_id,
                                       "observation_sha256": result["observation_sha256"],
                                       "n8n_receipt_sha256": result["n8n_receipt_sha256"],
                                       "execution_authority": False})
    return Handler


def create_server(config: BLSN8nServiceConfig) -> ThreadingHTTPServer:
    """Build an unstarted fixed-address server for this machine-local config."""
    server = ThreadingHTTPServer((config.bind_host, config.port), _handler(config))
    server.daemon_threads = True
    return server
