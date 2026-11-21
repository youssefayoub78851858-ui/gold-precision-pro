"""Capital Demo narrow PRIVATE price GET boundary. Disabled unless explicitly activated.

Only an isolated, separately approved private collector may import/use this.
Capital API credentials are TRADING-CAPABLE: this module never receives an API
key or password, cannot create a session or construct any order endpoint.
It requires externally obtained short-lived Demo CST / X-SECURITY-TOKEN values.
Source rights, clock parity, broker costs and holdout are NOT attested here.

Provider transport is deliberately dependency-injected: NO transport is used
unless operator-specific env/permissions are explicitly enabled. Even then,
a separate network egress policy is required for true account isolation.
"""
from __future__ import annotations

import datetime as dt
import os
import re
from urllib.parse import urlencode

from capital_demo_offline_adapter import (
    DEMO_BASE_URL, RESOLUTIONS, _normalize_row,
    audit_demo_get_only_request,
)

ENABLE_ENV = "CAPITAL_DEMO_PRIVATE_PRICE_GET_ENABLED"
RIGHTS_ENV = "CAPITAL_DEMO_PRIVATE_RIGHTS_DOCUMENTED"
ENABLE_VALUE = "APPROVED_PRIVATE_REVIEW_ONLY"
UTC = dt.timezone.utc
MAX_PAGE_ROWS = 1000


def _result(code):
    return {
        "mode": "CAPITAL_DEMO_PRIVATE_PRICE_GET_BOUNDARY_V1",
        "status": "BLOCKED", "reason": code,
        "signal": "WAIT", "executable": False, "researchEligible": False,
        "paperOrdersAllowed": False, "liveOrdersAllowed": False,
        "orderRouteSupported": False, "liveHostAllowed": False,
        "credentialLoginSupported": False,
        "brokerOrdersSent": 0, "providerRequestsMade": 0,
        "transportCallsAttempted": 0,
        "pageRowsChecked": 0,
        "sourceRightsIndependentlyAttested": False,
        "brokerSessionCalendarVerified": False,
        "pointInTimeReceiptAttested": False,
        "brokerCostEvidenceVerified": False,
        "prospectivePaperPerformanceProven": False,
    }


def _token(v):
    return (isinstance(v, str) and 24 <= len(v) <= 512
            and re.fullmatch(r"[A-Za-z0-9+/_=.:-]+", v) is not None)


def inspect_private_demo_page(chunk, *, cst=None, security_token=None,
                              explicit_operator_approval=False,
                              transport=None, deliver_private=None):
    """Perform at most ONE restricted Demo price GET with explicit operator gates.

    transport(method, url, headers) must be supplied by a separately reviewed
    private network layer; it must not auto-follow redirects. The response
    is checked in-memory and forwarded solely to the private deliver callback.
    Only bounded counts leave this function, never prices, quotes or tokens.
    deliver_private(payload) must return EXACTLY
    {"committed": True, "storedRows": len(payload["prices"])}; a
    caller assertion is not independent disk or provider verification.
    """
    request_attempted = False

    def safe_block(code):
        # Count calls to the injected transport even when the HTTP response,
        # data page or private archive fails. This is an ATTEMPT count,
        # not evidence that the provider actually received the request.
        result = _result(code)
        result["providerRequestsMade"] = int(request_attempted)
        result["transportCallsAttempted"] = int(request_attempted)
        return result

    fail = safe_block("PRIVATE_DEMO_GET_STANDBY")
    try:
        if (os.environ.get(ENABLE_ENV) != ENABLE_VALUE or
                os.environ.get(RIGHTS_ENV) != ENABLE_VALUE or
                explicit_operator_approval is not True):
            return fail
        if not callable(transport) or not callable(deliver_private):
            return safe_block("ISOLATED_PRIVATE_TRANSPORT_NOT_CONFIGURED")
        if not (_token(cst) and _token(security_token)):
            return safe_block("SHORT_LIVED_DEMO_SESSION_TOKENS_REQUIRED")
        if not isinstance(chunk, dict) or set(chunk) != {
                "request", "firstExpectedOpenUTC", "expectedEndExclusiveUTC",
                "expectedClosedSlots", "providerToBoundMayBeInclusive",
                "responseWindowMustBeVerified"}:
            return safe_block("INVALID_DISABLED_DEMO_HISTORY_CHUNK")
        spec = chunk["request"]
        if audit_demo_get_only_request(spec)["requestShapeAcceptable"] is not True:
            return safe_block("DEMO_PRICE_GET_ONLY_SPEC_REJECTED")
        width = next(
            (s for resolution, s in RESOLUTIONS.values()
             if spec["query"]["resolution"] == resolution), None)
        if width is None:
            return safe_block("UNRECOGNIZED_CANDLE_RESOLUTION")
        first = dt.datetime.fromisoformat(
            chunk["firstExpectedOpenUTC"].replace("Z", "+00:00"))
        end = dt.datetime.fromisoformat(
            chunk["expectedEndExclusiveUTC"].replace("Z", "+00:00"))
        if (first.tzinfo is None or end.tzinfo is None or
                first.utcoffset() != dt.timedelta(0) or
                end.utcoffset() != dt.timedelta(0) or
                not first < end or (end - first).total_seconds() !=
                chunk["expectedClosedSlots"] * width or
                type(chunk["expectedClosedSlots"]) is not int or
                not 1 <= chunk["expectedClosedSlots"] <= 900 or
                chunk["providerToBoundMayBeInclusive"] is not True or
                chunk["responseWindowMustBeVerified"] is not True):
            return safe_block("INVALID_EXACT_CLOSED_CANDLE_WINDOW")
        # Exact timestamped query bounds; never let a caller-controlled host,
        # path, HTTP method or arbitrary query parameter cross this boundary.
        expected_from = first.strftime("%Y-%m-%dT%H:%M:%S")
        expected_to = (end - dt.timedelta(seconds=width-1)).strftime(
            "%Y-%m-%dT%H:%M:%S")
        if (spec["query"]["from"] != expected_from or
                spec["query"]["to"] != expected_to):
            return safe_block("DEMO_WINDOW_DIFFERENT_FROM_APPROVED_PLAN")
        url = DEMO_BASE_URL + spec["path"] + "?" + urlencode(
            [(k, spec["query"][k]) for k in ("resolution", "from", "to", "max")]
        )
        # CST/session token powers trading at provider level. Never write it
        # to any log, UI response, URL, public DB, fixture or code.
        request_attempted = True
        reply = transport(
            "GET", url, {"CST": cst, "X-SECURITY-TOKEN": security_token})
        if (not isinstance(reply, dict) or
                set(reply) != {"httpStatus", "response", "redirected"} or
                type(reply["httpStatus"]) is not int or
                reply["httpStatus"] != 200 or reply["redirected"] is not False):
            return safe_block("DEMO_GET_HTTP_STATUS_OR_REDIRECT_REJECTED")
        payload = reply["response"]
        if (not isinstance(payload, dict) or
                payload.get("epic") != spec["path"].split("/")[-1] or
                payload.get("resolution") != spec["query"]["resolution"]):
            return safe_block("BROKER_PRICE_PAGE_IDENTITY_UNVERIFIED")
        prices = payload.get("prices")
        if not isinstance(prices, list) or len(prices) > MAX_PAGE_ROWS:
            return safe_block("BOUNDED_PRICE_PAGE_REQUIRED")
        # A 200 response containing zero candles is not a successful
        # capture. Nor may one requested window return more DISTINCT slots
        # than its approved closed-candle capacity. Never pad missing bars:
        # real session closures still need separate calendar verification.
        if not prices:
            return safe_block("BROKER_PRICE_PAGE_EMPTY_NOT_OBSERVED")
        if len(prices) > chunk["expectedClosedSlots"]:
            return safe_block("BROKER_PRICE_PAGE_EXCEEDS_APPROVED_WINDOW")
        prior = None
        seen = set()
        for row in prices:
            stamp, bid, ask = _normalize_row(row, width, end)
            opened = dt.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            if (not first <= opened < end or stamp in seen or
                    (prior is not None and stamp <= prior)):
                return safe_block("BROKER_HISTORY_OUTSIDE_EXACT_WINDOW_OR_DUPLICATE")
            prior = stamp
            seen.add(stamp)
        # Controlled callback only; raw prices are NOT returned in the report.
        # If downstream archival fails, never claim the page was received.
        delivery_result = deliver_private(payload)
        # A callback returning None (e.g. list.append), True or a guessed
        # count does NOT prove the private sink accepted the full page.
        # Require a strict, bounded receipt from the separately reviewed sink.
        # This receipt is only a callback assertion, NOT independent
        # persistence, market provenance, or source-rights attestation.
        if delivery_result is False:
            return safe_block("PRIVATE_DEMO_ARCHIVE_REFUSED_PAGE")
        if (not isinstance(delivery_result, dict)
                or set(delivery_result) != {"committed", "storedRows"}
                or delivery_result["committed"] is not True
                or type(delivery_result["storedRows"]) is not int
                or delivery_result["storedRows"] != len(prices)):
            return safe_block("PRIVATE_DEMO_ARCHIVE_ACKNOWLEDGEMENT_REQUIRED")
        report = _result("REQUIRES_INDEPENDENT_DATA_RIGHTS_AND_RECEIPT_AUDIT")
        report.update(
            status="PRIVATE_DEMO_GEOMETRY_ONLY_NOT_ADMITTED",
            providerRequestsMade=1, transportCallsAttempted=1,
            pageRowsChecked=len(prices),
            unclassifiedMissingClosedSlots=(
                chunk["expectedClosedSlots"] - len(prices)
            ),
            completeUTCGridWindowObserved=(
                len(prices) == chunk["expectedClosedSlots"]
            ),
            originalBrokerSessionVerified=False,
        )
        return report
    except (KeyError, ValueError, TypeError, OverflowError, AttributeError,
            OSError, StopIteration):
        return safe_block("INVALID_OR_UNAVAILABLE_PRIVATE_PRICE_PAGE")
    except Exception:
        # Unexpected transport/storage errors may contain credentials in
        # their messages. Only a fixed safe code crosses this boundary.
        return safe_block("PRIVATE_DEMO_TRANSPORT_OR_ARCHIVE_ERROR")
