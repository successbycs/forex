#!/usr/bin/env python3
"""Collect one fixed first-party central-bank policy calendar response.

The probe is a bounded transport observation only.  It neither parses event
times nor selects events, writes data, or exposes execution authority.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
from enum import Enum
from http.client import IncompleteRead
import socket
import ssl
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener


SCHEMA_VERSION = "forex.first-party-policy-calendar-observation.v1"
TIMEOUT_SECONDS = 20
MAX_BODY_BYTES = 2 * 1024 * 1024
USER_AGENT = "forex-first-party-policy-calendar-observer/1.0"


class PolicyCalendarFamily(str, Enum):
    FOMC_POLICY_DECISION = "FOMC_POLICY_DECISION"
    ECB_POLICY_DECISION = "ECB_POLICY_DECISION"


_OFFICIAL_URLS = {
    PolicyCalendarFamily.FOMC_POLICY_DECISION:
        "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
    PolicyCalendarFamily.ECB_POLICY_DECISION:
        "https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html",
}


class _NoRedirect(HTTPRedirectHandler):
    """Expose redirects as responses instead of issuing a second request."""

    def redirect_request(self, request, fp, code, msg, headers, newurl):  # type: ignore[override]
        return None


def requested_url(family: PolicyCalendarFamily) -> str:
    """Return the single fixed publisher endpoint for a policy family."""
    if not isinstance(family, PolicyCalendarFamily):
        raise ValueError("family must be a PolicyCalendarFamily enum value")
    return _OFFICIAL_URLS[family]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _content_type(response: Any) -> str | None:
    headers = getattr(response, "headers", None)
    value = headers.get("Content-Type") if headers is not None and hasattr(headers, "get") else None
    if not isinstance(value, str) or not value.strip():
        return None
    return value.split(";", 1)[0].strip().lower() or None


def _status(response: Any) -> int | None:
    value = getattr(response, "status", None)
    if value is None and hasattr(response, "getcode"):
        value = response.getcode()
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _transport_error_code(error: BaseException) -> str:
    if isinstance(error, (socket.timeout, TimeoutError)):
        return "TIMEOUT"
    if isinstance(error, ssl.SSLError):
        return "TLS_ERROR"
    if isinstance(error, URLError):
        if isinstance(error.reason, (socket.timeout, TimeoutError)):
            return "TIMEOUT"
        if isinstance(error.reason, ssl.SSLError):
            return "TLS_ERROR"
        return "URL_ERROR"
    return "TRANSPORT_ERROR"


def _envelope(url: str, started: str, completed: str, *, status_code: int | None,
              content_type: str | None, body: bytes, body_complete: bool,
              outcome: str, error_code: str | None) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "requested_url": url,
        "started_at_utc": started,
        "completed_at_utc": completed,
        "status_code": status_code,
        "content_type": content_type,
        "body_base64": base64.b64encode(body).decode("ascii"),
        "body_complete": body_complete,
        "outcome": outcome,
        "error_code": error_code,
        "execution_authority": False,
    }


def _default_open(request: Request, *, timeout: int):
    return build_opener(_NoRedirect()).open(request, timeout=timeout)


def collect_policy_calendar(
    family: PolicyCalendarFamily,
    *,
    opener: Callable[..., Any] | None = None,
    clock: Callable[[], str] | None = None,
) -> dict[str, Any]:
    """Fetch exactly one fixed HTML calendar response without retry or redirect.

    The injectable ``opener`` and ``clock`` exist solely to make transport
    behavior testable without network access.  No caller-controlled URL,
    headers, timeout, redirect behavior, or retry policy is exposed.
    """
    url = requested_url(family)
    now = clock or _utc_now
    started = now()
    request = Request(url, method="GET", headers={"Accept": "text/html", "User-Agent": USER_AGENT})
    open_once = opener or _default_open
    response: Any = None
    try:
        response = open_once(request, timeout=TIMEOUT_SECONDS)
    except HTTPError as error:
        response = error
    except Exception as error:
        return _envelope(url, started, now(), status_code=None, content_type=None,
                         body=b"", body_complete=False, outcome="TRANSPORT_ERROR",
                         error_code=_transport_error_code(error))

    try:
        status_code = _status(response)
        content_type = _content_type(response)
        try:
            bounded = response.read(MAX_BODY_BYTES + 1)
        except IncompleteRead as error:
            return _envelope(url, started, now(), status_code=status_code, content_type=content_type,
                             body=error.partial[:MAX_BODY_BYTES], body_complete=False,
                             outcome="TRANSPORT_ERROR", error_code="INCOMPLETE_BODY")
        if not isinstance(bounded, bytes):
            raise TypeError("response body was not bytes")
        body = bounded[:MAX_BODY_BYTES]
        if len(bounded) > MAX_BODY_BYTES:
            return _envelope(url, started, now(), status_code=status_code, content_type=content_type,
                             body=body, body_complete=False, outcome="BODY_TOO_LARGE",
                             error_code="BODY_TOO_LARGE")
        declared = response.headers.get("Content-Length") if getattr(response, "headers", None) is not None else None
        if declared is not None and (not isinstance(declared, str) or not declared.isdigit() or int(declared) != len(body)):
            return _envelope(url, started, now(), status_code=status_code, content_type=content_type,
                             body=body, body_complete=False, outcome="TRANSPORT_ERROR",
                             error_code="INCOMPLETE_BODY")
        if status_code != 200:
            return _envelope(url, started, now(), status_code=status_code, content_type=content_type,
                             body=body, body_complete=True, outcome="HTTP_ERROR", error_code="HTTP_STATUS")
        if content_type != "text/html":
            return _envelope(url, started, now(), status_code=status_code, content_type=content_type,
                             body=body, body_complete=True, outcome="UNSUPPORTED_CONTENT_TYPE",
                             error_code="UNSUPPORTED_CONTENT_TYPE")
        if not body:
            return _envelope(url, started, now(), status_code=status_code, content_type=content_type,
                             body=body, body_complete=True, outcome="TRANSPORT_ERROR", error_code="EMPTY_BODY")
        return _envelope(url, started, now(), status_code=status_code, content_type=content_type,
                         body=body, body_complete=True, outcome="SUCCESS", error_code=None)
    except Exception as error:
        return _envelope(url, started, now(), status_code=None, content_type=None,
                         body=b"", body_complete=False, outcome="TRANSPORT_ERROR",
                         error_code=_transport_error_code(error))
    finally:
        if response is not None and hasattr(response, "close"):
            try:
                response.close()
            except Exception:
                pass
