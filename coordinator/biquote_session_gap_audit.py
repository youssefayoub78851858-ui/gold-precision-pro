"""Public read-only *hypothesis* comparison of BiQuote missing bar times.

This is NOT a BiQuote/MT5 broker calendar. Compare gaps with the widely
reported NOV-2026 XAUUSD reference: daily 22:00-23:00 UTC pause and
Friday 22:00 through Sunday 23:00 UTC weekend. Broker feed/holiday hours
may vary; never accept these labels as proof or bridge a candle.
No HTTP, raw OHLC, orders, costs, schedule activation or credentials.
"""
from __future__ import annotations
import datetime as dt

UTC=dt.timezone.utc
WIDTHS={"M15":900,"H1":3600,"H4":14400}
START=dt.datetime(2026,11,1,tzinfo=UTC)
END=dt.datetime(2027,3,14,tzinfo=UTC)
MAX_MISSING=1100

def reference_window_for_missing_slot(open_utc:dt.datetime, width_seconds:int):
    """Possible generic market pause ONLY if entire missing candle is in
    reference closed-time; reference is not the underlying MT5 broker."""
    if open_utc < START or open_utc+dt.timedelta(seconds=width_seconds)>END:
        return None
    slot_end=open_utc+dt.timedelta(seconds=width_seconds)
    t=open_utc
    # 15-min pieces cover any H1/H4 candidate and keep classification strict
    while t<slot_end:
        weekday=t.weekday() # Mon=0 Fri=4 Sat=5 Sun=6
        hour=t.hour
        weekend=(weekday==4 and hour>=22 or weekday==5 or
                 weekday==6 and hour<23)
        daily=(weekday in (0,1,2,3) and hour==22)
        if not (weekend or daily):
            return False
        t+=dt.timedelta(minutes=15)
    return True

def audit_gap_times(frame_envelopes):
    result={"status":"REFERENCE_ONLY_NOT_BROKER_VERIFIED",
            "signal":"WAIT","executable":False,
            "sessionCalendarIndependentlyVerified":False,
            "brokerScheduleVerified":False,"referenceWindowUTC":"2026-11-01..2027-03-14",
            "frameGaps":{},"error":None}
    if not isinstance(frame_envelopes,dict) or set(frame_envelopes)!=set(WIDTHS):
        result["error"]="THREE_FRAMES_REQUIRED"
        return result
    try:
        for tf,seconds in WIDTHS.items():
            bars=frame_envelopes[tf]["bars"]
            if not isinstance(bars,list) or len(bars)<2 or len(bars)>1000:
                raise ValueError("INVALID_BARS_COUNT")
            dates=[]
            for row in bars:
                if not isinstance(row,dict) or not isinstance(row.get("isOpen"),bool):
                    raise ValueError("INVALID_CANDLE")
                value=row["openTime"]
                if not isinstance(value,str) or not value.endswith("Z"):
                    raise ValueError("NON_UTC_CANDLE_TIME")
                t=dt.datetime.fromisoformat(value.replace("Z","+00:00"))
                if not row["isOpen"]:
                    dates.append(t)
            dates=sorted(dates)
            if len(set(dates))!=len(dates):
                raise ValueError("DUPLICATED_CANDLE")
            expected=dt.timedelta(seconds=seconds)
            gaps=[]
            missing_total=0
            for before,after in zip(dates,dates[1:]):
                delta=(after-before).total_seconds()
                if delta%seconds!=0:
                    raise ValueError("MISALIGNED_CANDLE_GAP")
                missing=int(delta//seconds)-1
                if missing==0:continue
                missing_total+=missing
                covered=0
                outside=0
                unknown=0
                if missing>MAX_MISSING:
                    gap_type="TOO_LARGE_TO_CLASSIFY"
                else:
                    for i in range(1,missing+1):
                        outcome=reference_window_for_missing_slot(before+expected*i,seconds)
                        if outcome is True:covered+=1
                        elif outcome is False:outside+=1
                        else:unknown+=1
                    gap_type=("REFERENCE_PAUSE_CANDIDATE_NOT_VERIFIED"
                              if covered==missing else
                              "UNEXPLAINED_IN_REFERENCE_TRADING_TIME"
                              if outside else
                              "OUTSIDE_REFERENCE_DATE_RANGE")
                if len(gaps)<14:
                    gaps.append({
                      "previousBarOpenUTC":before.isoformat().replace("+00:00","Z"),
                      "nextBarOpenUTC":after.isoformat().replace("+00:00","Z"),
                      "missingCandleCount":missing,
                      "referencePauseSlots":covered,
                      "referenceTradingTimeMissingSlots":outside,
                      "unknownReferenceSlots":unknown,
                      "classification":gap_type
                    })
            result["frameGaps"][tf]={
                "closedBars":len(dates),"gapCount":sum(
                    (b-a).total_seconds()>seconds for a,b in zip(dates,dates[1:])),
                "missingCandleSlots":missing_total,
                "firstGapsUTC":gaps,
                "completeHistoryProven":False
            }
    except (ValueError,TypeError,KeyError,OverflowError) as exc:
        result["error"]=str(exc)
        result["frameGaps"]={}
    return result


def audit_closed_timestamp_reference(frames):
    """Safe aggregate of *private closed-bar timestamps*, not broker certification.

    Input is timestamps only. No prices, individual times, market recommendations,
    session whitelist, file I/O or network requests ever leave this function.
    Vendor-reference pause candidates ALWAYS remain unclassified for admission.
    """
    safe = {
        "mode": "BIQUOTE_PRIVATE_REFERENCE_GAP_COUNTS_ONLY",
        "status": "UNAVAILABLE",
        "signal": "WAIT", "executable": False, "researchEligible": False,
        "paperOrdersAllowed": False, "liveOrdersAllowed": False,
        "independentBrokerCalendarVerified": False,
        "sourceRightsVerified": False,
        "allGapsRemainUnclassified": True,
        "frames": {},
    }
    if not isinstance(frames, dict) or set(frames) != set(WIDTHS):
        return {**safe, "reasonCode": "THREE_FRAMES_REQUIRED"}
    try:
        summaries = {}
        for tf, width in WIDTHS.items():
            values = frames[tf]
            if not isinstance(values, list) or len(values) > 45000:
                raise ValueError("CLOSED_TIMESTAMP_COUNT_INVALID")
            timestamps = []
            for value in values:
                if (not isinstance(value, str) or not value.endswith("Z")
                        or not value.startswith("20")
                        or len(value) > 28):
                    raise ValueError("CLOSED_TIMESTAMP_FORMAT_INVALID")
                try:
                    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError:
                    raise ValueError("CLOSED_TIMESTAMP_FORMAT_INVALID") from None
                if (parsed.utcoffset() != dt.timedelta(0) or
                        parsed.microsecond or int(parsed.timestamp()) % width != 0):
                    raise ValueError("CLOSED_TIMESTAMP_UTC_GRID_INVALID")
                timestamps.append(parsed)
            if timestamps != sorted(set(timestamps)):
                raise ValueError("CLOSED_TIMESTAMP_DUPLICATE_OR_REORDERED")
            missing = pause = outside = unknown = pairs = 0
            for before, after in zip(timestamps, timestamps[1:]):
                count = int((after-before).total_seconds() // width) - 1
                if count < 0:
                    raise ValueError("CLOSED_TIMESTAMP_SEQUENCE_INVALID")
                if count == 0:
                    continue
                pairs += 1
                missing += count
                # Cap diagnostics, not persisted data; large gaps stay UNKNOWN.
                if count > MAX_MISSING:
                    unknown += count
                    continue
                for index in range(1, count+1):
                    candidate = reference_window_for_missing_slot(
                        before + dt.timedelta(seconds=width*index), width)
                    if candidate is True:
                        pause += 1
                    elif candidate is False:
                        outside += 1
                    else:
                        unknown += 1
            summaries[tf] = {
                "persistedClosed": len(timestamps),
                "gapPairs": pairs,
                "unclassifiedMissingSlots": missing,
                "vendorPauseCandidateSlotsNotVerified": pause,
                "outsideVendorReferenceSlots": outside,
                "unknownReferenceSlots": unknown,
                "comparisonHasAtLeastTwoBars": len(timestamps) >= 2,
            }
        return {**safe, "status": "REFERENCE_ONLY_NOT_BROKER_VERIFIED",
                "reasonCode": "UPSTREAM_BROKER_SESSION_AND_RIGHTS_UNVERIFIED",
                "frames": summaries}
    except (ValueError, TypeError, OverflowError):
        return {**safe, "reasonCode": "PRIVATE_CLOSED_TIMESTAMPS_INVALID"}
