import base64
import socket
from urllib.error import HTTPError

import pytest

from t480 import bls_monthly_probe as probe


class Response:
    def __init__(self, *, status=200, content_type="text/html; charset=utf-8", body=b""):
        self.status = status
        self.headers = {"Content-Type": content_type} if content_type is not None else {}
        self.body = body
        self.read_sizes = []
        self.closed = False

    def read(self, size):
        self.read_sizes.append(size)
        return self.body[:size]

    def close(self):
        self.closed = True


def clock():
    values = iter(["2026-09-12T00:00:00.000Z", "2026-09-12T00:00:01.000Z"])
    return lambda: next(values)


def test_real_http_response_with_premature_eof_is_not_success():
    from http.client import HTTPResponse
    from io import BytesIO
    class Socket:
        def makefile(self, mode):
            return BytesIO(b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: 5000\r\n\r\n<html>broken</html>")
    response = HTTPResponse(Socket())
    response.begin()
    result = probe.collect_month(2026, 9, opener=lambda *a, **kw: response, clock=clock())
    assert result["outcome"] == "TRANSPORT_ERROR"
    assert result["error_code"] == "INCOMPLETE_BODY"
    assert result["body_complete"] is False
    assert base64.b64decode(result["body_base64"]) == b"<html>broken</html>"


def test_year_range_matches_monthly_parser():
    with pytest.raises(ValueError):
        probe.collect_month(2100, 1)


def test_success_uses_exact_url_headers_timeout_and_bounded_body():
    response = Response(body=b"<html>calendar</html>")
    seen = {}

    def opener(request, *, timeout):
        seen["url"] = request.full_url
        seen["method"] = request.get_method()
        seen["accept"] = request.get_header("Accept")
        seen["agent"] = request.get_header("User-agent")
        seen["timeout"] = timeout
        return response

    result = probe.collect_month(2026, 9, opener=opener, clock=clock())
    assert seen == {"url": "https://www.bls.gov/schedule/2026/09_sched_list.htm", "method": "GET",
                    "accept": "text/html", "agent": probe.USER_AGENT, "timeout": 20}
    assert response.read_sizes == [probe.MAX_BODY_BYTES + 1]
    assert response.closed
    assert result == {"schema_version": "forex.bls-http-observation.v1",
                      "requested_url": seen["url"], "started_at_utc": "2026-09-12T00:00:00.000Z",
                      "completed_at_utc": "2026-09-12T00:00:01.000Z", "status_code": 200,
                      "content_type": "text/html", "body_base64": base64.b64encode(response.body).decode(),
                      "body_complete": True, "outcome": "SUCCESS", "error_code": None,
                      "execution_authority": False}


def test_http_error_retains_bounded_observed_body_without_parsing():
    response = Response(status=403, body=b"denied")

    def opener(request, *, timeout):
        raise HTTPError(request.full_url, 403, "forbidden", response.headers, response)

    result = probe.collect_month(2026, 9, opener=opener, clock=clock())
    assert result["outcome"] == "HTTP_ERROR"
    assert result["error_code"] == "HTTP_STATUS"
    assert result["status_code"] == 403
    assert base64.b64decode(result["body_base64"]) == b"denied"
    assert result["body_complete"] is True
    assert response.closed


def test_redirect_is_an_http_error_and_not_a_followed_success():
    response = Response(status=302, content_type="text/html", body=b"redirect")
    result = probe.collect_month(2026, 9, opener=lambda request, *, timeout: response, clock=clock())
    assert result["outcome"] == "HTTP_ERROR"
    assert result["status_code"] == 302
    assert result["error_code"] == "HTTP_STATUS"


def test_oversize_body_is_truncated_and_explicitly_incomplete():
    body = b"x" * (probe.MAX_BODY_BYTES + 17)
    response = Response(body=body)
    result = probe.collect_month(2026, 9, opener=lambda request, *, timeout: response, clock=clock())
    assert result["outcome"] == "BODY_TOO_LARGE"
    assert result["error_code"] == "BODY_TOO_LARGE"
    assert result["body_complete"] is False
    assert len(base64.b64decode(result["body_base64"])) == probe.MAX_BODY_BYTES


@pytest.mark.parametrize("content_type", [None, "application/json", "text/plain; charset=utf-8"])
def test_200_non_html_is_retained_but_not_a_parser_input(content_type):
    response = Response(content_type=content_type, body=b"not-html")
    result = probe.collect_month(2026, 9, opener=lambda request, *, timeout: response, clock=clock())
    assert result["outcome"] == "UNSUPPORTED_CONTENT_TYPE"
    assert result["error_code"] == "UNSUPPORTED_CONTENT_TYPE"
    assert base64.b64decode(result["body_base64"]) == b"not-html"


def test_transport_failure_emits_sanitized_failure_without_body():
    result = probe.collect_month(2026, 9,
                                 opener=lambda request, *, timeout: (_ for _ in ()).throw(socket.timeout("secret host")),
                                 clock=clock())
    assert result["outcome"] == "TRANSPORT_ERROR"
    assert result["error_code"] == "TIMEOUT"
    assert result["status_code"] is None
    assert result["content_type"] is None
    assert result["body_base64"] == ""
    assert result["body_complete"] is False
    assert "secret" not in str(result)


@pytest.mark.parametrize("year,month", [(1999, 1), (2101, 1), (2026, 0), (2026, 13), (True, 1), (2026, True)])
def test_requested_url_rejects_out_of_bounds_or_boolean_scalars(year, month):
    with pytest.raises(ValueError):
        probe.requested_url(year, month)
