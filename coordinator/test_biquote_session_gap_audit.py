"""Offline-only session-reference hypotheses, not MT5 broker certifications."""
import datetime as dt
import unittest
from biquote_session_gap_audit import audit_gap_times, reference_window_for_missing_slot

UTC=dt.timezone.utc
def utc(s):
    return dt.datetime.fromisoformat(s.replace("Z","+00:00"))
def entry(s):
    return {"openTime":s,"isOpen":False}
def packet(m15,h1,h4):
    return {name:{"bars":[entry(x) for x in data]}
            for name,data in (("M15",m15),("H1",h1),("H4",h4))}

class TestSessionGapDiagnostic(unittest.TestCase):
    def test_daily_pause_and_weekend_only_reference_not_verified(self):
        r=audit_gap_times(packet(
            ["2026-11-16T21:45:00Z","2026-11-16T23:00:00Z"],
            ["2026-11-16T21:00:00Z","2026-11-16T23:00:00Z"],
            ["2026-11-13T20:00:00Z","2026-11-15T20:00:00Z"]))
        self.assertIsNone(r["error"])
        for tf,slots in (("M15",4),("H1",1),("H4",11)):
            d=r["frameGaps"][tf]
            self.assertEqual(d["gapCount"],1)
            self.assertEqual(d["missingCandleSlots"],slots)
            item=d["firstGapsUTC"][0]
            self.assertEqual(item["referencePauseSlots"],slots)
            self.assertEqual(item["referenceTradingTimeMissingSlots"],0)
            self.assertEqual(item["classification"],"REFERENCE_PAUSE_CANDIDATE_NOT_VERIFIED")
        self.assertFalse(r["brokerScheduleVerified"])
        self.assertFalse(r["sessionCalendarIndependentlyVerified"])
        self.assertFalse(r["executable"])
        self.assertEqual(r["signal"],"WAIT")

    def test_open_market_gap_is_never_called_pause(self):
        r=audit_gap_times(packet(
            ["2026-11-17T10:00:00Z","2026-11-17T10:30:00Z"],
            ["2026-11-17T10:00:00Z","2026-11-17T12:00:00Z"],
            ["2026-11-17T04:00:00Z","2026-11-17T12:00:00Z"]))
        self.assertEqual(r["frameGaps"]["M15"]["firstGapsUTC"][0]["classification"],
                         "UNEXPLAINED_IN_REFERENCE_TRADING_TIME")
        self.assertEqual(r["frameGaps"]["H1"]["firstGapsUTC"][0]["referenceTradingTimeMissingSlots"],1)
        self.assertEqual(r["frameGaps"]["H4"]["firstGapsUTC"][0]["referenceTradingTimeMissingSlots"],1)

    def test_sunday_reopening_and_unknown_season_are_not_assumed(self):
        self.assertFalse(reference_window_for_missing_slot(utc("2026-11-15T23:00:00Z"),900))
        self.assertTrue(reference_window_for_missing_slot(utc("2026-11-15T22:45:00Z"),900))
        self.assertIsNone(reference_window_for_missing_slot(utc("2026-08-17T22:00:00Z"),900))

    def test_rejected_non_utc_and_unaligned_dont_invent_schedules(self):
        data=packet(["2026-11-17T10:13:00Z","2026-11-17T10:30:00Z"],
                    ["2026-11-17T10:00:00Z","2026-11-17T11:00:00Z"],
                    ["2026-11-17T04:00:00Z","2026-11-17T08:00:00Z"])
        self.assertEqual(audit_gap_times(data)["error"],"MISALIGNED_CANDLE_GAP")
        data["M15"]["bars"][0]["openTime"]="2026-11-17T10:00:00+02:00"
        self.assertEqual(audit_gap_times(data)["error"],"NON_UTC_CANDLE_TIME")
        self.assertFalse(audit_gap_times({})["sessionCalendarIndependentlyVerified"])

if __name__=="__main__":
    unittest.main()
