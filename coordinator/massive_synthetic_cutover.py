"""Synthetic REST-to-stream cutover rehearsal. No real source admission.

Compare independently generated overlapping closed bars, then count the
continuous synthetic union. Never publish prices, merge real feeds, or
treat overlap as evidence of market entitlement/session coverage.
"""
import datetime as dt
import math
from massive_history_stream_parity import canonical_utc_stamp, compare_synthetic_history_and_stream
from massive_bbo_history_adapter import _aggregate

WIDTH=dt.timedelta(minutes=15)
FAMILIES=(("bidFrames","bidFrames"),("askFrames","askFrames"),("midFrames","frames"))
def inspect_cutover(rest, stream):
    result=dict(status="BLOCKED",reason="INVALID_SYNTHETIC_INPUT",
                signal="WAIT",executable=False,paperOrdersAllowed=False,
                realDataQualificationProven=False,historyMayMergeWithStream=False,
                providerRequestsMade=0,overlapM15=0,syntheticUnionM15=0,
                syntheticUnionH1=0,syntheticUnionH4=0)
    def fail(reason):
        return {**result,"reason":reason}
    try:
        # Existing parity contract validates source flags, even though
        # different windows are expected to fail whole-window comparison.
        compare_synthetic_history_and_stream(rest,stream)
        def checked(dataset,key):
            family=dataset[key]
            bars=family["M15"]
            if not 1<=len(bars)<=2048:
                raise ValueError()
            output={}
            for row in bars:
                stamp=canonical_utc_stamp(row["openTime"])
                if stamp is None or stamp.timestamp()%900 or stamp in output:
                    raise ValueError()
                values=[row[k] for k in ("open","high","low","close")]
                if (any(type(v) not in (int,float) or not math.isfinite(v) or v<=0 for v in values)
                        or not values[2]<=min(values[0],values[3])<=max(values[0],values[3])<=values[1]):
                    raise ValueError()
                if output and stamp!=next(reversed(output))+WIDTH:
                    raise ValueError()
                output[stamp]={**row,"openTime":stamp.isoformat().replace("+00:00","Z")}
            for tf,n in (("H1",4),("H4",16)):
                parents=[{**x,"openTime":canonical_utc_stamp(x["openTime"]).isoformat().replace("+00:00","Z")} for x in family[tf]]
                if parents!=_aggregate(list(output.values()),n):
                    raise ValueError()
            return output
        historical=[checked(rest,a) for a,b in FAMILIES]
        streamed=[checked(stream,b) for a,b in FAMILIES]
        for group in (historical,streamed):
            if any(list(x)!=list(group[0]) for x in group[1:]):
                return fail("PRICE_BASIS_TIME_MISMATCH")
            for stamp in group[0]:
                bid,ask,mid=[x[stamp] for x in group]
                if any(bid[k]>ask[k] or not bid[k]<=mid[k]<=ask[k] for k in ("open","high","low","close")):
                    return fail("PRICE_BASIS_GEOMETRY_MISMATCH")
        old,new=historical[0],streamed[0]
        common=sorted(old.keys() & new.keys())
        if len(common)<16 or not (min(old)<min(new)<=max(old)<max(new)):
            return fail("INSUFFICIENT_OVERLAP_OR_NO_FORWARD_EXTENSION")
        for left,right in zip(historical,streamed):
            for stamp in common:
                if any(not math.isclose(left[stamp][k],right[stamp][k],rel_tol=1e-12,abs_tol=1e-8)
                       for k in ("open","high","low","close")):
                    return fail("OVERLAP_PRICE_MISMATCH")
        union=sorted(old.keys()|new.keys())
        if any(b-a!=WIDTH for a,b in zip(union,union[1:])):
            return fail("CUTOVER_GAP")
        # Count only; never export stitched prices into research.
        rows=[old[t] if t in old else new[t] for t in union]
        return {**result,"status":"SYNTHETIC_CUTOVER_REHEARSED",
                "reason":"NO_REAL_SOURCE_QUALIFICATION",
                "overlapM15":len(common),"syntheticUnionM15":len(union),
                "syntheticUnionH1":len(_aggregate(rows,4)),
                "syntheticUnionH4":len(_aggregate(rows,16))}
    except (ValueError,TypeError,KeyError,AttributeError,OverflowError):
        return result
