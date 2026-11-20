"""No-network Capital.com Demo OFFLINE adapter tests: all prices fabricated."""
import copy
import datetime as dt
import unittest

from capital_demo_offline_adapter import (
    DEMO_BASE_URL, demo_price_get_blueprint, review_capital_demo_pages
)

NOW = dt.datetime(2026, 11, 16, 12, 15, tzinfo=dt.timezone.utc)
EPIC = "TEST.GOLD.EPIC"


def sample_page(frame, count=3):
    widths = {"M15": 900, "H1": 3600, "H4": 14400}
    width = widths[frame]
    end = int(NOW.timestamp()) // width * width
    prices = []
    for index in range(count):
        opened = dt.datetime.fromtimestamp(end-width*(count-index), dt.timezone.utc)
        price = 4000+index
        prices.append({
            "snapshotTimeUTC": opened.strftime("%Y-%m-%dT%H:%M:%S"),
            "snapshotTime": "LOCAL_TIME_NOT_USED",
            "openPrice": {"bid":price, "ask":price+0.3},
            "highPrice": {"bid":price+2, "ask":price+2.3},
            "lowPrice": {"bid":price-1, "ask":price-0.7},
            "closePrice": {"bid":price+1, "ask":price+1.3},
            "lastTradedVolume": 99
        })
    return {"epic":EPIC, "resolution":
            {"M15":"MINUTE_15","H1":"HOUR","H4":"HOUR_4"}[frame],
            "prices":prices}


def sample(count=3):
    return {tf:[sample_page(tf,count)] for tf in ("M15","H1","H4")}


class CapitalDemoOfflineTests(unittest.TestCase):
    def check_wait(self, result):
        self.assertEqual(result["signal"], "WAIT")
        for flag in ("executable", "researchEligible", "paperTradingAllowed",
                     "providerConnectionStarted", "credentialsUsed",
                     "liveEndpointSupported", "orderEndpointsSupported", "dataRightsVerified"):
            self.assertIs(result[flag], False, flag)
        self.assertEqual(result["providerRequestsMade"], 0)

    def test_documented_bid_ask_offline_shape_and_unverified_rights(self):
        packets=sample()
        original=copy.deepcopy(packets)
        r=review_capital_demo_pages(packets, EPIC, NOW)
        self.check_wait(r)
        self.assertEqual(packets, original)
        self.assertTrue(r["offlineQuoteShapeValid"])
        self.assertEqual(r["closedBarCounts"], {"M15":3,"H1":3,"H4":3})
        self.assertEqual(r["minimumWarmupMissing"], {"M15":47,"H1":47,"H4":47})
        self.assertIn("PRIVATE_RENDER_DATA_RIGHTS_UNCONFIRMED",r["blockingReasons"])
        self.assertEqual(r["stagedBidFrames"]["M15"][0]["open"],4000)
        self.assertEqual(r["stagedAskFrames"]["M15"][0]["open"],4000.3)
        self.assertNotIn("volume",r["stagedBidFrames"]["M15"][0])

    def test_fifty_h4_warmup_does_not_grant_rights(self):
        r=review_capital_demo_pages(sample(50),EPIC,NOW)
        self.check_wait(r)
        self.assertEqual(r["minimumWarmupMissing"],{"M15":0,"H1":0,"H4":0})
        self.assertIn("NO_RESEARCH_OR_TRADING_ADMISSION",r["blockingReasons"])

    def test_duplicate_pagination_identical_is_deduplicated_conflict_blocked(self):
        packets=sample()
        row=copy.deepcopy(packets["M15"][0]["prices"][-1])
        packets["M15"].append({"prices":[row]})
        r=review_capital_demo_pages(packets,EPIC,NOW)
        self.check_wait(r)
        self.assertTrue(r["offlineQuoteShapeValid"])
        self.assertEqual(r["duplicatePageBoundaryRows"]["M15"],1)
        packets["M15"][1]["prices"][0]["closePrice"]["ask"]+=0.1
        broken=review_capital_demo_pages(packets,EPIC,NOW)
        self.check_wait(broken)
        self.assertIn("DUPLICATE_TIMESTAMP_CONFLICT",broken["blockingReasons"])
        self.assertNotIn("stagedBidFrames",broken)

    def test_crossed_quotes_never_auto_repaired(self):
        for field in ("openPrice","highPrice","lowPrice","closePrice"):
            with self.subTest(field=field):
                packets=sample()
                obj=packets["M15"][0]["prices"][0][field]
                obj["ask"]=obj["bid"]-0.1
                r=review_capital_demo_pages(packets,EPIC,NOW)
                self.check_wait(r)
                self.assertIn("BID_ASK_CROSSED_NO_AUTO_REPAIR",r["blockingReasons"])

    def test_invalid_price_times_fractions_and_candle_geometry(self):
        cases=(
            (lambda row: row.pop("snapshotTimeUTC"),"SNAPSHOT_UTC_MISSING"),
            (lambda row: row.update(snapshotTimeUTC="2026-11-16T14:00:00+02:00"),"SNAPSHOT_UTC_INVALID"),
            (lambda row: row.update(snapshotTimeUTC="2026-11-16T08:00:00.500"),"CANDLE_UTC_UNALIGNED"),
            (lambda row: row.update(snapshotTimeUTC="2026-11-16T12:15:00"),"CANDLE_UNCLOSED_OR_FUTURE"),
            (lambda row: row["openPrice"].update(bid=float("nan")),"BID_ASK_PRICE_INVALID"),
            (lambda row: row["openPrice"].update(bid=True),"BID_ASK_PRICE_INVALID"),
            (lambda row: row["highPrice"].update(bid=1),"BID_ASK_OHLC_INVALID"),
            (lambda row: row["lowPrice"].pop("ask"),"BID_ASK_PRICE_INVALID")
        )
        for mutation,expected in cases:
            with self.subTest(expected=expected):
                packets=sample()
                mutation(packets["M15"][0]["prices"][0])
                r=review_capital_demo_pages(packets,EPIC,NOW)
                self.check_wait(r)
                self.assertIn(expected,r["blockingReasons"])

    def test_invalid_page_and_epic_mismatch(self):
        cases=[]
        missing=sample();missing.pop("H4")
        cases.append((missing,"M15_H1_H4_REQUIRED"))
        empty=sample();empty["H4"][0]["prices"]=[]
        cases.append((empty,"HISTORY_EMPTY"))
        excessive=sample();excessive["M15"][0]["prices"]*=335
        cases.append((excessive,"PRICE_PAGE_INVALID_OR_OVER_LIMIT"))
        epic=sample();epic["M15"][0]["epic"]="WRONG"
        cases.append((epic,"EPIC_RESPONSE_MISMATCH"))
        res=sample();res["H1"][0]["resolution"]="HOUR_4"
        cases.append((res,"RESOLUTION_RESPONSE_MISMATCH"))
        for packets,reason in cases:
            with self.subTest(reason=reason):
                r=review_capital_demo_pages(packets,EPIC,NOW)
                self.check_wait(r)
                self.assertIn(reason,r["blockingReasons"])

    def test_gaps_flagged_without_fabricating_market_sessions(self):
        packets=sample()
        packets["M15"][0]["prices"].pop(1)
        r=review_capital_demo_pages(packets,EPIC,NOW)
        self.check_wait(r)
        self.assertEqual(r["unverifiedSessionGapCounts"]["M15"],1)
        self.assertEqual(r["closedBarCounts"]["M15"],2)
        self.assertIn("INDEPENDENT_BROKER_SESSION_AND_SNAPSHOT_CLOCK_MISSING",r["blockingReasons"])

    def test_independent_bid_ask_h1_h4_m15_parity_and_missing_coverage(self):
        # Exactly 16 M15, four H1 and one H4, all CLOSED and aligned.
        # Fabricated in memory; never a provider or broker observation.
        start = dt.datetime(2026, 11, 16, 8, tzinfo=dt.timezone.utc)
        widths = {"M15": 900, "H1": 3600, "H4": 14400}
        counts = {"M15": 16, "H1": 4, "H4": 1}
        packets = {}
        for frame, count in counts.items():
            page = sample_page(frame, count)
            for i, row in enumerate(page["prices"]):
                row["snapshotTimeUTC"] = (
                    start + dt.timedelta(seconds=i*widths[frame])
                ).strftime("%Y-%m-%dT%H:%M:%S")
                for key, value in (("openPrice", 4000),
                                   ("highPrice", 4002),
                                   ("lowPrice", 3998),
                                   ("closePrice", 4001)):
                    row[key] = {"bid": value, "ask": value+0.3}
            packets[frame] = [page]
        good = review_capital_demo_pages(packets, EPIC, NOW)
        self.check_wait(good)
        self.assertTrue(good["fullCrossFrameCoverageVerified"])
        self.assertEqual(good["h4FromH1BidAskParity"], {
            "fullyCoveredMatched": 1, "fullyCoveredDisagreed": 0,
            "notFullyCovered": 0
        })
        self.assertEqual(good["crossFrameBidAskParity"], {
            "H1": {"fullyCoveredMatched": 4, "fullyCoveredDisagreed": 0,
                   "notFullyCovered": 0},
            "H4": {"fullyCoveredMatched": 1, "fullyCoveredDisagreed": 0,
                   "notFullyCovered": 0}
        })
        self.assertNotIn("H1_H4_M15_BID_ASK_AGGREGATION_MISMATCH",
                         good["blockingReasons"])

        corrupted = copy.deepcopy(packets)
        corrupted["M15"][0]["prices"][4]["highPrice"] = {
            "bid": 4004, "ask": 4004.3
        }
        bad = review_capital_demo_pages(corrupted, EPIC, NOW)
        self.check_wait(bad)
        self.assertFalse(bad["fullCrossFrameCoverageVerified"])
        self.assertEqual(bad["crossFrameBidAskParity"]["H1"]["fullyCoveredDisagreed"], 1)
        self.assertEqual(bad["crossFrameBidAskParity"]["H4"]["fullyCoveredDisagreed"], 1)
        self.assertIn("H1_H4_M15_BID_ASK_AGGREGATION_MISMATCH", bad["blockingReasons"])

        partial = copy.deepcopy(packets)
        partial["M15"][0]["prices"].pop(4)
        incomplete = review_capital_demo_pages(partial, EPIC, NOW)
        self.check_wait(incomplete)
        self.assertFalse(incomplete["fullCrossFrameCoverageVerified"])
        self.assertEqual(incomplete["crossFrameBidAskParity"]["H1"]["notFullyCovered"], 1)
        self.assertEqual(incomplete["crossFrameBidAskParity"]["H4"]["notFullyCovered"], 1)
        self.assertIn("H1_H4_M15_BID_ASK_COVERAGE_INCOMPLETE",
                      incomplete["blockingReasons"])
        self.assertFalse(incomplete["dataRightsVerified"])
        self.assertFalse(incomplete["orderEndpointsSupported"])
        # Even with partial M15 history, independently compare the
        # original H1/H4 BID and ASK OHLC. Missing M15 is NOT repaired.
        self.assertEqual(incomplete["h4FromH1BidAskParity"]["fullyCoveredMatched"], 1)

        direct_bad = copy.deepcopy(partial)
        direct_bad["H4"][0]["prices"][0]["highPrice"]["ask"] = 4004.3
        independent = review_capital_demo_pages(direct_bad, EPIC, NOW)
        self.check_wait(independent)
        self.assertEqual(independent["crossFrameBidAskParity"]["H4"]["notFullyCovered"], 1)
        self.assertEqual(independent["h4FromH1BidAskParity"]["fullyCoveredDisagreed"], 1)
        self.assertIn("H4_H1_DIRECT_BID_ASK_AGGREGATION_MISMATCH",
                      independent["blockingReasons"])
        self.assertFalse(independent["fullCrossFrameCoverageVerified"])

        missing_hour = copy.deepcopy(packets)
        missing_hour["H1"][0]["prices"].pop(1)
        no_hour = review_capital_demo_pages(missing_hour, EPIC, NOW)
        self.check_wait(no_hour)
        self.assertEqual(no_hour["h4FromH1BidAskParity"]["notFullyCovered"], 1)
        self.assertIn("H4_H1_DIRECT_BID_ASK_COVERAGE_INCOMPLETE",
                      no_hour["blockingReasons"])
        self.assertFalse(no_hour["fullCrossFrameCoverageVerified"])

    def test_request_blueprint_demo_only_not_executable(self):
        blueprint=demo_price_get_blueprint(EPIC,"M15",NOW-dt.timedelta(days=1),NOW)
        self.assertEqual(blueprint["baseUrl"],DEMO_BASE_URL)
        self.assertEqual(blueprint["path"],"/api/v1/prices/"+EPIC)
        self.assertEqual(blueprint["method"],"GET")
        self.assertEqual(blueprint["query"]["resolution"],"MINUTE_15")
        self.assertEqual(blueprint["query"]["max"],1000)
        self.assertFalse(blueprint["enabled"])
        self.assertFalse(blueprint["containsCredentials"])
        self.assertEqual(blueprint["providerRequestsMade"],0)
        with self.assertRaisesRegex(ValueError,"INVALID_HISTORY_RANGE"):
            demo_price_get_blueprint(EPIC,"M15",NOW,NOW)
        with self.assertRaisesRegex(ValueError,"UNSUPPORTED_RESOLUTION"):
            demo_price_get_blueprint(EPIC,"M5",NOW-dt.timedelta(days=1),NOW)

    def test_utc_as_of_and_epic_are_mandatory(self):
        for now in (NOW.replace(tzinfo=None),"2026-11-16T14:15:00+02:00"):
            r=review_capital_demo_pages(sample(),EPIC,now)
            self.check_wait(r)
            self.assertIn("AS_OF_EXPLICIT_UTC_REQUIRED",r["blockingReasons"])
        for epic in ("","../live","GOLD?apiKey=secret"):
            r=review_capital_demo_pages(sample(),epic,NOW)
            self.check_wait(r)
            self.assertIn("BROKER_EPIC_UNVERIFIED",r["blockingReasons"])


if __name__=="__main__":
    unittest.main()
