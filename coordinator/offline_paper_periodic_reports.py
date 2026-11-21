"""Read-only synthetic journal reports; not a live prediction tracker.

The same audited net-cost arithmetic is used for cumulative, UTC-day,
UTC-week, completed 5-closed-trade batches, and a first-100-trade checkpoint.
No BUY/SELL, provider access, trading, real broker quotes or network.
Closing five paper trades is NOT five correct M15 forecasts; prediction
accuracy remains unavailable without separately logged, timestamped forecasts.
"""
from __future__ import annotations

import datetime as dt

from offline_paper_outcome_journal import (
    MODE as JOURNAL_MODE, OfflineJournal, local_audit, utc,
)

MODE = "GOLD_OFFLINE_SYNTHETIC_PAPER_REPORTS_V1"


def _report(trades, freeze, as_of):
    result = local_audit(trades, freeze, as_of)
    if (result.get("signal") != "WAIT"
            or result.get("executable") is not False
            or result.get("paperOrdersAllowed") is not False
            or result.get("liveOrdersAllowed") is not False
            or result.get("sourceRightsVerified") is not False
            or result.get("independentHoldoutValidated") is not False
            or result.get("closedTrades") != len(trades)
            or result.get("status") not in (
                "NO_CLOSED_PAPER_TRADES",
                "UNATTESTED_PAPER_ARITHMETIC_ONLY",
            )):
        raise ValueError("Invalid offline cost/chronology report")
    stats = result.get("statistics")
    if trades and not isinstance(stats, dict):
        raise ValueError("Missing paper arithmetic")
    if not trades and stats is not None:
        raise ValueError("Invented outcome without trades")
    stress = (stats or {}).get("modeledCostDoubleStress") or {}
    return {
        "closedTrades": len(trades),
        "netModeledUsd": (stats or {}).get("totalGrossMinusModeledCostsUsd"),
        "modeledCostsUsd": (stats or {}).get("modeledCostsUsd"),
        "netDoubleCostStressUsd": stress.get("netUsd"),
        "averageNetR": (stats or {}).get("averageNetR"),
        "winRate": (stats or {}).get("winRate"),
        "maxClosedDrawdownUsd": (stats or {}).get("maxRealizedDrawdownUsd"),
        "profitFactor": (stats or {}).get("profitFactor"),
        "outcomeStatus": result["status"],
        "independentlyValidated": False,
    }


def _week(stamp):
    day = utc(stamp).date()
    monday = day - dt.timedelta(days=day.weekday())
    return monday.isoformat()


def make_report(journal: OfflineJournal):
    if not isinstance(journal, OfflineJournal):
        raise ValueError("Only a verified isolated local journal is accepted")
    events, head = journal.verify()
    all_closes = [e for e in events if e["kind"] == "PAPER_CLOSED"]
    trades = [e["trade"] for e in all_closes]
    # A fixed as-of at the recorded observation watermark, not wall clock
    # (which would make old tests appear freshly observed).
    as_of = (events[-1]["observedUTC"] if events else
             (utc(journal.freeze_utc) + dt.timedelta(seconds=1))
             .isoformat().replace("+00:00", "Z"))

    days = {}
    weeks = {}
    for e in events:
        day = utc(e["observedUTC"]).date().isoformat()
        for group, key in ((days, day), (weeks, _week(e["observedUTC"]))):
            bucket = group.setdefault(key, {"events": 0, "wait": 0,
                                            "sourceBlocked": 0, "closes": []})
            bucket["events"] += 1
            bucket["wait"] += e["kind"] == "WAIT"
            bucket["sourceBlocked"] += e["kind"] == "SOURCE_BLOCKED"
            if e["kind"] == "PAPER_CLOSED":
                bucket["closes"].append(e["trade"])

    def grouped(buckets, period):
        return [{
            "period": period, "utcStart": key,
            "recordedEvents": value["events"],
            "waitEvents": value["wait"],
            "blockedSourceEvents": value["sourceBlocked"],
            **_report(value["closes"], journal.freeze_utc, as_of),
        } for key, value in sorted(buckets.items())]

    complete_fives = [
        {"closedTradeRange": [i + 1, i + 5],
         **_report(trades[i:i + 5], journal.freeze_utc, as_of)}
        for i in range(0, len(trades) // 5 * 5, 5)
    ]
    # 100-trade checkpoint is CLOSED PAPER outcomes only. Do not call it
    # M15-candle prediction accuracy or independent holdout performance.
    first_hundred = (_report(trades[:100], journal.freeze_utc, as_of)
                     if len(trades) >= 100 else None)
    result = {
        "mode": MODE,
        "status": "OFFLINE_SYNTHETIC_DESCRIPTIVE_ONLY",
        "origin": JOURNAL_MODE,
        "observationAsOfUTC": as_of,
        "journalRows": len(events),
        "journalDigest": head,
        "cumulative": _report(trades, journal.freeze_utc, as_of),
        "dailyUTC": grouped(days, "UTC_DAY"),
        "weeklyUTC": grouped(weeks, "UTC_WEEK_MONDAY"),
        "completedFiveTradeBatches": complete_fives,
        "partialFiveTradeBatchCount": len(trades) % 5,
        "firstHundredClosedTradeCheckpoint": first_hundred,
        "unverifiedNextM15ForecastAccuracy": None,
        "independentHoldoutValidated": False,
        "realMarketDataConnected": False,
        "brokerTransactionCostsVerified": False,
        "statisticallyValidated": False,
        "paperOrderExecutionEnabled": False,
        "liveOrderExecutionEnabled": False,
        "providerRequestsMade": 0,
        "brokerOrdersSent": 0,
        "paperOrdersSent": 0,
        "signal": "WAIT",
        "executable": False,
        "warning": "Only synthetic outcomes already in local SQLite; no broker returns, prediction-accuracy proof or trade authorization.",
    }
    return result
