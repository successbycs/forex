"""Loopback-only, bounded publisher fetcher used by the GDELT n8n flow.

This module deliberately accepts a small description of a GDELT candidate, not
an arbitrary URL command.  It resolves and validates a hostname for every hop,
then connects to the selected address directly while retaining TLS hostname
verification.  That prevents a later DNS answer changing the destination
between validation and connect.
"""
from __future__ import annotations

import base64
import hmac
import hashlib
import http.client
import ipaddress
import json
import re
import socket
import ssl
import time
import threading
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable
from urllib.parse import urljoin, urlsplit, urlunsplit

FETCH_PATH = "/forex/gdelt/fetch"
ARCHIVE_PATH = "/forex/gdelt/archive"
HEALTH_PATH = "/healthz"
MAX_REQUEST_BYTES = 32_768
MAX_RESPONSE_BYTES = 1_048_576
MAX_ARCHIVE_BYTES = 64 * 1_048_576
MAX_REDIRECTS = 3
TIMEOUT_SECONDS = 10
USER_AGENT = "ForexGDELTResearch/1.0"
MAX_CONCURRENT_FETCHES = 2
_FETCH_SLOTS = threading.BoundedSemaphore(MAX_CONCURRENT_FETCHES)


class GDELTFetchError(ValueError):
    """A request that cannot cross the publisher boundary."""


@dataclass(frozen=True)
class GDELTEgressConfig:
    bind_host: str = "127.0.0.1"
    port: int = 8092
    bearer_token: str = ""
    candidate_signing_key: str = ""
    container_private: bool = False

    def __post_init__(self) -> None:
        try:
            if not ipaddress.ip_address(self.bind_host).is_loopback and not (self.container_private and self.bind_host == "0.0.0.0"):
                raise GDELTFetchError("bind host must be loopback")
        except ValueError as exc:
            raise GDELTFetchError("bind host must be an IP address") from exc
        if not 1 <= self.port <= 65535:
            raise GDELTFetchError("port is invalid")
        if len(self.bearer_token) < 32:
            raise GDELTFetchError("egress bearer token is too short")
        if len(self.candidate_signing_key) < 32:
            raise GDELTFetchError("candidate signing key is too short")


def _canonical_url(value: object) -> str:
    if not isinstance(value, str) or not value or len(value) > 2048:
        raise GDELTFetchError("REFUSED_URL")
    parsed = urlsplit(value)
    if parsed.scheme.lower() != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise GDELTFetchError("REFUSED_URL")
    try:
        port = parsed.port
    except ValueError as exc:
        raise GDELTFetchError("REFUSED_URL") from exc
    if port not in (None, 443):
        raise GDELTFetchError("REFUSED_URL")
    host = parsed.hostname.rstrip(".").lower()
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise GDELTFetchError("REFUSED_IP_LITERAL")
    if host == "localhost" or host.endswith(".localhost") or any(word in host for word in ("gomarkets", "metatrader", "mt5", "broker")):
        raise GDELTFetchError("REFUSED_HOST")
    return urlunsplit(("https", host, parsed.path or "/", parsed.query, ""))


def _archive_url(raw: bytes) -> str:
    """Accept only one canonical public GDELT v2 GKG archive URL.

    n8n constructs these four URLs deterministically.  Keeping archive bytes
    behind this endpoint lets n8n remain on an internal-only Docker network;
    this is not a general-purpose download proxy.
    """
    if not 0 < len(raw) <= MAX_REQUEST_BYTES:
        raise GDELTFetchError("REFUSED_SIZE")
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GDELTFetchError("REFUSED_JSON") from exc
    if not isinstance(value, dict) or set(value) != {"url"}:
        raise GDELTFetchError("REFUSED_ARCHIVE")
    url = _canonical_url(value["url"])
    parsed = urlsplit(url)
    if parsed.hostname != "data.gdeltproject.org" or parsed.query or not re.fullmatch(
        r"/gdeltv2/[0-9]{14}\.gkg\.csv\.zip", parsed.path
    ):
        raise GDELTFetchError("REFUSED_ARCHIVE")
    return url


def _canonical_json(value: object) -> bytes:
    """Encode the exact HMAC input identically on n8n and Python."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def sign_candidate_envelope(*, candidate: dict[str, object], aggregate_sha256: str,
                            bucket_time_utc: str, signing_key: str) -> str:
    """Return the signature used by the scheduler for one immutable candidate."""
    material = {
        "aggregate_sha256": aggregate_sha256,
        "bucket_time_utc": bucket_time_utc,
        "candidate": candidate,
    }
    return hmac.new(signing_key.encode("utf-8"), _canonical_json(material), hashlib.sha256).hexdigest()


def _candidate(raw: bytes, *, candidate_signing_key: str) -> tuple[str, list[dict[str, object]]]:
    if not 0 < len(raw) <= MAX_REQUEST_BYTES:
        raise GDELTFetchError("REFUSED_SIZE")
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GDELTFetchError("REFUSED_JSON") from exc
    if not isinstance(value, dict) or set(value) != {"candidate", "aggregate_sha256", "bucket_time_utc", "signature"}:
        raise GDELTFetchError("REFUSED_CANDIDATE")
    candidate = value["candidate"]
    if not isinstance(candidate, dict) or set(candidate) != {"canonical_url", "sources"}:
        raise GDELTFetchError("REFUSED_CANDIDATE")
    aggregate_sha256 = value["aggregate_sha256"]
    bucket_time_utc = value["bucket_time_utc"]
    signature = value["signature"]
    if (not isinstance(aggregate_sha256, str) or not _sha256(aggregate_sha256)
            or not isinstance(bucket_time_utc, str) or not bucket_time_utc.endswith("Z")
            or not isinstance(signature, str) or len(signature) != 64):
        raise GDELTFetchError("REFUSED_CANDIDATE")
    expected = sign_candidate_envelope(candidate=candidate, aggregate_sha256=aggregate_sha256,
                                       bucket_time_utc=bucket_time_utc,
                                       signing_key=candidate_signing_key)
    if not hmac.compare_digest(signature, expected):
        raise GDELTFetchError("REFUSED_SIGNATURE")
    url = _canonical_url(candidate["canonical_url"])
    sources = candidate["sources"]
    if not isinstance(sources, list) or not sources or len(sources) > 64:
        raise GDELTFetchError("REFUSED_CANDIDATE")
    for source in sources:
        if not isinstance(source, dict) or set(source) != {"source_observation_id", "gdelt_document_id", "bucket_time_utc", "source_tone"}:
            raise GDELTFetchError("REFUSED_CANDIDATE")
        if not all(isinstance(source.get(key), str) and source[key] for key in ("source_observation_id", "gdelt_document_id", "bucket_time_utc")):
            raise GDELTFetchError("REFUSED_CANDIDATE")
        if source["source_tone"] is not None and not isinstance(source["source_tone"], (int, float)):
            raise GDELTFetchError("REFUSED_CANDIDATE")
    return url, sources


def _sha256(value: str) -> bool:
    return bool(re.fullmatch(r"sha256:[0-9a-f]{64}", value))


def _resolve_public(host: str, resolver: Callable[..., Any] = socket.getaddrinfo) -> str:
    try:
        answers = resolver(host, 443, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise GDELTFetchError("DNS_FAILED") from exc
    ips: list[str] = []
    for answer in answers:
        address = answer[4][0]
        try:
            parsed = ipaddress.ip_address(address)
        except ValueError:
            raise GDELTFetchError("DNS_INVALID")
        if not (parsed.is_global and not parsed.is_multicast and not parsed.is_reserved and not parsed.is_unspecified and not parsed.is_private and not parsed.is_loopback and not parsed.is_link_local):
            raise GDELTFetchError("REFUSED_NON_GLOBAL_DESTINATION")
        if address not in ips:
            ips.append(address)
    if not ips:
        raise GDELTFetchError("DNS_EMPTY")
    return ips[0]


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """HTTPS transport whose TCP peer is the validated resolver answer."""

    def __init__(self, host: str, pinned_ip: str, timeout: float):
        super().__init__(host, port=443, timeout=timeout, context=ssl.create_default_context())
        self._pinned_ip = pinned_ip

    def connect(self) -> None:
        sock = socket.create_connection((self._pinned_ip, 443), self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


def fetch_candidate(raw: bytes, *, candidate_signing_key: str,
                    resolver: Callable[..., Any] = socket.getaddrinfo,
                    connection_factory: Callable[[str, str, float], http.client.HTTPSConnection] = _PinnedHTTPSConnection,
                    monotonic: Callable[[], float] = time.monotonic) -> dict[str, object]:
    """Fetch one validated public document, returning bytes only on safe success."""
    try:
        url, _sources = _candidate(raw, candidate_signing_key=candidate_signing_key)
    except GDELTFetchError as exc:
        return {"status": "FAILED", "reason": str(exc), "http_status": None}
    if not _FETCH_SLOTS.acquire(blocking=False):
        return {"status": "FAILED", "reason": "FETCH_CAPACITY_REJECTED", "http_status": None}
    started = monotonic()
    current = url
    chain: list[str] = []
    try:
     for redirect_count in range(MAX_REDIRECTS + 1):
        remaining = TIMEOUT_SECONDS - (monotonic() - started)
        if remaining <= 0:
            return {"status": "FAILED", "reason": "TIMEOUT", "http_status": None}
        parsed = urlsplit(current); chain.append(current)
        try:
            pinned_ip = _resolve_public(parsed.hostname or "", resolver)
            connection = connection_factory(parsed.hostname or "", pinned_ip, remaining)
            target = urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
            connection.request("GET", target, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"})
            response = connection.getresponse()
            status = response.status
            headers = {key.lower(): value for key, value in response.getheaders()}
            if 300 <= status < 400:
                response.read(0); connection.close()
                return {"status": "FAILED", "reason": "REDIRECT_REFUSED", "http_status": status}
            if status != 200:
                response.read(0); connection.close()
                return {"status": "FAILED", "reason": "HTTP_STATUS_REJECTED", "http_status": status}
            content_type = headers.get("content-type", "").split(";", 1)[0].strip().lower()
            if content_type not in {"text/html", "application/xhtml+xml"}:
                response.read(0); connection.close()
                return {"status": "FAILED", "reason": "CONTENT_TYPE_REJECTED", "http_status": status}
            content_length = headers.get("content-length")
            if content_length and (not content_length.isdigit() or int(content_length) > MAX_RESPONSE_BYTES):
                response.read(0); connection.close()
                return {"status": "FAILED", "reason": "RESPONSE_TOO_LARGE", "http_status": status}
            chunks=[]; total=0
            while True:
                remaining = TIMEOUT_SECONDS - (monotonic() - started)
                if remaining <= 0:
                    connection.close(); return {"status":"FAILED","reason":"TIMEOUT","http_status":status}
                if getattr(connection, "sock", None) is not None: connection.sock.settimeout(remaining)
                part=response.read(min(65_536, MAX_RESPONSE_BYTES + 1 - total))
                if not part: break
                chunks.append(part); total += len(part)
                if total > MAX_RESPONSE_BYTES:
                    connection.close(); return {"status":"FAILED","reason":"RESPONSE_TOO_LARGE","http_status":status}
            body=b''.join(chunks); connection.close()
            if len(body) > MAX_RESPONSE_BYTES:
                return {"status": "FAILED", "reason": "RESPONSE_TOO_LARGE", "http_status": status}
            if monotonic() - started > TIMEOUT_SECONDS:
                return {"status": "FAILED", "reason": "TIMEOUT", "http_status": status}
            return {"status": "RETAINED", "reason": None, "http_status": status, "content_type": content_type,
                    "canonical_url": current, "redirect_chain": chain, "pinned_ip": pinned_ip, "byte_count": len(body),
                    "payload_sha256": "sha256:"+hashlib.sha256(body).hexdigest(), "content_base64": base64.b64encode(body).decode("ascii")}
        except GDELTFetchError as exc:
            return {"status": "FAILED", "reason": str(exc), "http_status": None}
        except (OSError, http.client.HTTPException, ssl.SSLError):
            return {"status": "FAILED", "reason": "FETCH_FAILED", "http_status": None}
     return {"status": "FAILED", "reason": "REDIRECT_REFUSED", "http_status": None}
    finally:
     _FETCH_SLOTS.release()


def fetch_archive(raw: bytes, *, resolver: Callable[..., Any] = socket.getaddrinfo,
                  connection_factory: Callable[[str, str, float], http.client.HTTPSConnection] = _PinnedHTTPSConnection,
                  monotonic: Callable[[], float] = time.monotonic) -> tuple[dict[str, object], bytes | None]:
    """Retrieve one fixed GDELT archive; never return partial or oversized bytes."""
    try:
        url = _archive_url(raw)
    except GDELTFetchError as exc:
        return {"status": "FAILED", "reason": str(exc), "http_status": None}, None
    if not _FETCH_SLOTS.acquire(blocking=False):
        return {"status": "FAILED", "reason": "FETCH_CAPACITY_REJECTED", "http_status": None}, None
    started = monotonic()
    try:
        parsed = urlsplit(url)
        remaining = TIMEOUT_SECONDS - (monotonic() - started)
        if remaining <= 0:
            return {"status": "FAILED", "reason": "TIMEOUT", "http_status": None}, None
        try:
            pinned_ip = _resolve_public(parsed.hostname or "", resolver)
            connection = connection_factory(parsed.hostname or "", pinned_ip, remaining)
            connection.request("GET", parsed.path, headers={"User-Agent": USER_AGENT, "Accept": "application/zip"})
            response = connection.getresponse()
            status = response.status
            headers = {key.lower(): value for key, value in response.getheaders()}
            if status != 200:
                response.read(0); connection.close()
                return {"status": "FAILED", "reason": "HTTP_STATUS_REJECTED", "http_status": status}, None
            content_length = headers.get("content-length")
            if content_length and (not content_length.isdigit() or int(content_length) > MAX_ARCHIVE_BYTES):
                response.read(0); connection.close()
                return {"status": "FAILED", "reason": "RESPONSE_TOO_LARGE", "http_status": status}, None
            chunks: list[bytes] = []; total = 0
            while True:
                remaining = TIMEOUT_SECONDS - (monotonic() - started)
                if remaining <= 0:
                    connection.close(); return {"status": "FAILED", "reason": "TIMEOUT", "http_status": status}, None
                if getattr(connection, "sock", None) is not None:
                    connection.sock.settimeout(remaining)
                part = response.read(min(65_536, MAX_ARCHIVE_BYTES + 1 - total))
                if not part:
                    break
                chunks.append(part); total += len(part)
                if total > MAX_ARCHIVE_BYTES:
                    connection.close(); return {"status": "FAILED", "reason": "RESPONSE_TOO_LARGE", "http_status": status}, None
            connection.close()
            data = b"".join(chunks)
            return {"status": "OK", "canonical_url": url, "pinned_ip": pinned_ip,
                    "byte_count": len(data), "payload_sha256": "sha256:" + hashlib.sha256(data).hexdigest()}, data
        except (OSError, http.client.HTTPException, ssl.SSLError):
            return {"status": "FAILED", "reason": "FETCH_FAILED", "http_status": None}, None
    finally:
        _FETCH_SLOTS.release()


def _handler(bearer_token: str, candidate_signing_key: str) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "ForexGDELTEgress/1"
        sys_version = ""
        def log_message(self, _format: str, *_args: object) -> None: return
        def _send(self, status: HTTPStatus, value: dict[str, object]) -> None:
            raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
            self.send_response(status); self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw))); self.send_header("Cache-Control", "no-store")
            self.end_headers(); self.wfile.write(raw)
        def _send_bytes(self, status: HTTPStatus, value: bytes) -> None:
            self.send_response(status); self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Length", str(len(value))); self.send_header("Cache-Control", "no-store")
            self.end_headers(); self.wfile.write(value)
        def do_GET(self) -> None:  # noqa: N802
            self._send(HTTPStatus.OK if self.path == HEALTH_PATH else HTTPStatus.NOT_FOUND,
                       {"status": "OK" if self.path == HEALTH_PATH else "NOT_FOUND", "execution_authority": False})
        def do_POST(self) -> None:  # noqa: N802
            if self.path not in {FETCH_PATH, ARCHIVE_PATH}:
                self._send(HTTPStatus.NOT_FOUND, {"status": "NOT_FOUND", "execution_authority": False}); return
            if self.headers.get("Content-Type", "").split(";", 1)[0].lower() != "application/json":
                self._send(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"status": "REFUSED_CONTENT_TYPE"}); return
            if not hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + bearer_token):
                self._send(HTTPStatus.UNAUTHORIZED, {"status": "REFUSED_AUTHENTICATION"}); return
            try: length = int(self.headers.get("Content-Length", "-1"))
            except ValueError: length = -1
            if not 0 < length <= MAX_REQUEST_BYTES or self.headers.get("Transfer-Encoding"):
                self._send(HTTPStatus.BAD_REQUEST, {"status": "REFUSED_FRAMING"}); return
            self.connection.settimeout(TIMEOUT_SECONDS)
            try: raw = self.rfile.read(length)
            except OSError: raw = b""
            if len(raw) != length:
                self._send(HTTPStatus.BAD_REQUEST, {"status": "REFUSED_BODY"}); return
            if self.path == ARCHIVE_PATH:
                result, archive = fetch_archive(raw)
                if archive is None:
                    self._send(HTTPStatus.BAD_REQUEST, result)
                else:
                    self._send_bytes(HTTPStatus.OK, archive)
                return
            self._send(HTTPStatus.OK, fetch_candidate(raw, candidate_signing_key=candidate_signing_key))
    return Handler


def create_server(config: GDELTEgressConfig) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((config.bind_host, config.port), _handler(config.bearer_token, config.candidate_signing_key))
    server.daemon_threads = True
    return server
