"""Private, offline BiQuote XAUUSD forward data vault — no network or trading.

Accept externally supplied, existing read-only BiQuote quote + three OHLC JSON
envelopes. This MODULE NEVER fetches, schedules, deploys, backfills, trades, or
enables access. Vault on a durable owner-only private Render coordinator disk;
NEVER commit actual data to this public GitHub repository.

Research boundary is fixed BEFORE forward collection begins:
2026-11-18T00:00:00Z. Historical MID candles may contain an initial BID
seed; simultaneous BID/ASK QUOTES are not historical BID/ASK OHLC.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import os
import pathlib
import re
import secrets
import stat
import sys

from biquote_offline_source_audit import FRAMES, _frame, _utc
from biquote_overlap_evidence import diagnose_biquote_overlap
from biquote_session_gap_audit import audit_closed_timestamp_reference

UTC = dt.timezone.utc
START = dt.datetime(2026, 11, 18, tzinfo=UTC)
FILE = "biquote-forward-private-v1.json"
MAX_SOURCE_BYTES = 2_500_000
MAX_VAULT_BYTES = 36_000_000
MAX_CANDLES_PER_FRAME = 45_000
MAX_QUOTE_SAMPLES = 10_000
APPROVAL_ENV = "GPP_BIQUOTE_PRIVATE_FORWARD_ARCHIVE"
APPROVAL = "APPROVED_READONLY_PRIVATE_NO_TRADING"
ALLOW_DIR_PREFIX = "/var/data/"
FRAMES_ORDER = ("M15", "H1", "H4")
SAFE = {
    "mode": "PRIVATE_FORWARD_BIQUOTE_CAPTURE_NOT_TRADING_ADMISSIBLE",
    "signal": "WAIT", "executable": False, "tradeEligible": False,
    "paperOrdersAllowed": False, "researchEligible": False,
    "providerRequestsMade": 0, "ordersSent": 0,
    "independentBrokerEntitlementVerified": False,
    "independentSessionCalendarVerified": False,
    "historicalBidAskOhlcAvailable": False,
    "priceBasis": "BIQUOTE_MID_POSSIBLE_INITIAL_BID_HISTORY_SEED",
    "startUTC": "2026-11-18T00:00:00Z",
}

def _fail(message):
    raise ValueError(message)

def _stamp(value):
    # Provider ticks may include 1–3 fractional milliseconds; closed
    # candle grid is separately validated by existing BiQuote _frame.
    if not isinstance(value, str) or not re.fullmatch(
        r"20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,3})?Z", value
    ):
        _fail("UTC_Z_REQUIRED")
    return _utc(value)

def _positive(v):
    return type(v) in (float, int) and math.isfinite(v) and v > 0

def _canonical(x):
    return json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

def _sha(payload):
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()

def _secure_dir(dirname, create=False):
    if not isinstance(dirname, (str, os.PathLike)):
        _fail("PRIVATE_DIR_REQUIRED")
    p = pathlib.Path(dirname)
    if not p.is_absolute() or str(p)=="/" or ".." in p.parts:
        _fail("PRIVATE_ABSOLUTE_PATH_REQUIRED")
    if create:
        p.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        st = p.lstat()
    except FileNotFoundError:
        return None
    if not stat.S_ISDIR(st.st_mode) or stat.S_ISLNK(st.st_mode) or st.st_mode & 0o077:
        _fail("VAULT_DIR_NOT_OWNER_ONLY")
    if hasattr(os, "getuid") and st.st_uid != os.getuid():
        _fail("VAULT_DIR_OWNER_MISMATCH")
    return p

def _secure_file(p):
    try:
        st = p.lstat()
    except FileNotFoundError:
        return False
    if not stat.S_ISREG(st.st_mode) or stat.S_ISLNK(st.st_mode) or st.st_mode & 0o077:
        _fail("VAULT_FILE_UNSAFE_PERMISSIONS_OR_SYMLINK")
    if hasattr(os, "getuid") and st.st_uid != os.getuid():
        _fail("VAULT_FILE_OWNER_MISMATCH")
    if st.st_size > MAX_VAULT_BYTES:
        _fail("VAULT_SIZE_EXCEEDED")
    return True

def _blank():
    return {
        "schema": 1, "source": "BIQUOTE_UNVERIFIED_UPSTREAM_MT5",
        "priceBasis": SAFE["priceBasis"], "startUTC": SAFE["startUTC"],
        "sessionVerified": False, "brokerRightsVerified": False,
        "closed": {tf: [] for tf in FRAMES_ORDER}, "quoteObservations": [],
        "lastImportedUTC": None,
    }

def load_vault(dirname):
    d = _secure_dir(dirname)
    if d is None:
        return _blank()
    p = d / FILE
    if not _secure_file(p):
        return _blank()
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(p, flags)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_mode & 0o077 or st.st_size > MAX_VAULT_BYTES:
            _fail("VAULT_FILE_UNSAFE_AFTER_OPEN")
        with os.fdopen(fd, "rb", closefd=False) as handle:
            raw = handle.read(MAX_VAULT_BYTES + 1)
    finally:
        os.close(fd)
    try:
        env = json.loads(raw)
    except (ValueError, UnicodeError):
        _fail("VAULT_UNREADABLE")
    if not isinstance(env, dict) or set(env) != {"payload", "sha256"} or \
       not isinstance(env["sha256"], str) or _sha(env["payload"]) != env["sha256"]:
        _fail("VAULT_TAMPER_OR_HASH_MISMATCH")
    v = env["payload"]
    if not isinstance(v, dict) or v.get("schema") != 1 or \
       v.get("startUTC") != SAFE["startUTC"] or \
       v.get("priceBasis") != SAFE["priceBasis"] or \
       v.get("brokerRightsVerified") is not False or \
       v.get("sessionVerified") is not False or \
       not isinstance(v.get("closed"), dict) or \
       set(v["closed"]) != set(FRAMES_ORDER) or \
       not isinstance(v.get("quoteObservations"), list):
        _fail("VAULT_PROVENANCE_INVALID")
    for tf in FRAMES_ORDER:
        rows = v["closed"][tf]
        if not isinstance(rows, list) or len(rows) > MAX_CANDLES_PER_FRAME:
            _fail("VAULT_HISTORY_COUNT_INVALID")
        if any(not isinstance(x, dict) or "openTime" not in x for x in rows):
            _fail("VAULT_HISTORY_SHAPE_INVALID")
        stamps = [_stamp(x["openTime"]) for x in rows]
        if stamps != sorted(set(stamps)) or any(x < START for x in stamps):
            _fail("VAULT_HISTORY_ORDER_INVALID")
    q = v["quoteObservations"]
    if len(q) > MAX_QUOTE_SAMPLES or any(not isinstance(x,dict) or "tickUTC" not in x for x in q):
        _fail("VAULT_QUOTE_INVALID")
    if [_stamp(x["tickUTC"]) for x in q] != sorted(set(_stamp(x["tickUTC"]) for x in q)):
        _fail("VAULT_QUOTE_ORDER_INVALID")
    return v

def _atomic_save(dirname, payload):
    d = _secure_dir(dirname, create=True)
    target = d / FILE
    _secure_file(target)
    body = (_canonical({"payload":payload,"sha256":_sha(payload)}) + "\n").encode()
    if len(body) > MAX_VAULT_BYTES:
        _fail("VAULT_STORAGE_BUDGET_REACHED")
    tmp = d / (FILE + ".tmp-" + secrets.token_hex(12))
    fd = None
    try:
        fd = os.open(tmp, os.O_CREAT | os.O_EXCL | os.O_WRONLY |
                     getattr(os,"O_NOFOLLOW",0), 0o600)
        with os.fdopen(fd,"wb",closefd=False) as handle:
            handle.write(body)
            handle.flush()
            os.fsync(fd)
        os.close(fd);fd=None
        os.replace(tmp,target)
        dirfd=os.open(d,os.O_RDONLY | getattr(os,"O_DIRECTORY",0))
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
    finally:
        if fd is not None:
            os.close(fd)
        try: tmp.unlink()
        except FileNotFoundError: pass

def ingest(dirname, sample, *, received_utc):
    """One already-received quote + M15/H1/H4 snapshot, NO network calls.

    Raises without writing on any malformed, stale, revised, out-of-order
    or mismatched record. Gaps are retained, never generated/backfilled.
    """
    received = _stamp(received_utc)
    if received < START:
        _fail("FORWARD_HOLDOUT_NOT_STARTED")
    if not isinstance(sample,dict) or set(sample) != {"source","quote","frames"} or \
       sample["source"] != "BiQuote":
        _fail("UNTRUSTED_SOURCE_ENVELOPE")
    quote, frames = sample["quote"], sample["frames"]
    if not isinstance(quote,dict) or quote.get("symbol") != "XAUUSD" or \
       quote.get("stale") is not False or quote.get("marketState") != "open" or \
       not _positive(quote.get("bid")) or not _positive(quote.get("ask")) or \
       quote["ask"] < quote["bid"]:
        _fail("QUOTE_NOT_VALID_FRESH_OPEN")
    qt=_stamp(quote.get("timestamp"))
    age = (received-qt).total_seconds()
    if age < 0 or age > 30:
        _fail("QUOTE_STALE_OR_FUTURE")
    spread=quote["ask"]-quote["bid"]
    if quote.get("mid") is not None and (
        not _positive(quote["mid"]) or abs(quote["mid"]-(quote["ask"]+quote["bid"])/2)>0.0001):
        _fail("MID_PARITY_FAILED")
    if quote.get("spread") is not None and (
        type(quote["spread"]) not in (int,float) or
        abs(quote["spread"]-spread)>0.0001):
        _fail("QUOTE_SPREAD_PARITY_FAILED")
    evidence=diagnose_biquote_overlap(frames,now=received)
    if evidence["error"] is not None:
        _fail("FRAME_VALIDATION_"+evidence["error"])
    if any(evidence["overlap"][tf]["fullyCoveredOHLCDisagree"]>0 for tf in ("H1","H4")):
        _fail("CROSS_FRAME_OHLC_MISMATCH")
    # Even an incomplete H4 must contain each observed M15 extreme and
    # its known opening/closing member. Partial coverage is NEVER silently
    # approved; this stricter invariant only rejects impossible source data.
    if any(evidence["overlap"][tf]["partialObservedOHLCBoundDisagreements"]>0
           for tf in ("H1","H4")):
        _fail("PARTIAL_CROSS_FRAME_OBSERVED_PRICE_BOUNDS_INVALID")
    for tf in FRAMES_ORDER:
        newest=evidence["frames"][tf]["newestClosedUTC"]
        if newest is None or \
           (received-_stamp(newest)).total_seconds()>FRAMES[tf][1]*2:
            _fail("CLOSED_HISTORY_STALE_"+tf)
    incoming={}
    for tf in FRAMES_ORDER:
        closed=_frame(frames[tf],FRAMES[tf][0],FRAMES[tf][1],received)
        incoming[tf]=[{"openTime":dt.datetime.fromtimestamp(t,UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                       **{k:closed[t][k] for k in ("open","high","low","close")}}
                      for t in sorted(closed) if dt.datetime.fromtimestamp(t,UTC)>=START]
    current=load_vault(dirname)
    amended=json.loads(_canonical(current))
    newly={}
    for tf in FRAMES_ORDER:
        existing=amended["closed"][tf]
        old={x["openTime"]:x for x in existing}
        last=existing[-1]["openTime"] if existing else None
        additions=[]
        for bar in incoming[tf]:
            t=bar["openTime"]
            if t in old:
                if old[t] != bar:
                    _fail("CLOSED_CANDLE_REVISED_"+tf)
            elif last is not None and t <= last:
                _fail("LATE_OR_OUT_OF_ORDER_BACKFILL_"+tf)
            else:
                additions.append(bar)
        if len(existing)+len(additions)>MAX_CANDLES_PER_FRAME:
            _fail("MAX_CANDLE_CAP_"+tf)
        amended["closed"][tf].extend(additions)
        newly[tf]=len(additions)
    if len(amended["quoteObservations"]) >= MAX_QUOTE_SAMPLES:
        _fail("QUOTE_OBSERVATION_CAP")
    quoted={"tickUTC":quote["timestamp"],
            "observedUTC":received_utc,
            "bid":quote["bid"],"ask":quote["ask"],
            "spread":round(spread,8)}
    oldquotes=amended["quoteObservations"]
    if oldquotes:
        last=oldquotes[-1]
        if quoted["tickUTC"]<last["tickUTC"]:
            _fail("OUT_OF_ORDER_TICK")
        if quoted["tickUTC"]==last["tickUTC"]:
            if (quoted["bid"],quoted["ask"]) != (last["bid"],last["ask"]):
                _fail("SAME_TICK_REVISED")
            quoted=None
    if quoted:
        oldquotes.append(quoted)
    amended["lastImportedUTC"]=received_utc
    changed=any(newly.values()) or bool(quoted)
    if changed:
        _atomic_save(dirname, amended)
    return {
        **SAFE, "status":"PRIVATE_FORWARD_CAPTURE_SAVED" if changed else "NO_NEW_BARS",
        "sampleSourceIndependentlyAuthenticated": False,
        "newClosedBars":newly,
        "totals":{tf:len(amended["closed"][tf]) for tf in FRAMES_ORDER},
        "spreadQuoteSamples":len(oldquotes),
        "crossFrameIncompleteM15": {
            tf:evidence["overlap"][tf]["internalM15ConstituentGaps"] for tf in ("H1","H4")
        },
        "sourceMarketDataPersistedToPrivateVault":changed,
        "rawDataReturnedToCaller":False,
        "candidateV3StrategyExecuted":False,
        "independentProfitabilityProven":False
    }

def _closed_coverage(rows, tf, last_imported):
    """No prices or raw quotes; session pauses remain UNCLASSIFIED."""
    width=FRAMES[tf][1]
    stamps=[_stamp(item["openTime"]) for item in rows]
    if not stamps:
        return {"closedBars":0, "firstClosedUTC":None, "lastClosedUTC":None,
                "latestContiguousBars":0, "unclassifiedGapPairs":0,
                "unclassifiedMissingSlots":0, "ageAtLastImportSeconds":None}
    missing=0
    pairs=0
    contiguous=1
    for before,after in zip(stamps,stamps[1:]):
        step=int((after-before).total_seconds())
        if step!=width:
            pairs+=1
            missing+=max(0,step//width-1)
            contiguous=1
        else:
            contiguous+=1
    last_end=stamps[-1]+dt.timedelta(seconds=width)
    observed=_stamp(last_imported) if last_imported else None
    age=round((observed-last_end).total_seconds(),3) if observed else None
    return {"closedBars":len(rows),
            "firstClosedUTC":(stamps[0]+dt.timedelta(seconds=width)).isoformat().replace("+00:00","Z"),
            "lastClosedUTC":last_end.isoformat().replace("+00:00","Z"),
            "latestContiguousBars":contiguous,
            "unclassifiedGapPairs":pairs,
            "unclassifiedMissingSlots":missing,
            "ageAtLastImportSeconds":age if age is not None and age>=0 else None}


def capture_freshness(last_imported_utc, quote_samples, *, now_utc=None):
    """Observation liveness from sealed metadata; NEVER source authorization.

    Only a stored quote receipt is eligible, not a recent candle timestamp,
    a public GET or Render's HTTP/health status. This never fetches, persists,
    opens an order, or treats a vendor pause as an approved market closure.
    """
    result = {
        "mode": "BIQUOTE_PRIVATE_CAPTURE_LIVENESS_DIAGNOSTIC_ONLY",
        "status": "NO_CAPTURE", "signal": "WAIT", "executable": False,
        "paperOrdersAllowed": False, "sourceQualified": False,
        "brokerCalendarVerified": False, "captureVerifiedByBroker": False,
        "asOfUTC": None, "ageSeconds": None,
    }
    current = dt.datetime.now(UTC) if now_utc is None else now_utc
    if (not isinstance(current, dt.datetime) or current.tzinfo is None
            or current.utcoffset() != dt.timedelta(0)):
        return {**result, "status": "UTC_CLOCK_UNVERIFIED"}
    asof = current.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    if type(quote_samples) is not int or not 0 <= quote_samples <= MAX_QUOTE_SAMPLES:
        return {**result, "status": "CAPTURE_COUNT_INVALID", "asOfUTC": asof}
    if quote_samples == 0 or last_imported_utc is None:
        return {**result, "asOfUTC": asof}
    try:
        received = _stamp(last_imported_utc)
    except (TypeError, ValueError):
        return {**result, "status": "CAPTURE_TIMESTAMP_INVALID", "asOfUTC": asof}
    age = (current-received).total_seconds()
    if not math.isfinite(age) or age < 0:
        return {**result, "status": "FUTURE_CAPTURE_OR_CLOCK_SKEW",
                "asOfUTC": asof}
    return {**result,
            "status": "RECENT_UNVERIFIED" if age <= 300 else
                      "STALE_OVER_5_MINUTES",
            "ageSeconds": min(int(age), 31536000),
            "asOfUTC": asof}


def closed_frame_freshness(coverage, *, now_utc=None):
    """Price-free age of last truly sealed M15/H1/H4 closes vs UTC *now*.

    A healthy quote does not prove the candle endpoints are updating.
    Thresholds are diagnostic 2x each timeframe, NOT broker session hours.
    Do not infer vendor rights, gap exemptions or signal eligibility here.
    """
    output={
        "mode":"BIQUOTE_PRIVATE_CLOSED_FRAME_AGE_DIAGNOSTIC_ONLY",
        "status":"UNAVAILABLE","signal":"WAIT","executable":False,
        "sourceQualified":False,"paperOrdersAllowed":False,
        "brokerCalendarVerified":False,"gapBridgingAllowed":False,
        "asOfUTC":None,"frames":{}
    }
    current=dt.datetime.now(UTC) if now_utc is None else now_utc
    if (not isinstance(current,dt.datetime) or current.tzinfo is None
            or current.utcoffset()!=dt.timedelta(0)):
        return output
    asof=current.isoformat(timespec="milliseconds").replace("+00:00","Z")
    if not isinstance(coverage,dict) or set(coverage)!=set(FRAMES_ORDER):
        return {**output,"asOfUTC":asof}
    frames={}
    for tf in FRAMES_ORDER:
        width=FRAMES[tf][1]
        item=coverage[tf]
        if not isinstance(item,dict):
            return {**output,"asOfUTC":asof}
        n=item.get("closedBars")
        close=item.get("lastClosedUTC")
        if type(n) is not int or not 0<=n<=MAX_CANDLES_PER_FRAME:
            return {**output,"asOfUTC":asof}
        if n==0:
            if close is not None:
                return {**output,"asOfUTC":asof}
            frames[tf]={"status":"NO_CLOSED_BAR","ageSeconds":None,
                        "thresholdSeconds":2*width}
            continue
        try:
            recent_close=_stamp(close)
        except (TypeError,ValueError):
            return {**output,"asOfUTC":asof}
        elapsed=(current-recent_close).total_seconds()
        if not math.isfinite(elapsed):
            return {**output,"asOfUTC":asof}
        if elapsed<0:
            frames[tf]={"status":"FUTURE_CLOSE_OR_CLOCK_SKEW","ageSeconds":None,
                        "thresholdSeconds":2*width}
        else:
            frames[tf]={
                "status":"RECENT_UNVERIFIED" if elapsed<=2*width else
                         "CANDLE_STALE_OVER_TWO_FRAMES",
                "ageSeconds":min(int(elapsed),31536000),
                "thresholdSeconds":2*width,
            }
    return {**output,"status":"AGE_COUNTS_ONLY_UNVERIFIED","asOfUTC":asof,
            "frames":frames}


def inspect_metadata(dirname, *, now_utc=None):
    """Private counts, closed-bar continuity and last arrival; NO prices."""
    v=load_vault(dirname)
    coverage={tf:_closed_coverage(v["closed"][tf],tf,v["lastImportedUTC"])
              for tf in FRAMES_ORDER}
    # Only aggregate closed timestamp gaps, never a broker calendar or prices.
    # Derive the private, read-only vendor pause hypothesis from this SAME
    # checksum-protected archive already loaded above. Fail closed on any
    # inconsistent metadata; this can never promote source or trading rights.
    gap_reference=audit_closed_timestamp_reference({
        tf:[row["openTime"] for row in v["closed"][tf]] for tf in FRAMES_ORDER})
    if gap_reference["status"]!="REFERENCE_ONLY_NOT_BROKER_VERIFIED":
        _fail("SEALED_GAP_REFERENCE_NOT_RELIABLE")
    for tf in FRAMES_ORDER:
        if (gap_reference["frames"][tf]["persistedClosed"]!=len(v["closed"][tf])
            or gap_reference["frames"][tf]["unclassifiedMissingSlots"]
                !=coverage[tf]["unclassifiedMissingSlots"]
            or gap_reference["frames"][tf]["gapPairs"]
                !=coverage[tf]["unclassifiedGapPairs"]):
            _fail("SEALED_GAP_REFERENCE_COUNTER_MISMATCH")
    return {**SAFE,
            "status":"PRIVATE_FORWARD_VAULT_METADATA_ONLY",
            "counts":{tf:len(v["closed"][tf]) for tf in FRAMES_ORDER},
            "quoteSamples":len(v["quoteObservations"]),
            "lastImportedUTC":v["lastImportedUTC"],
            "captureFreshness":capture_freshness(
                v["lastImportedUTC"], len(v["quoteObservations"]), now_utc=now_utc),
            "forwardCoverage":coverage,
            "closedFrameFreshness":closed_frame_freshness(
                coverage,now_utc=now_utc),
            "gapReference":gap_reference,
            "coverageClassification":"GAPS_UNCLASSIFIED_WITHOUT_INDEPENDENT_BROKER_CALENDAR",
            "researchCandidate":"NONE",
            "tradeSignalReady":False,
            "independentProfitabilityProven":False,
            "noTradingAdmission":True}

def main():
    # Use a long-lived private disk; no file/stdout with raw provider quotes.
    # An operator explicitly pipes an already authorized received JSON
    # snapshot to stdin. This program NEVER fetches or schedules anything.
    if len(sys.argv)!=3 or sys.argv[1] not in ("ingest","status"):
        raise SystemExit("Usage: python biquote_private_forward_vault.py ingest|status /var/data/<private-vault>")
    mode, directory=sys.argv[1:]
    if not pathlib.Path(directory).is_absolute() or \
       not directory.startswith(ALLOW_DIR_PREFIX):
        raise SystemExit("BLOCKED: private persistent /var/data path required")
    if os.environ.get(APPROVAL_ENV)!=APPROVAL:
        raise SystemExit("BLOCKED: explicit private read-only archival approval required")
    if mode=="status":
        result=inspect_metadata(directory)
    else:
        raw=sys.stdin.buffer.read(MAX_SOURCE_BYTES+1)
        if len(raw)>MAX_SOURCE_BYTES:
            raise SystemExit("BLOCKED: input too large")
        try: data=json.loads(raw)
        except (ValueError,UnicodeError):
            raise SystemExit("BLOCKED: invalid JSON")
        result=ingest(directory,data,received_utc=dt.datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"))
    print(_canonical(result))

if __name__=="__main__":
    main()
