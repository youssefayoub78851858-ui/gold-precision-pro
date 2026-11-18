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
