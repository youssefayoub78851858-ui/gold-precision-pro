"""Offline-only normalizer for Massive C:XAUUSD aggregate response fixtures.

There is deliberately no transport, key handling, persistence, or provider call.
All payloads produced for this adapter are synthetic test inputs and remain
quarantined by ``xauusd_feed_gate``.
"""
from __future__ import annotations

import datetime as dt
import math


SYMBOL = "C:XAUUSD"
INTERVALS = {
    "15min": (15, "minute"),
    "1h": (1, "hour"),
    "4h": (4, "hour"),
}


def aggregate_spec(interval: str) -> dict:
    """Return the documented aggregate granularity; does not build/send a URL."""
    if interval not in INTERVALS:
        raise ValueError("unsupported interval")
    multiplier, timespan = INTERVALS[interval]
    return {"symbol": SYMBOL, "multiplier": multiplier, "timespan": timespan}


def normalize_fixture_response(interval: str, response: dict) -> dict:
    """Normalize a synthetic Massive-shaped JSON fixture into closed-bar rows.

    Aggregate ``v`` is not copied: for currencies it represents quote activity,
    not executed trade volume. The downstream gate rechecks UTC alignment,
    closure, freshness, and expected-session gaps.
    """
    aggregate_spec(interval)
    if not isinstance(response, dict) or response.get("status") != "OK":
        raise ValueError("fixture response status must be OK")
    if response.get("ticker") != SYMBOL:
        raise ValueError("fixture ticker must be C:XAUUSD")
    results = response.get("results")
    if not isinstance(results, list) or not results:
        raise ValueError("fixture aggregate results are unavailable")
    width_seconds = {"15min": 900, "1h": 3600, "4h": 14400}[interval]
    candles = []
    for row in results:
        if not isinstance(row, dict):
            raise ValueError("aggregate row must be an object")
        stamp = row.get("t")
        if isinstance(stamp, bool) or not isinstance(stamp, (int, float)) or not math.isfinite(stamp):
            raise ValueError("aggregate timestamp must be epoch milliseconds")
        opened = dt.datetime.fromtimestamp(stamp / 1000, tz=dt.timezone.utc)
        if opened.timestamp() % width_seconds:
            raise ValueError("aggregate timestamp is not UTC interval aligned")
        values = {}
        for source, target in (("o", "open"), ("h", "high"), ("l", "low"), ("c", "close")):
            value = row.get(source)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError("invalid aggregate OHLC")
            values[target] = float(value)
        if values["high"] < max(values["open"], values["close"], values["low"]):
            raise ValueError("invalid aggregate high")
        if values["low"] > min(values["open"], values["close"], values["high"]):
            raise ValueError("invalid aggregate low")
        candles.append({"openTime": opened.isoformat().replace("+00:00", "Z"), **values})
    if [bar["openTime"] for bar in candles] != sorted({bar["openTime"] for bar in candles}):
        raise ValueError("fixture aggregate bars must be unique and oldest first")
    return {"provider": "Massive", "symbol": SYMBOL, "interval": interval,
            "candles": candles, "sourceDataMode": "synthetic",
            "researchEligible": False, "signal": "WAIT", "executable": False}


def build_synthetic_gate_payload(responses: dict, received_utc: str,
                                 expected_open_times: dict) -> dict:
    """Build only a clearly synthetic gate payload from three fixture responses."""
    if not isinstance(responses, dict) or set(responses) != set(INTERVALS):
        raise ValueError("fixture responses for M15/H1/H4 are required")
    if not isinstance(expected_open_times, dict) or set(expected_open_times) != set(INTERVALS):
        raise ValueError("expected open times for M15/H1/H4 are required")
    frames = {}
    for interval in INTERVALS:
        normalized = normalize_fixture_response(interval, responses[interval])
        frames[interval] = {"candles": normalized["candles"],
                             "expectedOpenTimes": expected_open_times[interval]}
    return {"provider": "Massive synthetic fixture", "instrument": "XAU/USD",
            "mode": "synthetic", "receivedUTC": received_utc, "frames": frames,
            "researchEligible": False, "signal": "WAIT", "executable": False}
