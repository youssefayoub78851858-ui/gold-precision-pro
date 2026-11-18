"""Private BiQuote quote-receipt cadence audit, not broker uptime proof.

Offline on the owner-only, already SHA-sealed research vault. Counts the
intervals between received, valid BID/ASK observations in coarse bins.
Broker sessions and planned closures are UNKNOWN, so delayed/skipped samples
must never automatically be labelled as a vendor outage or a trade signal.
No quotes, prices, timestamps, paths, credentials, or execution rights returned.
"""
from __future__ import annotations

import datetime as dt
import math
import re

UTC = dt.timezone.utc
STAMP = re.compile(r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,3})?Z")
MAX_SAMPLES = 10000
INTERVAL_BINS = ("LE_150_SECONDS", "GT_150_LE_300_SECONDS",
                 "GT_300_LE_600_SECONDS", "GT_600_LE_3600_SECONDS",
                 "GT_3600_SECONDS")
LAG_BINS = ("LE_5_SECONDS", "GT_5_LE_15_SECONDS", "GT_15_LE_30_SECONDS")
BASE = {
    "mode": "BIQUOTE_PRIVATE_SAMPLED_QUOTE_CADENCE_COUNTS_V1",
    "status": "INVALID_ARCHIVE_WAIT",
    "signal": "WAIT", "executable": False,
    "paperOrdersAllowed": False, "liveOrdersAllowed": False,
    "brokerRightsVerified": False, "brokerCalendarVerified": False,
    "continuousMarketDataVerified": False,
    "missingSamplesAreMarketOutageProof": False,
    "longGapsAreBrokerClosures": False,
    "tradeReady": False,
    "sourceQuoteSamples": 0, "observedIntervals": 0,
    "intervalBins": {k: 0 for k in INTERVAL_BINS},
    "quoteReceiptLagBins": {k: 0 for k in LAG_BINS},
}


def _stamp(value):
    if not isinstance(value, str) or not STAMP.fullmatch(value):
        raise ValueError("INVALID_UTC")
    stamp = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.utcoffset() != dt.timedelta(0):
        raise ValueError("INVALID_UTC")
    return stamp


def audit_quote_cadence(sealed):
    """Count quote timestamps and sampled receipt gaps without fabricating ticks.

    A two-minute sampler is NOT a continuous tick feed. No sample outside
    market hours can be inferred; a gap may mean broker closure, missed poll,
    process restart, or source failure. No source is queried.
    """
    try:
        if (not isinstance(sealed, dict) or sealed.get("schema") != 1 or
                sealed.get("source") != "BIQUOTE_UNVERIFIED_UPSTREAM_MT5"):
            raise ValueError("UNVERIFIED_ARCHIVE")
        rows = sealed.get("quoteObservations")
        if not isinstance(rows, list) or len(rows) > MAX_SAMPLES:
            raise ValueError("UNVERIFIED_QUOTE_COUNT")
        intervals = {key: 0 for key in INTERVAL_BINS}
        lag_counts = {key: 0 for key in LAG_BINS}
        previous_tick = None
        previous_received = None
        for item in rows:
            if not isinstance(item, dict):
                raise ValueError("INVALID_SAMPLE")
            tick = _stamp(item.get("tickUTC"))
            received = _stamp(item.get("observedUTC"))
            lag = (received - tick).total_seconds()
            if (not math.isfinite(lag) or not 0 <= lag <= 30 or
                    (previous_tick is not None and tick <= previous_tick) or
                    (previous_received is not None and received <= previous_received)):
                raise ValueError("INVALID_SAMPLE_SEQUENCE")
            bid, ask, spread = (item.get("bid"), item.get("ask"),
                                item.get("spread"))
            if (any(type(x) not in (float, int) or not math.isfinite(x)
                    for x in (bid, ask, spread)) or
                    not 0 < bid <= ask or spread < 0 or
                    abs(round(ask - bid, 8) - spread) > 1e-5):
                raise ValueError("QUOTE_SPREAD_CONTRADICTION")
            if lag <= 5:
                lag_counts["LE_5_SECONDS"] += 1
            elif lag <= 15:
                lag_counts["GT_5_LE_15_SECONDS"] += 1
            else:
                lag_counts["GT_15_LE_30_SECONDS"] += 1
            if previous_received is not None:
                span = (received - previous_received).total_seconds()
                if span <= 150:
                    key = "LE_150_SECONDS"
                elif span <= 300:
                    key = "GT_150_LE_300_SECONDS"
                elif span <= 600:
                    key = "GT_300_LE_600_SECONDS"
                elif span <= 3600:
                    key = "GT_600_LE_3600_SECONDS"
                else:
                    key = "GT_3600_SECONDS"
                intervals[key] += 1
            previous_received, previous_tick = received, tick
        return {**BASE,
                "status": ("SPARSE_RECEIPT_CADENCE_OBSERVED_ONLY" if rows else
                           "NO_RECORDED_QUOTES"),
                "sourceQuoteSamples": len(rows),
                "observedIntervals": max(0, len(rows)-1),
                "intervalBins": intervals, "quoteReceiptLagBins": lag_counts}
    except (ValueError, TypeError, OverflowError):
        return {**BASE}
