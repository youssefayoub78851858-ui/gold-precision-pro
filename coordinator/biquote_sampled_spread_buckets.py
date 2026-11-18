"""Private, price-free sampled XAUUSD bid/ask spread distribution.

The samples belong to BiQuote's unverified upstream MT5 broker and are not
broker execution fills, licensed historical bid/ask OHLC, or net PnL evidence.
No network, files, orders, price levels, source tick timestamps or secrets in
the returned report. Never grants BUY/SELL or paper/live order permission.
"""
from __future__ import annotations
import datetime as dt
import math
import re

STAMP = re.compile(r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,3})?Z")
BINS = ("LE_0_25", "GT_0_25_LE_0_50", "GT_0_50_LE_1",
        "GT_1_LE_2", "GT_2_LE_5", "GT_5")
MAX_QUOTES = 10000
SAFE = {
    "mode": "BIQUOTE_PRIVATE_SAMPLED_SPREAD_COUNTS_V1",
    "status": "INVALID_ARCHIVE_WAIT",
    "signal": "WAIT", "executable": False,
    "paperOrdersAllowed": False, "liveOrdersAllowed": False,
    "sourceRightsVerified": False, "upstreamBrokerVerified": False,
    "historicalBidAskOHLCVerified": False,
    "brokerCommissionSlippageVerified": False,
    "independentNetExpectancyVerified": False,
    "sampleIntervalNotContinuousTickFeed": True,
    "sourceQuoteSamples": 0,
    "buckets": {name: 0 for name in BINS},
}


def _stamp(x):
    if not isinstance(x, str) or not STAMP.fullmatch(x):
        raise ValueError("INVALID_QUOTE_TIMESTAMP")
    t = dt.datetime.fromisoformat(x.replace("Z", "+00:00"))
    if t.utcoffset() != dt.timedelta(0):
        raise ValueError("INVALID_QUOTE_TIMESTAMP")
    return t


def audited_sampled_spread_buckets(vault):
    """Return only histogram counts, fail closed on malformed quotes.

    Every bucket is in USD per gold ounce, not dollars per 0.01 MT5 lot.
    Samples are periodic and not a market-tick stream; no broker fees,
    contract multiplier, commission or fill slippage may be inferred.
    """
    try:
        if (not isinstance(vault, dict) or vault.get("schema") != 1
                or vault.get("source") != "BIQUOTE_UNVERIFIED_UPSTREAM_MT5"):
            raise ValueError("NOT_SEALED_BIQUOTE")
        quotes = vault.get("quoteObservations")
        if not isinstance(quotes, list) or len(quotes) > MAX_QUOTES:
            raise ValueError("INVALID_SAMPLE_COUNT")
        counts = {name: 0 for name in BINS}
        previous = None
        for q in quotes:
            if not isinstance(q, dict):
                raise ValueError("INVALID_QUOTE")
            tick, received = _stamp(q.get("tickUTC")), _stamp(q.get("observedUTC"))
            lag = (received - tick).total_seconds()
            if not 0 <= lag <= 30 or (previous is not None and tick <= previous):
                raise ValueError("INVALID_QUOTE_UTC_SEQUENCE")
            previous = tick
            bid, ask, stored = q.get("bid"), q.get("ask"), q.get("spread")
            if (type(bid) not in (int, float) or type(ask) not in (int, float)
                    or type(stored) not in (int, float)
                    or not all(math.isfinite(x) for x in (bid, ask, stored))
                    or not 0 < bid <= ask or stored < 0):
                raise ValueError("INVALID_BID_ASK_OR_SPREAD")
            spread = ask - bid
            if not math.isfinite(spread) or abs(round(spread, 8) - stored) > 0.00001:
                raise ValueError("SPREAD_REPORTED_NOT_BID_ASK")
            if spread <= .25:
                name = "LE_0_25"
            elif spread <= .50:
                name = "GT_0_25_LE_0_50"
            elif spread <= 1:
                name = "GT_0_50_LE_1"
            elif spread <= 2:
                name = "GT_1_LE_2"
            elif spread <= 5:
                name = "GT_2_LE_5"
            else:
                name = "GT_5"
            counts[name] += 1
        return {**SAFE, "status": ("OBSERVED_SPARSE_QUOTES_ONLY" if quotes else
                                  "NO_RECORDED_QUOTES"), "sourceQuoteSamples": len(quotes),
                "buckets": counts}
    except (ValueError, TypeError, OverflowError):
        return {**SAFE}
