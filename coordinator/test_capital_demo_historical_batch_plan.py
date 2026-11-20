"""Offline-only Capital Demo historical batch planning contract tests."""
import copy
import datetime as dt
import unittest

from capital_demo_historical_batch_plan import plan_demo_closed_history
from capital_demo_offline_adapter import DEMO_BASE_URL

EPIC = "TEST.GOLD.EPIC"
START = "2026-11-08T00:00:00Z"
END = "2026-11-18T00:00:00Z"
ASOF = "2026-11-20T12:00:00Z"
WIDTHS = {"M15": 900, "H1": 3600, "H4": 14400}
RES = {"M15": "MINUTE_15", "H1": "HOUR", "H4": "HOUR_4"}


class CapitalInertHistoryPlanTests(unittest.TestCase):
    def assert_wait(self, p):
        self.assertEqual(p["signal"], "WAIT")
        for k in ("executable", "researchEligible", "paperOrdersAllowed",
                  "liveOrdersAllowed", "credentialsUsed", "sourceRightsVerified",
                  "kycRequiredNow", "connected"):
            self.assertIs(p[k], False, k)
        self.assertEqual(p["providerRequestsMade"], 0)
        self.assertEqual(p["brokerOrdersSent"], 0)

    def test_exact_partition_and_no_network_or_trade_permissions(self):
        p = plan_demo_closed_history(EPIC, START, END, ASOF)
        self.assert_wait(p)
        self.assertEqual(p["status"], "INERT_PLAN_ONLY")
        self.assertFalse(p["autoExecute"])
        self.assertFalse(p["orderRouteAllowed"])
        self.assertFalse(p["liveAccountHostAllowed"])
        self.assertEqual(p["lastUserAction"], "DEFER_KYC_UNTIL_APPROVED_FINAL_CONNECTION")
        self.assertEqual(p["expectedClosedBarCounts"], {"M15": 960, "H1": 240, "H4": 60})
        self.assertEqual(p["requestCount"], 4)
        self.assertEqual([q["expectedClosedSlots"] for q in p["requests"]["M15"]], [900, 60])
        self.assertEqual(p["requests"]["M15"][0]["firstExpectedOpenUTC"], START)
        self.assertEqual(p["requests"]["M15"][-1]["expectedEndExclusiveUTC"], END)
        for frame, batches in p["requests"].items():
            previous = START
            width = WIDTHS[frame]
            for item in batches:
                r = item["request"]
                self.assertTrue(item["responseWindowMustBeVerified"])
                self.assertTrue(item["providerToBoundMayBeInclusive"])
                self.assertEqual(item["firstExpectedOpenUTC"], previous)
                self.assertEqual(r["method"], "GET")
                self.assertEqual(r["baseUrl"], DEMO_BASE_URL)
                self.assertEqual(r["path"], "/api/v1/prices/"+EPIC)
                self.assertEqual(r["query"]["resolution"], RES[frame])
                self.assertEqual(r["query"]["max"], 1000)
                self.assertFalse(r["enabled"])
                self.assertTrue(r["requiresExplicitCloudRights"])
                self.assertFalse(r["containsCredentials"])
                self.assertEqual(r["providerRequestsMade"], 0)
                self.assertEqual(r["query"]["from"]+"Z", previous)
                end_exclusive = dt.datetime.fromisoformat(
                    item["expectedEndExclusiveUTC"].replace("Z","+00:00")
                )
                requested_last_open_plus_one = end_exclusive - dt.timedelta(seconds=width-1)
                self.assertEqual(
                    r["query"]["to"]+"Z",
                    requested_last_open_plus_one.isoformat().replace("+00:00","Z")
                )
                self.assertLess(
                    dt.datetime.fromisoformat(r["query"]["to"]+"+00:00"),
                    end_exclusive
                )
                length = (dt.datetime.fromisoformat(item["expectedEndExclusiveUTC"].replace("Z","+00:00")) -
                          dt.datetime.fromisoformat(previous.replace("Z","+00:00"))).total_seconds()
                self.assertEqual(length, width*item["expectedClosedSlots"])
                self.assertLessEqual(item["expectedClosedSlots"], 900)
                previous = item["expectedEndExclusiveUTC"]
            self.assertEqual(previous, END)
            self.assertEqual(sum(x["expectedClosedSlots"] for x in batches),
                             p["expectedClosedBarCounts"][frame])

    def test_one_leftover_slot_has_explicit_end_and_no_ghost_price(self):
        p=plan_demo_closed_history(EPIC, START, END, ASOF, bars_per_call=17)
        self.assert_wait(p)
        self.assertEqual(p["status"], "INERT_PLAN_ONLY")
        self.assertEqual(p["expectedClosedBarCounts"]["M15"], 960)
        self.assertEqual(p["requests"]["M15"][-1]["expectedClosedSlots"], 8)
        self.assertEqual(p["requestCount"],
                         (960+16)//17+(240+16)//17+(60+16)//17)
        self.assertEqual(p["requests"]["H4"][-1]["expectedClosedSlots"], 9)

    def test_no_wide_unbounded_or_forward_requests(self):
        cases=[
            (dict(epic="GOLD/../../positions"),"UNVERIFIED_GOLD_EPIC"),
            (dict(epic=""),"UNVERIFIED_GOLD_EPIC"),
            (dict(epic="DEMO?token=secret"),"UNVERIFIED_GOLD_EPIC"),
            (dict(start_utc="2026-11-08T01:00:00Z"),"H4_GRID_BOUNDARIES_REQUIRED"),
            (dict(end_utc="2026-11-18T01:00:00Z"),"H4_GRID_BOUNDARIES_REQUIRED"),
            (dict(end_utc="2026-11-21T00:00:00Z"),"NONCLOSED_OR_INVERTED_RANGE"),
            (dict(start_utc=END),"NONCLOSED_OR_INVERTED_RANGE"),
            (dict(start_utc="2026-01-01T00:00:00Z"),"EXCESSIVE_HISTORY_WINDOW"),
            (dict(bars_per_call=1),"INVALID_INERT_CHUNK_SIZE"),
            (dict(bars_per_call=901),"INVALID_INERT_CHUNK_SIZE"),
            (dict(bars_per_call=True),"INVALID_INERT_CHUNK_SIZE"),
            (dict(bars_per_call=90.0),"INVALID_INERT_CHUNK_SIZE"),
            (dict(start_utc="2026-11-08T02:00:00+02:00"),"AS_OF_EXPLICIT_UTC_REQUIRED"),
            (dict(as_of_utc="not-a-time"),"AS_OF_EXPLICIT_UTC_REQUIRED")
        ]
        default={"epic":EPIC,"start_utc":START,"end_utc":END,"as_of_utc":ASOF}
        for change, reason in cases:
            with self.subTest(change=change):
                inputs=copy.deepcopy(default);inputs.update(change)
                v=plan_demo_closed_history(**{k:inputs[k] for k in default},
                  **({"bars_per_call":change["bars_per_call"]} if "bars_per_call" in change else {}))
                self.assert_wait(v)
                self.assertEqual(v["status"], "BLOCKED", v)
                self.assertEqual(v["reason"], reason)
                self.assertEqual(v["requests"], {})
                self.assertNotIn("secret", str(v).lower())

    def test_120_days_supported_for_preparation_no_replay(self):
        start="2026-06-01T00:00:00Z"
        end="2026-09-29T00:00:00Z" # 120d exact
        p=plan_demo_closed_history(EPIC,start,end,ASOF)
        self.assert_wait(p)
        self.assertEqual(p["status"],"INERT_PLAN_ONLY")
        self.assertEqual(p["expectedClosedBarCounts"]["M15"],11520)
        self.assertEqual(p["requestCount"],13+4+1)
        self.assertFalse(p["connected"])


if __name__=="__main__":
    unittest.main()
