"""Offline local sealed-vault -> frozen V3 chronological research counter.

Never calls a market provider or opens a paper account. Reads one already
SHA-checked private archive, supplies OHLC over local Node stdin only, and
emits count-only WAIT metadata. New bars can have locally observed receipts;
legacy bars do not. Neither proves broker first availability or executable fills.
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
        # Snapshot at the last LOCAL sealed-vault import; never infer a clock
        # from candle opening/closing, file mtime, or wall-clock now.
        if sealed.get("lastImportedUTC") is not None:
            packet["decisionCutoffUTC"]=sealed["lastImportedUTC"]
        for tf in FRAMES_ORDER:
            packet["frames"][tf]=[
                {"datetime":b["openTime"],"open":b["open"],"high":b["high"],
                 "low":b["low"],"close":b["close"]}
                for b in sealed["closed"][tf]]
        if "firstObservedClosedUTC" in sealed:
            packet["firstObservedClosedUTC"]=sealed["firstObservedClosedUTC"]
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
        audit=out.get("firstSeenReceiptAudit")
        point=out.get("signalDataReadiness")
        receipt_counts={tf:len(sealed.get("firstObservedClosedUTC",{}).get(tf,{}))
                        for tf in FRAMES_ORDER}
        legacy_counts={tf:counts[tf]-receipt_counts[tf] for tf in FRAMES_ORDER}
        receipt_count=audit.get("observedDecisionCount") if isinstance(audit,dict) else None
        receipt_watches=audit.get("technicalWatchCounts") if isinstance(audit,dict) else None
        receipt_status=("NO_TIME_ELIGIBLE_WATCHES" if receipt_count==0 else
                        "LOCAL_RECEIPT_WATCHES_NOT_TRADE_PROOF")
        if (not isinstance(audit,dict) or
            audit.get("mode")!="BIQUOTE_V3_LOCAL_FIRST_SEEN_RECEIPT_AUDIT_ONLY" or
            audit.get("signal")!="WAIT" or
            audit.get("executable") is not False or
            audit.get("paperOrdersAllowed") is not False or
            audit.get("brokerOrdersSent")!=0 or
            audit.get("sourceRightsVerified") is not False or
            audit.get("independentReceiptVerified") is not False or
            audit.get("brokerFillsModeled") is not False or
            audit.get("winRate") is not None or
            audit.get("netExpectancy") is not None or
            audit.get("firstObservedBarCounts")!=receipt_counts or
            audit.get("legacyMissingReceiptCounts")!=legacy_counts or
            type(receipt_count) is not int or not 0<=receipt_count<=256 or
            not isinstance(receipt_watches,dict) or
            set(receipt_watches)!={"BUY","SELL","NONE"} or
            any(type(receipt_watches[k]) is not int or
                not 0<=receipt_watches[k]<=256 for k in receipt_watches) or
            sum(receipt_watches.values())!=receipt_count or
            audit.get("status")!=(
                receipt_status if "firstObservedClosedUTC" in sealed else "BLOCKED")):
            return result
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
        # Validate all count-only point-in-time metadata BEFORE exposing it.
        # A JSON runner cannot self-authorize market rights or paper/live orders.
        if (not isinstance(point,dict)
            or point.get("mode")!="BIQUOTE_LOCAL_POINT_IN_TIME_DATA_GATE_V1"
            or point.get("status") not in (
                "RECEIPTS_UNAVAILABLE","INSUFFICIENT_EVIDENCE",
                "LOCAL_GEOMETRY_ONLY_NOT_TRADE_READY")
            or point.get("signal")!="WAIT"
            or point.get("researchCandidate")!="NONE"
            or any(point.get(k) is not False for k in (
                "executable","tradeEligible","paperOrdersAllowed",
                "liveOrdersAllowed","sourceRightsVerified",
                "brokerSessionCalendarVerified","independentAvailabilityVerified",
                "brokerCostsVerified","profitabilityProven"))
            or point.get("brokerOrdersSent")!=0
            or point.get("providerRequestsMade")!=0
            or point.get("storedClosedCounts")!=counts
            or point.get("legacyWithoutFirstSeen")!=legacy_counts
            or point.get("observedAtDecision")!=receipt_counts):
            return result
        continuous=point.get("contiguousObservedClosed")
        warm=point.get("technicalWarmupMissing")
        paper=point.get("paperHistoryMissing")
        if (not all(isinstance(v,dict) and set(v)==set(FRAMES_ORDER)
                    for v in (continuous,warm,paper))
            or any(type(continuous[tf]) is not int
                   or not 0<=continuous[tf]<=receipt_counts[tf]
                   or type(warm[tf]) is not int
                   or warm[tf]!=max(0,21-continuous[tf])
                   or type(paper[tf]) is not int
                   or paper[tf]!=max(0,50-continuous[tf])
                   for tf in FRAMES_ORDER)):
            return result
        local=point.get("status")=="LOCAL_GEOMETRY_ONLY_NOT_TRADE_READY"
        if (point.get("localGeometryObserved") is not local
            or point.get("localTimingAndParityCheck")!=(
                "LOCAL_ONLY_NOT_INDEPENDENT" if local else "NOT_PROVEN")
            or (local and any(warm.values()))
            or (("firstObservedClosedUTC" not in sealed)!=
                (point.get("status")=="RECEIPTS_UNAVAILABLE"))):
            return result
        # The exact local lastImport time is passed to Node. Its result can
        # canonicalize .000Z, but may never assert a different decision clock.
        if "firstObservedClosedUTC" in sealed:
            import datetime as dt
            try:
                observed_clock=dt.datetime.fromisoformat(
                    point["asOfUTC"].replace("Z","+00:00"))
                archived_clock=dt.datetime.fromisoformat(
                    sealed["lastImportedUTC"].replace("Z","+00:00"))
            except (TypeError,ValueError,KeyError,AttributeError):
                return result
            if observed_clock!=archived_clock:
                return result
        return {**BASE,
                "status":"RETROSPECTIVE_ONLY_NOT_TRADE_PROOF" if count else "BLOCKED",
                "reason":"MISSING_PER_BAR_FIRST_SEEN_BROKER_QUOTES_AND_COSTS",
                "closedCounts":{tf:counts[tf] for tf in FRAMES_ORDER},
                "retrospectiveDecisionCount":count,
                "technicalWatchCounts":{key:watches[key] for key in ("BUY","SELL","NONE")},
                "pointInTimeDataAudit":{
                    "status":point["status"],"signal":"WAIT",
                    "sourceRightsVerified":False,
                    "independentAvailabilityVerified":False,
                    "brokerSessionCalendarVerified":False,
                    "localTimingAndParityCheck":point["localTimingAndParityCheck"],
                    "observedAtDecision":receipt_counts,
                    "legacyWithoutFirstSeen":legacy_counts,
                    "contiguousObservedClosed":continuous,
                    "technicalWarmupMissing":warm,
                    "paperHistoryMissing":paper},
                "localFirstSeenAudit":{
                    "status":audit["status"],"signal":"WAIT",
                    "paperOrdersAllowed":False,
                    "independentReceiptVerified":False,
                    "recordedClosedCounts":receipt_counts,
                    "unknownLegacyClosedCounts":legacy_counts,
                    "observedDecisionCount":receipt_count,
                    "technicalWatchCounts":{
                        key:receipt_watches[key] for key in ("BUY","SELL","NONE")}}}
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
