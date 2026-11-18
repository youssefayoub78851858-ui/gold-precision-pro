"""Zero-network regression of seven-day bounded private research windows."""
import datetime as dt
import socket
import unittest
from unittest.mock import patch

import biquote_seven_day_review as run

UTC=dt.timezone.utc
ENV={"CUTOVER_MODE":"standby",
     "GPP_BIQUOTE_PUBLIC_24H_REVIEW":"APPROVED_READONLY_NO_TRADING",
     "GPP_BIQUOTE_PRIVATE_FORWARD_ARCHIVE":"APPROVED_READONLY_PRIVATE_NO_TRADING",
     "GPP_BIQUOTE_7DAY_FORWARD_REVIEW":"APPROVED_SEVEN_DAYS_READONLY_NO_TRADING"}
DAY=run.START
VAULT="/var/data/biquote-private-approved"

def meta(n=0):
    return {"status":"PRIVATE_FORWARD_VAULT_METADATA_ONLY","signal":"WAIT",
            "executable":False,"paperOrdersAllowed":False,"tradeSignalReady":False,
            "quoteSamples":n,"counts":{"M15":0,"H1":0,"H4":0}}

class SevenDayReviewTests(unittest.TestCase):
    def test_approval_standby_and_no_auto_activation(self):
        for key in list(ENV):
            bad={**ENV,key:"disabled"}
            self.assertFalse(run.approved(bad))
            with self.assertRaisesRegex(ValueError,"SEPARATE_SEVEN_DAY"):
                run.run_seven_days(VAULT,environment=bad)
        self.assertTrue(run.approved(ENV))
        with self.assertRaisesRegex(ValueError,"OWNER_ONLY"):
            run.run_seven_days("/tmp/untrusted",environment=ENV)
        with self.assertRaisesRegex(ValueError,"HOLDOUT"):
            run.run_seven_days(VAULT,environment=ENV,anchor=DAY+dt.timedelta(days=1))
        with self.assertRaisesRegex(ValueError,"HOLDOUT"):
            run.run_seven_days(VAULT,environment=ENV,days=8)

    def test_single_probe_and_signed_archive_sink_no_market_leak(self):
        reads=[]; writes=[]; status=[]
        def source_probe(*,private_snapshot_sink):
            private_snapshot_sink({"private":"DO_NOT_DISPLAY"},DAY+dt.timedelta(minutes=10))
            reads.append(1)
            return {"signal":"WAIT"}
        def observer(start,*,probe):
            self.assertEqual(start,DAY)
            self.assertEqual(probe()["signal"],"WAIT")
            return {"signal":"WAIT","executable":False,"completed24hWindow":True}
        def archive(path,sample,*,received_utc):
            writes.append((path,sample,received_utc))
            return {"saved":True}
        with patch.object(socket,"socket",side_effect=AssertionError("NO_NETWORK")):
            out=run.run_seven_days(VAULT,clock=lambda:DAY+dt.timedelta(minutes=2),
                     observer=observer,source_probe=source_probe,archive=archive,
                     metadata=lambda _:meta(),emit=status.append,days=1,environment=ENV)
        self.assertEqual(out["windowsCompleted"],1)
        self.assertEqual(len(reads),1)
        self.assertEqual(len(writes),1)
        self.assertEqual(writes[0][0],VAULT)
        self.assertEqual(out["signal"],"WAIT")
        self.assertFalse(out["paperOrdersAllowed"])
        self.assertFalse(out["sourceQualifiedForTrading"])
        self.assertNotIn("DO_NOT_DISPLAY",str(status)+str(out))
        self.assertNotIn("DO_NOT_DISPLAY",str(out))
        self.assertNotIn("quoteObservations",str(out))
        self.assertNotIn("\'private\':",str(out))
        audit=next(x for x in status if x["event"]=="BIQUOTE_SEVEN_DAY_VAULT_REOPEN_AUDIT")
        self.assertEqual(audit["previouslyStoredQuoteSamples"],0)
        self.assertFalse(audit["previouslyStoredData"])
        self.assertEqual(audit["closedBarCounts"],{"M15":0,"H1":0,"H4":0})
        self.assertEqual(audit["signal"],"WAIT")
        self.assertFalse(audit["paperOrdersAllowed"])

    def test_restarted_vault_counts_are_read_from_sealed_metadata_not_memory(self):
        printed=[]
        prior={**meta(37),"counts":{"M15":5,"H1":2,"H4":1},
               "quoteObservations":[{"bid":91372.55,"ask":91372.75}],
               "secretBrokerToken":"DO_NOT_LOG"}
        def observer(start,*,probe):
            self.assertEqual(start,DAY)
            return {"signal":"WAIT","executable":False,"completed24hWindow":True}
        with patch.object(socket,"socket",side_effect=AssertionError("NO_NETWORK")):
            result=run.run_seven_days(VAULT,clock=lambda:DAY+dt.timedelta(minutes=3),
                observer=observer,metadata=lambda _:prior,emit=printed.append,
                days=1,environment=ENV)
        self.assertEqual(result["signal"],"WAIT")
        audited=next(v for v in printed if v["event"]=="BIQUOTE_SEVEN_DAY_VAULT_REOPEN_AUDIT")
        self.assertTrue(audited["previouslyStoredData"])
        self.assertEqual(audited["previouslyStoredQuoteSamples"],37)
        self.assertEqual(audited["closedBarCounts"],{"M15":5,"H1":2,"H4":1})
        self.assertEqual(audited["capacityStatus"],"CAPACITY_HEADROOM")
        self.assertNotIn("91372",str(printed))
        self.assertNotIn("DO_NOT_LOG",str(printed))
        self.assertNotIn("quoteObservations",str(printed))

    def test_new_closed_bar_emits_safe_counts_and_gaps_without_quotes(self):
        events=[]
        calls=[0]
        def metadata(_):
            calls[0]+=1
            if calls[0]==1:
                return meta()
            result={**meta(2),"counts":{"M15":1,"H1":0,"H4":0}}
            result["forwardCoverage"]={
                "M15":{"closedBars":1,"latestContiguousBars":1,
                       "unclassifiedGapPairs":0,"unclassifiedMissingSlots":0},
                "H1":{"closedBars":0,"latestContiguousBars":0,
                      "unclassifiedGapPairs":0,"unclassifiedMissingSlots":0},
                "H4":{"closedBars":0,"latestContiguousBars":0,
                      "unclassifiedGapPairs":0,"unclassifiedMissingSlots":0},
            }
            result["privateSecret"]="DO_NOT_LOG_BROKER_PASSWORD"
            return result
        def archive(_path,_sample,*,received_utc):
            return {"newClosedBars":{"M15":1,"H1":0,"H4":0},
                    "rawBid":987654.32}
        def probe(*,private_snapshot_sink):
            private_snapshot_sink({"secret":"DO_NOT_LOG_RAW_QUOTE"},
                                  DAY+dt.timedelta(minutes=15))
            return {"signal":"WAIT"}
        def observer(_start,*,probe):
            probe()
            return {"signal":"WAIT","executable":False,"completed24hWindow":True}
        with patch.object(socket,"socket",side_effect=AssertionError("NO_NETWORK")):
            result=run.run_seven_days(VAULT,clock=lambda:DAY+dt.timedelta(minutes=3),
                metadata=metadata,archive=archive,source_probe=probe,
                observer=observer,emit=events.append,days=1,environment=ENV)
        self.assertEqual(result["windowsCompleted"],1)
        progress=[x for x in events if x["event"]=="BIQUOTE_STAGE3_CLOSED_BAR_PROGRESS"]
        self.assertEqual(len(progress),1)
        self.assertEqual(progress[0]["frames"]["M15"]["persistedClosed"],1)
        self.assertEqual(progress[0]["frames"]["H4"]["contiguousClosed"],0)
        self.assertEqual(progress[0]["h4RemainingUntil21"],21)
        self.assertFalse(progress[0]["v3TradeQualified"])
        for secret in ("DO_NOT_LOG_RAW_QUOTE","DO_NOT_LOG_BROKER_PASSWORD","987654"):
            self.assertNotIn(secret,str(events)+str(result))

    def test_rejected_stage3_counter_metadata_fails_closed_without_leaks(self):
        events=[]
        calls=[0]
        def metadata(_):
            calls[0]+=1
            if calls[0]==1:return meta()
            return {**meta(),"privateSecret":"NO_PRINT_THIS",
                "forwardCoverage":{"M15":{"closedBars":1,
                    "latestContiguousBars":999,"unclassifiedGapPairs":0,
                    "unclassifiedMissingSlots":0}}}
        def archive(*_args,**_kwargs):
            return {"newClosedBars":{"M15":1,"H1":0,"H4":0}}
        def probe(*,private_snapshot_sink):
            private_snapshot_sink({},DAY+dt.timedelta(minutes=15))
            return {"signal":"WAIT"}
        def observer(_start,*,probe):
            probe()
            return {"signal":"WAIT","executable":False,"completed24hWindow":True}
        out=run.run_seven_days(VAULT,clock=lambda:DAY+dt.timedelta(minutes=3),
            metadata=metadata,archive=archive,source_probe=probe,
            observer=observer,emit=events.append,days=1,environment=ENV)
        self.assertEqual(out["signal"],"WAIT")
        self.assertTrue(any(x["event"]=="BIQUOTE_STAGE3_METADATA_UNAVAILABLE" for x in events))
        self.assertFalse(any(x["event"]=="BIQUOTE_STAGE3_CLOSED_BAR_PROGRESS" for x in events))
        self.assertNotIn("NO_PRINT_THIS",str(events))

    def test_restart_gap_reference_counts_are_metadata_only_and_not_approval(self):
        events=[]
        known={**meta(4),"counts":{"M15":2,"H1":2,"H4":2},
               "sensitiveBid":912345.5,"secret":"PRIVATE_DO_NOT_DISPLAY"}
        sealed={"closed":{
            "M15":[{"openTime":"2026-11-16T21:45:00Z"},
                   {"openTime":"2026-11-16T23:00:00Z"}],
            "H1":[{"openTime":"2026-11-16T21:00:00Z"},
                  {"openTime":"2026-11-16T23:00:00Z"}],
            "H4":[{"openTime":"2026-11-16T20:00:00Z"},
                  {"openTime":"2026-11-17T00:00:00Z"}]},
            "quoteObservations":[{"secret":"DO_NOT_PRINT"}]}
        with patch.object(socket,"socket",side_effect=AssertionError("NO_NETWORK")), patch.object(
                run,"load_vault",return_value=sealed):
            out=run.run_seven_days(VAULT,clock=lambda:DAY+dt.timedelta(minutes=2),
                metadata=lambda _:known,
                observer=lambda *_args,**_kwargs:{"signal":"WAIT",
                    "executable":False,"completed24hWindow":True},
                emit=events.append,days=1,environment=ENV)
        self.assertEqual(out["windowsCompleted"],1)
        gaps=[x for x in events if x["event"]=="BIQUOTE_STAGE3_VENDOR_REFERENCE_GAPS"]
        self.assertEqual(len(gaps),1)
        self.assertEqual(gaps[0]["phase"],"RESTART")
        self.assertEqual(gaps[0]["frames"]["M15"]["unclassifiedMissingSlots"],4)
        self.assertEqual(gaps[0]["frames"]["M15"]["vendorPauseCandidateSlotsNotVerified"],4)
        self.assertEqual(gaps[0]["frames"]["H4"]["unclassifiedMissingSlots"],0)
        self.assertFalse(gaps[0]["gapsApproved"])
        self.assertFalse(gaps[0]["brokerSessionVerified"])
        self.assertFalse(gaps[0]["paperOrdersAllowed"])
        self.assertFalse(gaps[0]["liveOrdersAllowed"])
        for marker in ("912345","DO_NOT_PRINT","PRIVATE_DO_NOT_DISPLAY",
                       "2026-11-16T21"):
            self.assertNotIn(marker,str(events)+str(out))

    def test_closed_h1_h4_parity_in_render_events_is_counts_only(self):
        start=dt.datetime(2026,11,18,tzinfo=UTC)
        def closed(minutes):
            return {"openTime":(start+dt.timedelta(minutes=minutes))
                    .strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "open":100,"high":101,"low":99,"close":100}
        archive={"closed":{
            "M15":[closed(15*i) for i in range(32)],
            "H1":[closed(60*i) for i in range(8)],
            "H4":[closed(240*i) for i in range(2)]},
            "quoteObservations":[{"secret":"NOT_FOR_LOGS"}]}
        metadata={**meta(4),"counts":{"M15":32,"H1":8,"H4":2},
                  "privateKey":"CREDENTIAL_MUST_NEVER_LEAK"}
        for mismatched in (False, True):
            events=[]
            sample_archive={"closed":{tf:[dict(x) for x in rows]
              for tf,rows in archive["closed"].items()},
              "quoteObservations":archive["quoteObservations"]}
            if mismatched:
                sample_archive["closed"]["H4"][-1]["high"]=102
            with patch.object(socket,"socket",side_effect=AssertionError("NO_NETWORK")),patch.object(
                    run,"load_vault",return_value=sample_archive):
                outcome=run.run_seven_days(VAULT,clock=lambda:DAY+dt.timedelta(minutes=2),
                    metadata=lambda _:metadata,
                    observer=lambda *_args,**_kwargs:{"signal":"WAIT",
                        "executable":False,"completed24hWindow":True},
                    emit=events.append,days=1,environment=ENV)
            results=[x for x in events
                     if x["event"]=="BIQUOTE_STAGE3_ARCHIVE_OHLC_OVERLAP"]
            self.assertEqual(len(results),1)
            proof=results[0]
            self.assertEqual(proof["phase"],"RESTART")
            self.assertEqual(proof["frames"]["H1"]["fullyCoveredCompared"],8)
            self.assertEqual(proof["frames"]["H4"]["fullyCoveredCompared"],2)
            self.assertEqual(proof["frames"]["H4"]["fullyCoveredDisagreed"],
                             1 if mismatched else 0)
            self.assertEqual(proof["frames"]["H4"]["notFullyCovered"],0)
            self.assertFalse(proof["sourceRightsVerified"])
            self.assertFalse(proof["brokerSessionVerified"])
            self.assertFalse(proof["tradeEligible"])
            self.assertFalse(proof["liveOrdersAllowed"])
            self.assertFalse(proof["paperOrdersAllowed"])
            self.assertEqual(outcome["signal"],"WAIT")
            for secret in ("CREDENTIAL_MUST_NEVER_LEAK","NOT_FOR_LOGS",
                           "2026-11-18T00","\"high\"","\"open\""):
                self.assertNotIn(secret,str(events)+str(outcome))

    def test_mid_vs_closed_bars_log_reports_only_validated_counts(self):
        # Real HTTP is never contacted. A synthetic tick from one sealed
        # closed candle matches each timeframe, then contradicts all three.
        opened="2026-11-18T08:00:00Z"
        closed={"openTime":opened,"open":4000.0,"high":4000.5,
                "low":3999.5,"close":4000.2}
        for tick_bid,expected in ((4000.1,"CONSISTENT_OBSERVED_SAMPLES_ONLY"),
                                  (4008.0,"OBSERVED_MID_OUTSIDE_CLOSED_OHLC"),
                                  (-1.0,None)):
            log=[]
            vault={"schema":1,"source":"BIQUOTE_UNVERIFIED_UPSTREAM_MT5",
                   "closed":{tf:[dict(closed)] for tf in ("M15","H1","H4")},
                   "quoteObservations":[{
                       "tickUTC":"2026-11-18T08:02:00Z",
                       "observedUTC":"2026-11-18T08:02:02Z",
                       "bid":tick_bid,"ask":4008.5 if tick_bid==4008.0 else 4000.3,
                       "password":"PRIVATE_DO_NOT_PRINT"}],
                   "secret":"BRIDGE_MUST_NOT_LEAK"}
            counts={"M15":1,"H1":1,"H4":1}
            with patch.object(socket,"socket",side_effect=AssertionError("NO_NETWORK")),patch.object(
                    run,"load_vault",return_value=vault):
                response=run.run_seven_days(VAULT,clock=lambda:DAY+dt.timedelta(minutes=2),
                    metadata=lambda _:{**meta(1),"counts":counts},
                    observer=lambda *_args,**_kwargs:{"signal":"WAIT",
                        "executable":False,"completed24hWindow":True},
                    emit=log.append,days=1,environment=ENV)
            self.assertEqual(response["signal"],"WAIT")
            self.assertFalse(response["paperOrdersAllowed"])
            entries=[x for x in log
                     if x["event"]=="BIQUOTE_STAGE3_QUOTE_MID_CLOSED_RANGE"]
            if expected is None:
                self.assertFalse(entries)
                self.assertEqual(len([x for x in log if
                    x["event"]=="BIQUOTE_STAGE3_QUOTE_MID_RANGE_UNAVAILABLE"]),1)
            else:
                self.assertEqual(len(entries),1)
                proof=entries[0]
                self.assertEqual(proof["status"],expected)
                self.assertEqual(proof["phase"],"RESTART")
                self.assertEqual(proof["sourceQuoteSamples"],1)
                for tf in ("M15","H1","H4"):
                    item=proof["frames"][tf]
                    self.assertEqual(item["comparableQuoteSamples"],1)
                    self.assertEqual(item["outsideClosedOHLC"],int(tick_bid>4001))
                    self.assertEqual(item["withinClosedOHLC"],int(tick_bid<4001))
                    self.assertEqual(item["notInArchivedClosedBars"],0)
                self.assertFalse(proof["brokerSessionVerified"])
                self.assertFalse(proof["sourceRightsVerified"])
                self.assertFalse(proof["tradeEligible"])
                self.assertFalse(proof["liveOrdersAllowed"])
            printed=str(log)+str(response)
            for secret in ("PRIVATE_DO_NOT_PRINT","BRIDGE_MUST_NOT_LEAK",
                           "4000.1","4008.0","4008.5",opened,
                           "'bid'","'ask'","'openTime'"):
                self.assertNotIn(secret,printed)

    def test_mismatched_sealed_reference_is_unavailable_without_promoting(self):
        events=[]
        forged={**meta(4),"counts":{"M15":2,"H1":0,"H4":0}}
        with patch.object(run,"load_vault",return_value={
                "closed":{"M15":[],"H1":[],"H4":[]},
                "secret":"NEVER_PRINT_THIS"}):
            out=run.run_seven_days(VAULT,clock=lambda:DAY+dt.timedelta(minutes=2),
                metadata=lambda _:forged,
                observer=lambda *_args,**_kwargs:{"signal":"WAIT",
                    "executable":False,"completed24hWindow":True},
                emit=events.append,days=1,environment=ENV)
        self.assertEqual(out["signal"],"WAIT")
        self.assertTrue(any(x["event"]=="BIQUOTE_STAGE3_REFERENCE_UNAVAILABLE"
                            for x in events))
        self.assertFalse(any(x["event"]=="BIQUOTE_STAGE3_VENDOR_REFERENCE_GAPS"
                             for x in events))
        self.assertNotIn("NEVER_PRINT_THIS",str(events))

    def test_corrupt_metadata_blocks_readonly_worker_before_any_feed_call(self):
        emitted=[]
        def must_not_call(*_a,**_k):
            self.fail("NO_NETWORK_OR_ORDER_ALLOWED_ON_BAD_STORAGE")
        out=run.run_seven_days(VAULT,clock=lambda:DAY+dt.timedelta(minutes=3),
            metadata=lambda _:{**meta(-1)},source_probe=must_not_call,
            observer=must_not_call,days=1,environment=ENV,emit=emitted.append)
        self.assertEqual(out["status"],"VAULT_METADATA_READ_BLOCKED")
        self.assertEqual(out["signal"],"WAIT")
        self.assertFalse(out["paperOrdersAllowed"])
        self.assertEqual(emitted[0]["event"],"BIQUOTE_SEVEN_DAY_VAULT_AUDIT_BLOCKED")
        self.assertNotIn("quoteSamples",str(emitted))

    def test_restart_expired_days_skipped_and_budget_stops_before_io(self):
        invoked=[]
        def no_io(*args,**kwargs):
            invoked.append(1)
            raise AssertionError("MUST_NOT_CALL")
        with patch.object(socket,"socket",side_effect=AssertionError("NO_NETWORK")):
            out=run.run_seven_days(VAULT,clock=lambda:DAY+dt.timedelta(days=7),
                  metadata=no_io,observer=no_io,source_probe=no_io,days=7,environment=ENV)
        self.assertEqual(out["windowsExpiredWithoutReplay"],7)
        self.assertEqual(out["windowsCompleted"],0)
        self.assertEqual(invoked,[])
        capped=run.run_seven_days(VAULT,clock=lambda:DAY+dt.timedelta(days=1,minutes=1),
                metadata=lambda _:meta(9300),observer=no_io,source_probe=no_io,
                days=2,environment=ENV)
        self.assertEqual(capped["windowsExpiredWithoutReplay"],1)
        self.assertEqual(capped["status"],"CAPACITY_REVIEW_REQUIRED")
        self.assertEqual(invoked,[])

    def test_bad_report_and_future_clock_fail_closed(self):
        out=run.run_seven_days(VAULT,clock=lambda:DAY+dt.timedelta(minutes=2),
                metadata=lambda _:meta(),observer=lambda *_a,**_k:{"signal":"BUY"},
                days=1,environment=ENV)
        self.assertEqual(out["status"],"REPORT_CONTRACT_REJECTED")
        self.assertFalse(out["liveOrdersAllowed"])
        with self.assertRaisesRegex(ValueError,"NON_ADVANCING"):
            run.run_seven_days(VAULT,clock=lambda:DAY-dt.timedelta(days=2),
                sleep=lambda _:None,days=1,environment=ENV)

if __name__=="__main__":
    unittest.main()
