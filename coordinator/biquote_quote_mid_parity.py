"""Sealed BiQuote tick-MID versus CLOSED M15/H1/H4 OHLC consistency.

This diagnostic checks sampled quote midpoints against price ranges from the
same upstream feed and matching candle timestamp. It neither reconstructs
historical BID/ASK candles nor verifies broker rights, execution, or profit.
No HTTP, orders, price-bearing output, timestamps, or persistence.
"""
from __future__ import annotations

import datetime as dt
import math
import re

UTC = dt.timezone.utc
WIDTHS = {"M15": 900, "H1": 3600, "H4": 14400}
MAX_BARS = 45_000
MAX_QUOTES = 10_000
EPSILON_USD = 0.01
STAMP = re.compile(r"20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,3})?Z")


def _utc(value):
    if not isinstance(value, str) or not STAMP.fullmatch(value):
        raise ValueError("INVALID_TIME")
    t = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if t.utcoffset() != dt.timedelta(0):
        raise ValueError("INVALID_TIME")
    return t


def _price(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def audit_closed_quote_mid_parity(sealed):
    """Only fixed-format counters leave the authenticated private process.

    Repeated quote samples in one bar are counted as *observations*, not
    independent historical candles; absence of contradictions is limited
    self-consistency evidence, never a market-data entitlement.
    """
    base = {
        "mode": "PRIVATE_BIQUOTE_QUOTE_MID_CLOSED_OHLC_COUNTS_V1",
        "status": "UNAVAILABLE",
        "signal": "WAIT", "executable": False,
        "researchEligible": False, "paperOrdersAllowed": False,
        "liveOrdersAllowed": False, "brokerRightsVerified": False,
        "brokerSessionCalendarVerified": False,
        "independentBrokerPriceParityVerified": False,
        "historicalBidAskOHLCVerified": False,
        "sourceCandleBasis": "LIVE_MID_WITH_POSSIBLE_INITIAL_BID_SEED",
        "sourceQuoteSamples": 0,
        "frames": {},
    }
    try:
        if not isinstance(sealed, dict) or sealed.get("schema") != 1 or (
                sealed.get("source") != "BIQUOTE_UNVERIFIED_UPSTREAM_MT5"):
            raise ValueError("BAD_PRIVATE_ARCHIVE")
        closed = sealed.get("closed")
        quotes = sealed.get("quoteObservations")
        if (not isinstance(closed, dict) or set(closed) != set(WIDTHS)
                or not isinstance(quotes, list) or len(quotes) > MAX_QUOTES):
            raise ValueError("BAD_PRIVATE_ARCHIVE")
        indexes = {}
        summaries = {}
        for tf, width in WIDTHS.items():
            rows = closed[tf]
            if not isinstance(rows, list) or len(rows) > MAX_BARS:
                raise ValueError("BAD_FRAME")
            by_time = {}
            for item in rows:
                if not isinstance(item, dict):
                    raise ValueError("BAD_CLOSED_BAR")
                opened = _utc(item.get("openTime"))
                timestamp = int(opened.timestamp())
                if opened.microsecond or timestamp % width or timestamp in by_time:
                    raise ValueError("INVALID_CLOSED_BAR_GRID")
                values = [item.get(key) for key in ("open", "high", "low", "close")]
                if not all(_price(x) for x in values):
                    raise ValueError("INVALID_OHLC")
                o, hi, lo, c = values
                if hi < max(o, lo, c) or lo > min(o, hi, c):
                    raise ValueError("INVALID_OHLC")
                by_time[timestamp] = (lo, hi)
            indexes[tf] = by_time
            summaries[tf] = {
                "archivedClosedBars": len(by_time),
                "comparableQuoteSamples": 0,
                "withinClosedOHLC": 0,
                "outsideClosedOHLC": 0,
                "notInArchivedClosedBars": 0,
                "distinctComparableClosedBars": 0,
            }
        distinct = {tf: set() for tf in WIDTHS}
        for quote in quotes:
            if not isinstance(quote, dict):
                raise ValueError("INVALID_QUOTE")
            tick = _utc(quote.get("tickUTC"))
            receipt = _utc(quote.get("observedUTC"))
            if not 0 <= (receipt - tick).total_seconds() <= 30:
                raise ValueError("QUOTE_RECEIPT_NOT_FRESH")
            bid, ask = quote.get("bid"), quote.get("ask")
            if not _price(bid) or not _price(ask) or ask < bid:
                raise ValueError("INVALID_QUOTE")
            mid = (bid + ask) / 2
            if not math.isfinite(mid):
                raise ValueError("INVALID_QUOTE")
            stamp = int(tick.timestamp())
            for tf, width in WIDTHS.items():
                slot = (stamp // width) * width
                limits = indexes[tf].get(slot)
                item = summaries[tf]
                if limits is None:
                    item["notInArchivedClosedBars"] += 1
                    continue
                item["comparableQuoteSamples"] += 1
                distinct[tf].add(slot)
                low, high = limits
                if low - EPSILON_USD <= mid <= high + EPSILON_USD:
                    item["withinClosedOHLC"] += 1
                else:
                    item["outsideClosedOHLC"] += 1
        for tf in WIDTHS:
            summaries[tf]["distinctComparableClosedBars"] = len(distinct[tf])
        has_sample = any(x["comparableQuoteSamples"] for x in summaries.values())
        contradiction = any(x["outsideClosedOHLC"] for x in summaries.values())
        status = ("OBSERVED_MID_OUTSIDE_CLOSED_OHLC" if contradiction else
                  "CONSISTENT_OBSERVED_SAMPLES_ONLY" if has_sample else
                  "NO_COMPARABLE_CLOSED_SAMPLES")
        return {**base, "status": status, "sourceQuoteSamples": len(quotes),
                "frames": summaries}
    except (ValueError, TypeError, OverflowError, KeyError):
        return {**base, "status": "INVALID_ARCHIVE_WAIT"}
