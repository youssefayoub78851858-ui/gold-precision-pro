"""Strict Capital.com DEMO-ONLY price GET transport, dormant until called.

This module does not establish a session or accept an API key. Capital session
tokens can authorize trades; strict external egress restrictions are ALSO
needed before real credentials are provisioned. No HTTP at import.
"""
import datetime as dt
import json
import os
import re
import ssl
from urllib.parse import urlsplit, parse_qsl
from urllib.request import (
    Request, build_opener, HTTPSHandler, HTTPRedirectHandler, ProxyHandler,
)
from capital_demo_offline_adapter import DEMO_BASE_URL, RESOLUTIONS, _valid_epic
from capital_demo_private_get_boundary import ENABLE_ENV, RIGHTS_ENV, ENABLE_VALUE

MAX_BYTES = 1048576


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise ValueError("DEMO_REDIRECT_BLOCKED")


def _validate(method, url, headers):
    if method != "GET" or not isinstance(url, str):
        raise ValueError("DEMO_GET_ONLY")
    u, base = urlsplit(url), urlsplit(DEMO_BASE_URL)
    if (u.scheme != "https" or u.netloc != base.netloc or u.fragment
            or u.username is not None or u.password is not None
            or not u.path.startswith("/api/v1/prices/")
            or not _valid_epic(u.path.removeprefix("/api/v1/prices/"))):
        raise ValueError("DEMO_PRICE_HOST_AND_ROUTE_REQUIRED")
    q = parse_qsl(u.query, keep_blank_values=True, strict_parsing=True)
    if [key for key, _ in q] != ["resolution", "from", "to", "max"]:
        raise ValueError("DEMO_BOUNDED_QUERY_ONLY")
    params = dict(q)
    if (params["resolution"] not in {r for r, _ in RESOLUTIONS.values()}
            or params["max"] != "1000"):
        raise ValueError("DEMO_RESOLUTION_OR_LIMIT_INVALID")
    clocks = []
    for key in ("from", "to"):
        value = params[key]
        if not re.fullmatch(r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d", value):
            raise ValueError("DEMO_UTC_BOUND_INVALID")
        try:
            clocks.append(dt.datetime.strptime(value, "%Y-%m-%dT%H:%M:%S"))
        except ValueError:
            raise ValueError("DEMO_UTC_BOUND_INVALID") from None
    width = next(seconds for resolution, seconds in RESOLUTIONS.values()
                 if resolution == params["resolution"])
    if not (clocks[0] < clocks[1]
            and (clocks[1] - clocks[0]).total_seconds() <= 900 * width):
        raise ValueError("DEMO_BOUNDED_TIME_WINDOW_REQUIRED")
    if not isinstance(headers, dict) or set(headers) != {"CST", "X-SECURITY-TOKEN"}:
        raise ValueError("DEMO_SESSION_HEADERS_ONLY")
    if any(not isinstance(v, str) or re.fullmatch(
            r"[A-Za-z0-9+/_=.:-]{24,512}", v) is None for v in headers.values()):
        raise ValueError("DEMO_SESSION_TOKEN_FORMAT_INVALID")


def demo_https_price_get(method, url, headers, *, opener=None,
                         explicit_operator_approval=False):
    """One no-redirect Demo GET; opener injection is used for offline tests.

    Do not call directly except through a separately approved, private,
    egress-filtered reader. Returns raw JSON only to that private reader.
    """
    # A caller must not bypass the private gateway by calling the raw
    # transport. These latches are not independent rights attestation.
    if (os.environ.get(ENABLE_ENV) != ENABLE_VALUE
            or os.environ.get(RIGHTS_ENV) != ENABLE_VALUE
            or explicit_operator_approval is not True):
        raise ValueError("PRIVATE_DEMO_TRANSPORT_NOT_APPROVED")
    _validate(method, url, headers)
    request = Request(url, headers=headers, method="GET")
    client = opener if opener is not None else build_opener(
        ProxyHandler({}), NoRedirect(),
        HTTPSHandler(context=ssl.create_default_context()))
    with client.open(request, timeout=8) as response:
        if getattr(response, "status", None) != 200:
            raise ValueError("DEMO_NON_200")
        # Defense in depth: even an injected or accidentally misconfigured
        # opener that followed an HTTP redirect must not return a successful
        # market data response from a different endpoint. The real urllib
        # HTTPSResponse has geturl(); unknown response objects fail closed.
        final_url = getattr(response, "geturl", None)
        if not callable(final_url) or final_url() != url:
            raise ValueError("DEMO_REDIRECT_OR_ENDPOINT_CHANGED")
        ct = response.headers.get("Content-Type", "")
        if not isinstance(ct, str) or ct.lower().split(";", 1)[0].strip() != "application/json":
            raise ValueError("DEMO_CONTENT_TYPE_INVALID")
        raw = response.read(MAX_BYTES + 1)
        if not isinstance(raw, bytes) or len(raw) > MAX_BYTES:
            raise ValueError("DEMO_PAGE_TOO_LARGE")
        try:
            body = json.loads(raw.decode("utf-8"))
        except (UnicodeError, ValueError):
            raise ValueError("DEMO_JSON_INVALID") from None
        if not isinstance(body, dict):
            raise ValueError("DEMO_JSON_OBJECT_REQUIRED")
        return {"httpStatus": 200, "response": body, "redirected": False}
