from __future__ import annotations

import base64
from http.client import IncompleteRead
import socket
from urllib.error import HTTPError

import pytest

from t480 import first_party_policy_calendar_probe as probe


class Response:
    def __init__(self, *, status=200, content_type="text/html; charset=utf-8", body=b"", content_length=None):
        self.status = status
        self.headers = {"Content-Type": content_type} if content_type is not None else {}
        if content_length is not None:
            self.headers["Content-Length"] = content_length
        self.body = body
        self.read_sizes: list[int] = []
        self.closed = False

    def read(self, size):
        self.read_sizes.append(size)
        return self.body[:size]

    def close(self):
        self.closed = True


def clock():
    values = iter(["2026-09-13T00:00:00.000Z", "2026-09-13T00:00:01.000Z"])
    return lambda: next(values)


@pytest.mark.parametrize(
    ("family", "url"),
    [
        (probe.PolicyCalendarFamily.FOMC_POLICY_DECISION, "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"),
        (probe.PolicyCalendarFamily.ECB_POLICY_DECISION, "https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html"),
    ],
)
def test_each_family_uses_its_exact_fixed_official_endpoint(family, url):
    response = Response(body=b"<html>calendar</html>")
    seen = {}

    def opener(request, *, timeout):
        seen.update(url=request.full_url, method=request.get_method(), accept=request.get_header("Accept"), timeout=timeout)
        return response

    result = probe.collect_policy_calendar(family, opener=opener, clock=clock())
    assert seen == {"url": url, "method": "GET", "accept": "text/html", "timeout": 20}
    assert result["requested_url"] == url
    assert result["execution_authority"] is False
    assert result["outcome"] == "SUCCESS"
    assert response.read_sizes == [probe.MAX_BODY_BYTES + 1]
    assert response.closed


def test_only_enum_families_are_accepted_and_no_generic_url_surface_exists():
    with pytest.raises(ValueError, match="PolicyCalendarFamily"):
        probe.collect_policy_calendar("https://example.invalid")  # type: ignore[arg-type]
    assert probe.requested_url(probe.PolicyCalendarFamily.FOMC_POLICY_DECISION).startswith("https://www.federalreserve.gov/")
    assert probe.requested_url(probe.PolicyCalendarFamily.ECB_POLICY_DECISION).startswith("https://www.ecb.europa.eu/")


def test_redirect_response_is_an_error_not_a_followed_success():
    response = Response(status=302, body=b"redirect")
    result = probe.collect_policy_calendar(probe.PolicyCalendarFamily.FOMC_POLICY_DECISION,
                                           opener=lambda request, *, timeout: response, clock=clock())
    assert probe._NoRedirect().redirect_request(None, None, 302, "", None, "https://other.invalid") is None
    assert result["outcome"] == "HTTP_ERROR"
    assert result["status_code"] == 302
    assert result["error_code"] == "HTTP_STATUS"


def test_http_non_html_and_oversize_fail_closed_with_retained_bounded_bytes():
    denied = Response(status=403, body=b"denied")

    def denied_open(request, *, timeout):
        raise HTTPError(request.full_url, 403, "forbidden", denied.headers, denied)

    http_result = probe.collect_policy_calendar(probe.PolicyCalendarFamily.ECB_POLICY_DECISION,
                                                opener=denied_open, clock=clock())
    assert http_result["outcome"] == "HTTP_ERROR"
    assert base64.b64decode(http_result["body_base64"]) == b"denied"
    not_html = probe.collect_policy_calendar(probe.PolicyCalendarFamily.FOMC_POLICY_DECISION,
                                             opener=lambda request, *, timeout: Response(content_type="application/json", body=b"{}"),
                                             clock=clock())
    assert (not_html["outcome"], not_html["body_complete"]) == ("UNSUPPORTED_CONTENT_TYPE", True)
    huge = probe.collect_policy_calendar(probe.PolicyCalendarFamily.FOMC_POLICY_DECISION,
                                         opener=lambda request, *, timeout: Response(body=b"x" * (probe.MAX_BODY_BYTES + 1)),
                                         clock=clock())
    assert (huge["outcome"], huge["body_complete"]) == ("BODY_TOO_LARGE", False)
    assert len(base64.b64decode(huge["body_base64"])) == probe.MAX_BODY_BYTES


def test_timeout_and_incomplete_body_fail_closed_without_claiming_complete_capture():
    timeout = probe.collect_policy_calendar(
        probe.PolicyCalendarFamily.FOMC_POLICY_DECISION,
        opener=lambda request, *, timeout: (_ for _ in ()).throw(socket.timeout("private host")),
        clock=clock(),
    )
    assert timeout["outcome"] == "TRANSPORT_ERROR"
    assert timeout["error_code"] == "TIMEOUT"
    assert timeout["body_complete"] is False

    class IncompleteResponse(Response):
        def read(self, size):
            raise IncompleteRead(b"partial", 10)

    incomplete = probe.collect_policy_calendar(
        probe.PolicyCalendarFamily.ECB_POLICY_DECISION,
        opener=lambda request, *, timeout: IncompleteResponse(),
        clock=clock(),
    )
    assert incomplete["outcome"] == "TRANSPORT_ERROR"
    assert incomplete["error_code"] == "INCOMPLETE_BODY"
    assert incomplete["body_complete"] is False
    assert base64.b64decode(incomplete["body_base64"]) == b"partial"
