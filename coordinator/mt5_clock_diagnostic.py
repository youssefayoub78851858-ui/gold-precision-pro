"""Offline, read-only MT5 clock-basis diagnostic.

Requires two actual MT5 Demo CSV captures bracketing a broker DST transition,
plus independently observed UTC reference timestamps. It has no network client,
does not sign in to MT5, and never changes the importer research gate.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import pathlib

UTC = dt.timezone.utc


def _utc(value: str) -> dt.datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("independent UTC reference is required")
    parsed = dt.datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != dt.timedelta(0):
        raise ValueError("independent clock value must have explicit UTC offset")
    return parsed.astimezone(UTC)


def sample_from_csv(path: str, phase: str, trusted_utc: str) -> dict:
    """Read the newest raw M15 bar and tick/clock fields from one local export."""
    if phase not in {"before_transition", "after_transition"}:
        raise ValueError("phase must be before_transition or after_transition")
    with pathlib.Path(path).open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    rows = [row for row in rows if row.get("symbol") != "#SNAPSHOT_END"]
    if not rows:
        raise ValueError("MT5 snapshot contains no data rows")
    last = rows[-1]
    required = ("bar_open_epoch_seconds", "quote_epoch_milliseconds",
                "time_current_server_label", "time_gmt_epoch_seconds")
    if any(not last.get(field) for field in required):
        raise ValueError("MT5 snapshot lacks raw diagnostic clock fields")
    return {
        "phase": phase,
        "trustedUTC": trusted_utc,
        "barEpochSeconds": int(last["bar_open_epoch_seconds"]),
        "tickEpochMilliseconds": int(last["quote_epoch_milliseconds"]),
        "timeCurrentServerLabel": last["time_current_server_label"],
        "timeGmtEpochSeconds": int(last["time_gmt_epoch_seconds"]),
    }


def diagnose(samples: list[dict], trusted_clock_source: str,
             expected_server_shift_seconds: int,
             max_clock_skew_seconds: int = 120,
             max_bar_age_seconds: int = 3600) -> dict:
    """Check independent UTC agreement and observed server-clock DST shift."""
    reasons = []
    if not isinstance(trusted_clock_source, str) or not trusted_clock_source.strip():
        reasons.append("INDEPENDENT_CLOCK_SOURCE_NOT_IDENTIFIED")
    if (isinstance(expected_server_shift_seconds, bool) or
            not isinstance(expected_server_shift_seconds, int) or
            expected_server_shift_seconds == 0 or abs(expected_server_shift_seconds) > 86400):
        reasons.append("BROKER_DST_SHIFT_NOT_DOCUMENTED")
    if len(samples) != 2:
        reasons.append("BEFORE_AND_AFTER_DST_SAMPLES_REQUIRED")

    results = []
    by_phase = {sample.get("phase"): sample for sample in samples if isinstance(sample, dict)}
    if set(by_phase) != {"before_transition", "after_transition"}:
        reasons.append("DST_SAMPLE_PHASES_INVALID")

    for phase in ("before_transition", "after_transition"):
        sample = by_phase.get(phase)
        if not sample:
            continue
        try:
            trusted = _utc(sample.get("trustedUTC"))
            tick_ms = int(sample["tickEpochMilliseconds"])
            bar_seconds = int(sample["barEpochSeconds"])
            gmt_seconds = int(sample["timeGmtEpochSeconds"])
            server_label = dt.datetime.strptime(sample["timeCurrentServerLabel"], "%Y-%m-%d %H:%M:%S")
        except (KeyError, TypeError, ValueError, OverflowError):
            reasons.append(f"{phase.upper()}_SAMPLE_INVALID")
            continue
        if min(tick_ms, bar_seconds, gmt_seconds) < 0:
            reasons.append(f"{phase.upper()}_NEGATIVE_EPOCH")
            continue
        tick_skew = tick_ms / 1000 - trusted.timestamp()
        gmt_skew = gmt_seconds - trusted.timestamp()
        bar_age = trusted.timestamp() - bar_seconds
        expected_last_closed_bar = int(trusted.timestamp()) // 900 * 900 - 900
        if abs(tick_skew) > max_clock_skew_seconds:
            reasons.append(f"{phase.upper()}_TICK_EPOCH_DIFFERS_FROM_TRUSTED_UTC")
        if abs(gmt_skew) > max_clock_skew_seconds:
            reasons.append(f"{phase.upper()}_TIMEGMT_DIFFERS_FROM_TRUSTED_UTC")
        if (bar_seconds % 900 or
                bar_age < 0 or bar_age > max_bar_age_seconds or
                bar_seconds != expected_last_closed_bar):
            reasons.append(f"{phase.upper()}_M15_EPOCH_DOES_NOT_MATCH_TRUSTED_UTC_BAR")
        server_offset = (server_label - trusted.replace(tzinfo=None)).total_seconds()
        results.append({
            "phase": phase,
            "trustedUTC": trusted.isoformat().replace("+00:00", "Z"),
            "tickClockSkewSeconds": round(tick_skew, 3),
            "timeGMTClockSkewSeconds": round(gmt_skew, 3),
            "m15BarAgeSeconds": round(bar_age, 3),
            "expectedLastClosedM15EpochSeconds": expected_last_closed_bar,
            "barEpochMatchesTrustedUTC": bar_seconds == expected_last_closed_bar,
            "serverOffsetSecondsAtCapture": int(server_offset),
        })

    if len(results) == 2:
        before, after = results
        if before["trustedUTC"] >= after["trustedUTC"]:
            reasons.append("DST_SAMPLES_NOT_CHRONOLOGICAL")
        observed_shift = after["serverOffsetSecondsAtCapture"] - before["serverOffsetSecondsAtCapture"]
        if observed_shift != expected_server_shift_seconds:
            reasons.append("OBSERVED_SERVER_SHIFT_DIFFERS_FROM_DOCUMENTED_DST_SHIFT")
    else:
        observed_shift = None

    passed = not reasons
    return {
        "mode": "MT5_CLOCK_DIAGNOSTIC_ONLY",
        "status": "CLOCK_DIAGNOSTIC_PASSED_FOR_CAPTURED_DST_WINDOW" if passed else "CLOCK_BASIS_UNVERIFIED",
        "clockBasisVerified": passed,
        "trustedClockSource": trusted_clock_source.strip() if isinstance(trusted_clock_source, str) else "",
        "expectedServerShiftSeconds": expected_server_shift_seconds,
        "observedServerShiftSeconds": observed_shift,
        "samples": results,
        "blockingReasons": reasons,
        "signal": "WAIT",
        "executable": False,
        "researchEligible": False,
        "networkRequestsMade": 0,
        "disclaimer": "A passing result applies only to these captures and the declared broker DST shift. It does not authenticate symbol, market-data rights, history outside the sampled window, or profitability. This diagnostic never unlocks the importer or a signal engine."
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", action="append", nargs=3, metavar=("PHASE", "CSV", "TRUSTED_UTC"), required=True)
    parser.add_argument("--trusted-clock-source", required=True,
                        help="Name of independent UTC reference used for the captures")
    parser.add_argument("--expected-server-shift-seconds", type=int, required=True,
                        help="Broker-documented signed offset change across the sampled DST transition")
    parser.add_argument("--output", required=True, help="Local diagnostic JSON file")
    args = parser.parse_args()
    samples = [sample_from_csv(path, phase, trusted) for phase, path, trusted in args.sample]
    result = diagnose(samples, args.trusted_clock_source, args.expected_server_shift_seconds)
    pathlib.Path(args.output).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("status", "clockBasisVerified", "observedServerShiftSeconds", "blockingReasons", "signal", "executable")}))
    if not result["clockBasisVerified"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
