#!/usr/bin/env python3
"""Fetch one fixed BLS monthly release-calendar observation.

This is deliberately a small transport payload, not a parser, scheduler, or
trading interface.  It performs exactly one GET for a caller-selected bounded
calendar month and returns an evidence-shaped JSON observation.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import json
from http.client import IncompleteRead
import socket
import ssl
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener


SCHEMA_VERSION = "forex.bls-http-observation.v1"
MIN_YEAR = 2000
MAX_YEAR = 2099
TIMEOUT_SECONDS = 20
MAX_BODY_BYTES = 2 * 1024 * 1024
USER_AGENT = "forex-bls-monthly-observer/1.0"


class _NoRedirect(HTTPRedirectHandler):
    """Return the redirect response to urllib instead of issuing a new GET."""

    def redirect_request(self, request, fp, code, msg, headers, newurl):  # type: ignore[override]
        return None


def requested_url(year: int, month: int) -> str:
    """Return the sole permitted BLS URL after strict scalar validation."""
    if isinstance(year, bool) or not isinstance(year, int) or not MIN_YEAR <= year <= MAX_YEAR:
        raise ValueError(f"year must be an integer in {MIN_YEAR}..{MAX_YEAR}")
    if isinstance(month, bool) or not isinstance(month, int) or not 1 <= month <= 12:
        raise ValueError("month must be an integer in 1..12")
    return f"https://www.bls.gov/schedule/{year:04d}/{month:02d}_sched_list.htm"


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
        reason = error.reason
        if isinstance(reason, (socket.timeout, TimeoutError)):
            return "TIMEOUT"
        if isinstance(reason, ssl.SSLError):
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


def collect_month(year: int, month: int, *, opener: Callable[..., Any] | None = None,
                  clock: Callable[[], str] | None = None) -> dict[str, Any]:
    """Collect one bounded calendar response without redirects or retries.

    ``opener`` is injectable solely for offline tests.  It receives the fixed
    request and the fixed 20-second timeout.  Returned bytes are never parsed.
    """
    url = requested_url(year, month)
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
        overflow = len(bounded) > MAX_BODY_BYTES
        body = bounded[:MAX_BODY_BYTES]
        if overflow:
            return _envelope(url, started, now(), status_code=status_code, content_type=content_type,
                             body=body, body_complete=False, outcome="BODY_TOO_LARGE",
                             error_code="BODY_TOO_LARGE")
        declared = response.headers.get("Content-Length") if getattr(response, "headers", None) is not None else None
        if declared is not None and (not isinstance(declared, str) or not declared.isdigit() or int(declared) != len(body)):
            return _envelope(url, started, now(), status_code=status_code, content_type=content_type,
                             body=body, body_complete=False, outcome="TRANSPORT_ERROR", error_code="INCOMPLETE_BODY")
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
                # The response outcome has already been captured.  A close
                # failure is not safe to expose as an implementation detail.
                pass


def _bounded_year(value: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("year must be an integer") from exc


def _bounded_month(value: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("month must be an integer") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=_bounded_year, required=True)
    parser.add_argument("--month", type=_bounded_month, required=True)
    args = parser.parse_args(argv)
    try:
        result = collect_month(args.year, args.month)
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
