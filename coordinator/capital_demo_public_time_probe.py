"""One unauthenticated Capital.com DEMO GET /api/v1/time reachability probe.

This is NOT gold market data or a license check. NO account credentials, API
key, session, broker quote, user position, order route or research signals.
Only the exact documented public demo server-time endpoint is requested.
"""
from __future__ import annotations

import json
import ssl
from urllib.request import Request, build_opener, ProxyHandler, HTTPSHandler, HTTPRedirectHandler

URL = "https://demo-api-capital.backend-capital.com/api/v1/time"
MAX_BYTES = 4096


class RejectRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise ValueError("DEMO_TIME_REDIRECT_NOT_PERMITTED")


def _report(status, reason):
    return {
        "mode": "CAPITAL_DEMO_PUBLIC_TIME_REACHABILITY_ONLY",
        "status": status, "reason": reason,
        "onlyRequested": "GET_DEMO_API_TIME_WITHOUT_AUTH",
        "demoTimeEndpointReachable": status == "PUBLIC_DEMO_TIME_REACHABLE",
        "credentialsUsed": False, "apiKeyUsed": False,
        "ordersSent": 0, "marketDataRequested": False,
        "goldCandlesRetrieved": 0, "marketDataRightsVerified": False,
        "renderConnectionVerified": False, "pricesReady": False,
        "signal": "WAIT", "executable": False,
        "paperOrdersAllowed": False, "liveOrdersAllowed": False,
    }


def probe(*, opener=None):
    try:
        # Construct URL and HTTP method internally, never take user-supplied
        # host, path, token, cookies, or headers.
        client = opener or build_opener(
            ProxyHandler({}),
            RejectRedirect(),
            HTTPSHandler(context=ssl.create_default_context()))
        request = Request(URL, headers={"Accept": "application/json"}, method="GET")
        with client.open(request, timeout=8) as response:
            if response.status != 200 or response.geturl() != URL:
                return _report("BLOCKED", "NOT_AN_EXACT_DEMO_TIME_RESPONSE")
            content_type = response.headers.get("Content-Type", "")
            if content_type.lower().split(";", 1)[0].strip() != "application/json":
                return _report("BLOCKED", "DEMO_TIME_CONTENT_TYPE_NOT_JSON")
            raw = response.read(MAX_BYTES + 1)
            if not isinstance(raw, bytes) or len(raw) > MAX_BYTES:
                return _report("BLOCKED", "DEMO_TIME_RESPONSE_TOO_LARGE")
            payload = json.loads(raw.decode("utf-8"))
            if not isinstance(payload, dict):
                return _report("BLOCKED", "DEMO_TIME_RESPONSE_NOT_OBJECT")
        return _report("PUBLIC_DEMO_TIME_REACHABLE", "NO_MARKET_DATA_RIGHTS_INFERRED")
    except Exception:
        # Never return exception details, URLs from redirects, response body
        # or any headers in outputs; this probe has no credentials to leak.
        return _report("BLOCKED", "DEMO_TIME_UNAVAILABLE_OR_INVALID")


if __name__ == "__main__":
    result = probe()
    print(json.dumps(result, sort_keys=True))
    if not result["demoTimeEndpointReachable"]:
        raise SystemExit(1)
