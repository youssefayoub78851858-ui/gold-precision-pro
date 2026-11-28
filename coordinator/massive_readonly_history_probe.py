"""Bounded, opt-in Massive historical quote sample. No automatic startup.

Read-only GET of one page, no cursor follow, redirects, secrets in URLs,
storage, order access or research admission. Not a continuous collector.
Operator must independently approve entitlement, rights and request cost.
"""
import datetime as dt
import json
import urllib.request
import urllib.error
from urllib.parse import urlencode
from massive_bbo_history_adapter import _decode_quote, _utc

BASE = "https://api.massive.com/v3/quotes/C:XAUUSD"
MAX_BYTES = 2_000_000
MAX_ROWS = 1000

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def _get(request):
    with urllib.request.build_opener(NoRedirect()).open(request, timeout=10) as response:
        return response.read(MAX_BYTES+1)

def _ns(t):
    elapsed = t - dt.datetime(1970,1,1,tzinfo=dt.timezone.utc)
    return ((elapsed.days*86400+elapsed.seconds)*1000000+elapsed.microseconds)*1000

def probe_history(*, authorized=False, credential=None, start_utc=None,
                  end_utc=None, now_utc=None, limit=MAX_ROWS, transport=None):
    report = dict(status="NOT_AUTHORIZED", signal="WAIT", executable=False,
                  paperOrdersAllowed=False, liveOrdersAllowed=False,
                  historyCoverageVerified=False, realDataQualificationProven=False,
                  providerRequestAttempts=0, quoteCount=0, truncated=None,
                  maxObservedGapSeconds=None)
    if authorized is not True:
        return report
    def finish(status, **fields):
        return {**report, "status":status, **fields}
    try:
        start,end,now=map(_utc,(start_utc,end_utc,now_utc))
        if not (start < end <= now and end-start <= dt.timedelta(days=1)):
            raise ValueError("Invalid window")
        if (not isinstance(credential,str) or not credential or len(credential)>4096
                or any(not 33<=ord(c)<=126 for c in credential)
                or type(limit) is not int or not 1<=limit<=MAX_ROWS
                or (transport is not None and not callable(transport))):
            raise ValueError("Invalid configuration")
        begin, cutoff = _ns(start), _ns(end)
        url = BASE + "?" + urlencode({"timestamp.gte":begin,"timestamp.lt":cutoff,
                                      "sort":"timestamp","order":"asc","limit":limit})
        req=urllib.request.Request(url,headers={"Authorization":"Bearer "+credential,
                                                "Accept":"application/json"},method="GET")
    except (ValueError,TypeError,OverflowError):
        return finish("INVALID_CONFIGURATION")
    credential=None
    report["providerRequestAttempts"]=1
    try:
        raw=(transport or _get)(req)
        if not isinstance(raw,bytes) or len(raw)>MAX_BYTES:
            return finish("INVALID_RESPONSE_SIZE")
        body=json.loads(raw)
        if not isinstance(body,dict) or body.get("status")!="OK":
            return finish("PROVIDER_RESPONSE_REJECTED")
        rows=body.get("results",[])
        if not isinstance(rows,list) or len(rows)>limit:
            return finish("INVALID_QUOTE_COUNT")
        if "next_url" in body and not isinstance(body["next_url"],str):
            return finish("INVALID_CURSOR_SHAPE")
        truncated=bool(body.get("next_url")) or len(rows)==limit
        if not rows:
            return finish("NO_QUOTES_OBSERVED",truncated=truncated)
        quotes=[_decode_quote(row,cutoff) for row in rows]
        times=[q["ns"] for q in quotes]
        if min(times)<begin or any(b<a for a,b in zip(times,times[1:])):
            return finish("QUOTE_WINDOW_OR_ORDER_REJECTED")
        gap=max((b-a for a,b in zip(times,times[1:])),default=0)/1e9
        return finish("HISTORICAL_SAMPLE_OBSERVED_NOT_QUALIFIED",
                      quoteCount=len(quotes),truncated=truncated,
                      maxObservedGapSeconds=gap)
    except urllib.error.HTTPError as error:
        return finish("ENTITLEMENT_REFUSED" if error.code in (401,403) else
                      "RATE_LIMITED" if error.code==429 else "HTTP_REJECTED")
    except Exception:
        return finish("HISTORICAL_SAMPLE_FAILED")
