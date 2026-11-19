"""Offline local sealed-vault -> frozen V3 chronological research counter.

Never calls a market provider or opens a paper account. Reads one already
SHA-checked private archive, supplies OHLC over local Node stdin only, and
emits count-only WAIT metadata. Not a point-in-time holdout; schema v1
has no per-candle first-availability receipts or executable spread history.
"""
from __future__ import annotations
import json
import os
import pathlib
import subprocess
from biquote_private_forward_vault import load_vault, inspect_vault_metadata, FRAMES_ORDER

NODE=pathlib.Path(__file__).with_name("biquote_v3_chronological_replay.js")
BASE={
    "mode":"BIQUOTE_V3_PRIVATE_CHRONOLOGICAL_REPLAY_COUNTS_ONLY",
    "status":"BLOCKED","signal":"WAIT","executable":False,
    "paperOrdersAllowed":False,"liveOrdersAllowed":False,
    "sourceRequestsMade":0,"brokerOrdersSent":0,
    "sourceRightsVerified":False,"brokerSessionCalendarVerified":False,
    "firstAvailablePerCandleVerified":False,
    "costAdjustedPnL":None,"netExpectancy":None,"winRate":None,
    "tradingApprovalGranted":False,
}

def inspect_private_vault(dirname, *, runner=None):
    result={**BASE,"reason":"PRIVATE_ARCHIVE_OR_OFFLINE_ENGINE_UNAVAILABLE",
            "closedCounts":{tf:0 for tf in FRAMES_ORDER},
            "retrospectiveDecisionCount":0,
            "technicalWatchCounts":{"BUY":0,"SELL":0,"NONE":0}}
    try:
        sealed=load_vault(dirname)
        meta=inspect_vault_metadata(sealed)
        if (meta.get("status")!="PRIVATE_FORWARD_VAULT_METADATA_ONLY" or
            meta.get("signal")!="WAIT" or
            meta.get("executable") is not False or
            meta.get("noTradingAdmission") is not True or
            meta.get("paperOrdersAllowed") is not False or
            sealed.get("source")!="BIQUOTE_UNVERIFIED_UPSTREAM_MT5" or
            sealed.get("brokerRightsVerified") is not False or
            sealed.get("sessionVerified") is not False):
            return result
        counts=meta["counts"]
        packet={"dataOrigin":"BIQUOTE_ARCHIVED_UNVERIFIED_NO_PAPER","frames":{}}
        for tf in FRAMES_ORDER:
            packet["frames"][tf]=[
                {"datetime":b["openTime"],"open":b["open"],"high":b["high"],
                 "low":b["low"],"close":b["close"]}
                for b in sealed["closed"][tf]]
        if runner is None:
            raw=subprocess.run(
                ["node",str(NODE)],input=json.dumps(packet,allow_nan=False),
                text=True,capture_output=True,check=True,timeout=20).stdout
        else:
            raw=runner(packet)
        if not isinstance(raw,str) or len(raw)>6400:
            return result
        out=json.loads(raw)
        watches=out.get("technicalWatchCounts")
        count=out.get("retrospectiveDecisionCount")
        stored=out.get("storedClosedCounts")
        if (out.get("mode")!="BIQUOTE_V3_CHRONOLOGICAL_RECONSTRUCTION_ONLY"
            or out.get("signal")!="WAIT" or out.get("executable") is not False
            or out.get("paperOrdersAllowed") is not False
            or out.get("liveOrdersAllowed") is not False
            or out.get("sourceRightsVerified") is not False
            or out.get("brokerCalendarVerified") is not False
            or out.get("individualCandleFirstAvailableUTCVerified") is not False
            or out.get("executionBidAskHistoryVerified") is not False
            or out.get("brokerCostsVerified") is not False
            or out.get("independentHoldoutPerformanceProven") is not False
            or out.get("hypotheticalNetPnL") is not None
            or out.get("netExpectancy") is not None
            or out.get("winRate") is not None
            or out.get("replayOnlyNotPointInTime") is not True
            or out.get("noFutureCandlesUsed") is not True
            or out.get("providerRequestsMade")!=0
            or out.get("brokerOrdersSent")!=0
            or out.get("status") not in (
                "BLOCKED","RETROSPECTIVE_WATCH_COUNTS_ONLY")
            or not isinstance(stored,dict)
            or set(stored)!=set(FRAMES_ORDER)
            or any(type(stored[tf]) is not int or stored[tf]!=counts[tf]
                for tf in FRAMES_ORDER)
            or not isinstance(watches,dict)
            or set(watches)!={"BUY","SELL","NONE"}
            or any(type(watches[k]) is not int or not 0<=watches[k]<=256
                   for k in watches)
            or type(count) is not int or not 0<=count<=256
            or sum(watches.values())!=count
            or (out["status"]=="BLOCKED")!=(count==0)):
            return result
        return {**BASE,
                "status":"RETROSPECTIVE_ONLY_NOT_TRADE_PROOF" if count else "BLOCKED",
                "reason":"MISSING_PER_BAR_FIRST_SEEN_BROKER_QUOTES_AND_COSTS",
                "closedCounts":{tf:counts[tf] for tf in FRAMES_ORDER},
                "retrospectiveDecisionCount":count,
                "technicalWatchCounts":{key:watches[key] for key in ("BUY","SELL","NONE")}}
    except (OSError,ValueError,TypeError,KeyError,subprocess.SubprocessError):
        return result

def main():
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--vault-dir",required=True)
    args=parser.parse_args()
    # Explicit owner-only local archival approval and private disk for CLI.
    # No incoming HTTP endpoint is created and no collector is restarted.
    from biquote_private_forward_vault import APPROVAL_ENV,APPROVAL
    if (not pathlib.Path(args.vault_dir).is_absolute() or
        not str(args.vault_dir).startswith("/var/data/") or
        os.environ.get(APPROVAL_ENV)!=APPROVAL):
        print(json.dumps({**BASE,"reason":"OWNER_ONLY_ARCHIVE_ACCESS_NOT_APPROVED"}))
        return
    print(json.dumps(inspect_private_vault(args.vault_dir),sort_keys=True))

if __name__=="__main__":
    main()
