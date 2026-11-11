"""Fail-closed, provider-neutral XAU/USD candle intake contract.

No HTTP client or provider credentials are implemented here. A future adapter
must authenticate a signed payload, normalize it to this schema, and pass the
source-rights gate before any data can be considered admissible. This module
never creates a BUY/SELL signal.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import math
import re
from dataclasses import dataclass

UTC = dt.timezone.utc
INTERVALS = {"15min": 900, "1h": 3600, "4h": 14400}
MAX_AGE_SECONDS = {"15min": 20 * 60, "1h": 75 * 60, "4h": 5 * 60 * 60}
OHLC = ("open", "high", "low", "close")


def parse_utc(value: str) -> dt.datetime:
    if not isinstance(value, str) or not value:
        raise ValueError("UTC timestamp required")
    try:
        parsed = dt.datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    except ValueError as error:
        raise ValueError("invalid UTC timestamp") from error
    if parsed.tzinfo is None or parsed.utcoffset() != dt.timedelta(0):
        raise ValueError("UTC timestamp required")
    return parsed.astimezone(UTC)


def _seconds(value: dt.datetime) -> int:
    return int(value.timestamp())


@dataclass(frozen=True)
class SourcePolicy:
    """Rights and deployment gates; all authorization flags default closed."""
    enabled: bool = False
    source_approved: bool = False
    cloud_use_allowed: bool = False
    entitlement_verified: bool = False
    rights_reference: str = ""
    expected_provider: str = ""

    @property
    def authorized(self) -> bool:
        return bool(self.enabled and self.source_approved and self.cloud_use_allowed
                    and self.entitlement_verified and self.rights_reference.strip())


class ReplayGuard:
    """Small nonce cache intended to live for one receiver process."""
    def __init__(self):
        self._nonces: dict[str, int] = {}

    def accept(self, nonce: str, now_epoch: int, ttl_seconds: int = 300) -> bool:
        self._nonces = {key: expiry for key, expiry in self._nonces.items() if expiry >= now_epoch}
        if not isinstance(nonce, str) or not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", nonce):
            return False
        if nonce in self._nonces:
            return False
        self._nonces[nonce] = now_epoch + ttl_seconds
        return True


def verify_signed_body(raw_body: bytes, headers: dict, secret: str, now: dt.datetime,
                       replay_guard: ReplayGuard, max_skew_seconds: int = 60) -> dict:
    """Verify timestamped HMAC-SHA256; never returns/logs secret or signature."""
    if not isinstance(raw_body, bytes) or not secret or len(secret.encode("utf-8")) < 32:
        raise ValueError("receiver secret unavailable or too short")
    try:
        stamp = int(headers["X-GPP-Timestamp"])
        nonce = headers["X-GPP-Nonce"]
        supplied = headers["X-GPP-Signature"]
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("signature headers missing") from error
    current = _seconds(parse_utc(now.isoformat()))
    if abs(current - stamp) > max_skew_seconds:
        raise ValueError("signed payload timestamp outside allowed skew")
    digest = hashlib.sha256(raw_body).hexdigest()
    message = f"{stamp}\n{nonce}\n{digest}".encode("utf-8")
    expected = "sha256=" + hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
    if not isinstance(supplied, str) or not hmac.compare_digest(expected, supplied):
        raise ValueError("signature invalid")
    if not replay_guard.accept(nonce, current):
        raise ValueError("nonce invalid or replayed")
    try:
        payload = json.loads(raw_body)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("signed body must contain valid JSON") from error
    if not isinstance(payload, dict):
        raise ValueError("payload object required")
    return payload


def _validate_candle(row: dict, interval: str, now: dt.datetime) -> tuple[dt.datetime, dict]:
    if not isinstance(row, dict):
        raise ValueError("candle object required")
    opened = parse_utc(row.get("openTime"))
    width = INTERVALS[interval]
    if _seconds(opened) % width:
        raise ValueError(f"{interval} candle is not UTC-aligned")
    close_time = opened + dt.timedelta(seconds=width)
    if close_time > now:
        raise ValueError(f"forming or future {interval} candle")
    prices = []
    for name in OHLC:
        value = row.get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError("invalid OHLC value")
        prices.append(float(value))
    opn, high, low, close = prices
    if high < max(opn, close, low) or low > min(opn, close, high):
        raise ValueError("invalid OHLC range")
    normalized = {"openTime": opened.isoformat().replace("+00:00", "Z"),
                  **dict(zip(OHLC, prices))}
    volume = row.get("volume")
    if volume is not None:
        if isinstance(volume, bool) or not isinstance(volume, (int, float)) or not math.isfinite(volume) or volume < 0:
            raise ValueError("invalid volume")
        normalized["volume"] = float(volume)
    return opened, normalized


def validate_frame(interval: str, frame: dict, now: dt.datetime) -> dict:
    if interval not in INTERVALS or not isinstance(frame, dict):
        raise ValueError("unsupported interval or frame")
    now = parse_utc(now.isoformat())
    candles = frame.get("candles")
    expected_values = frame.get("expectedOpenTimes")
    if not isinstance(candles, list) or not candles:
        raise ValueError(f"{interval} candles missing")
    if not isinstance(expected_values, list) or not expected_values:
        raise ValueError(f"{interval} expected session schedule missing")
    parsed = [_validate_candle(row, interval, now) for row in candles]
    opens = [item[0] for item in parsed]
    if opens != sorted(opens) or len(opens) != len(set(opens)):
        raise ValueError(f"{interval} duplicate or unordered candles")
    expected = [parse_utc(value) for value in expected_values]
    width = INTERVALS[interval]
    if expected != sorted(expected) or len(expected) != len(set(expected)):
        raise ValueError(f"{interval} expected schedule duplicate or unordered")
    if any(_seconds(value) % width or value + dt.timedelta(seconds=width) > now for value in expected):
        raise ValueError(f"{interval} expected schedule contains unclosed or unaligned bars")
    observed = set(opens)
    expected_set = set(expected)
    missing = sorted(expected_set - observed)
    unexpected = sorted(observed - expected_set)
    gaps = [value.isoformat().replace("+00:00", "Z") for value in missing]
    if unexpected:
        raise ValueError(f"{interval} candles fall outside declared schedule")
    if gaps:
        raise ValueError(f"{interval} candle gap: {','.join(gaps)}")
    latest_close = opens[-1] + dt.timedelta(seconds=width)
    age = (now - latest_close).total_seconds()
    if age < 0 or age > MAX_AGE_SECONDS[interval]:
        raise ValueError(f"{interval} latest closed candle is stale")
    return {"interval": interval, "count": len(parsed), "latestOpenUTC": parsed[-1][1]["openTime"],
            "latestCloseUTC": latest_close.isoformat().replace("+00:00", "Z"),
            "ageSeconds": int(age), "gaps": gaps, "closed": True, "aligned": True,
            "candles": [item[1] for item in parsed]}


def intake_payload(payload: dict, now: dt.datetime, policy: SourcePolicy) -> dict:
    """Validate a packet; explicitly synthetic packets stay quarantined from research."""
    reasons = []
    mode = payload.get("mode") if isinstance(payload, dict) else None
    if mode not in {"live", "recorded", "synthetic"}:
        reasons.append("DATA_MODE_UNRECOGNIZED")
    if mode in {"live", "recorded"} and not policy.authorized:
        reasons.append("SOURCE_RIGHTS_OR_ENABLEMENT_NOT_VERIFIED")
    if not isinstance(payload, dict):
        reasons.append("PAYLOAD_INVALID")
        payload = {}
    if payload.get("instrument") != "XAU/USD":
        reasons.append("INSTRUMENT_IDENTITY_UNCONFIRMED")
    provider = payload.get("provider")
    if not isinstance(provider, str) or not provider.strip() or (policy.expected_provider and provider != policy.expected_provider):
        reasons.append("PROVIDER_IDENTITY_MISMATCH")
    try:
        received = parse_utc(payload.get("receivedUTC"))
        now_utc = parse_utc(now.isoformat())
        if received > now_utc + dt.timedelta(seconds=60) or (now_utc - received).total_seconds() > 120:
            reasons.append("INGEST_PACKET_STALE_OR_FUTURE")
    except (TypeError, ValueError):
        now_utc = parse_utc(now.isoformat())
        reasons.append("INGEST_TIMESTAMP_INVALID")
    frames = payload.get("frames")
    validated = {}
    if not isinstance(frames, dict) or set(frames) != set(INTERVALS):
        reasons.append("M15_H1_H4_REQUIRED")
    else:
        for interval in INTERVALS:
            try:
                validated[interval] = validate_frame(interval, frames[interval], now_utc)
            except (TypeError, ValueError) as error:
                reasons.append(f"{interval.upper()}_REJECTED:{error}")
    if reasons:
        validated = {}
    synthetic = mode == "synthetic" and not reasons
    status = "SYNTHETIC_TEST_ONLY" if synthetic else "ADMISSIBLE_FOR_RESEARCH_ONLY" if not reasons else "BLOCKED"
    blocking_reasons = ["SYNTHETIC_DATA_NOT_REAL_MARKET_EVIDENCE"] if synthetic else reasons
    return {"status": status,
            "sourceDataMode": mode or "unknown", "provider": provider,
            "instrument": payload.get("instrument"), "frames": validated,
            "blockingReasons": blocking_reasons, "researchEligible": status == "ADMISSIBLE_FOR_RESEARCH_ONLY",
            "signal": "WAIT", "executable": False,
            "sourceRequestsMade": 0, "secretPersisted": False}


def retry_delay_seconds(failure_count: int, base_seconds: int = 5, maximum_seconds: int = 300) -> int:
    """Bounded exponential delay for adapter outages; does not perform retries."""
    if isinstance(failure_count, bool) or not isinstance(failure_count, int) or failure_count < 0:
        raise ValueError("failure_count must be a non-negative integer")
    if base_seconds < 1 or maximum_seconds < base_seconds:
        raise ValueError("invalid retry bounds")
    return min(maximum_seconds, base_seconds * (2 ** min(failure_count, 30)))

