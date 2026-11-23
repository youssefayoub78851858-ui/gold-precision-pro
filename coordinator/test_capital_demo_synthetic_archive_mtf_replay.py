"""Restart synthetic sealed BID/ASK pages on all three timeframes.

No provider network, trading, real broker data, market entitlements or
independent recovery claims; this is the data quality cutover rehearsal.
"""
import copy
import datetime as dt
import json
import os
import pathlib
import tempfile
import unittest

from capital_demo_historical_batch_plan import plan_demo_closed_history
from capital_demo_private_page_store import commit_fixture_page
from capital_demo_synthetic_archive_mtf_replay import replay_saved_synthetic_mtf

START = "2026-11-20T08:00:00Z"
END = "2026-11-20T12:00:00Z"
ASOF = "2026-11-20T12:12:00Z"
OBS = "2026-11-20T12:05:00Z"
EPIC = "TEST.GOLD.EPIC"
WIDTHS = {"M15": 15, "H1": 60, "H4": 240}
RESOLUTIONS = {"M15": "MINUTE_15", "H1": "HOUR", "H4": "HOUR_4"}


def stamp(minutes):
    when = dt.datetime(2026, 11, 20, 8, tzinfo=dt.timezone.utc)
    return (when + dt.timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%S")


def snapshot(i):
    open_value = 4000 + i * 0.25
    return {"open": open_value, "high": open_value + .30,
            "low": open_value - .15, "close": open_value + .15}


def raw_bar(start_minutes, value):
    row = {"snapshotTimeUTC": stamp(start_minutes)}
    for name, key in (("openPrice", "open"), ("highPrice", "high"),
                      ("lowPrice", "low"), ("closePrice", "close")):
        row[name] = {"bid": value[key], "ask": value[key] + .4}
    return row


def make_pages():
    m = [snapshot(i) for i in range(16)]
    def aggregate(parts):
        return {"open": parts[0]["open"], "high": max(x["high"] for x in parts),
                "low": min(x["low"] for x in parts),
                "close": parts[-1]["close"]}
    return {
        "M15": [raw_bar(i*15, bar) for i, bar in enumerate(m)],
        "H1": [raw_bar(i*60, aggregate(m[i*4:(i+1)*4])) for i in range(4)],
        "H4": [raw_bar(0, aggregate(m))]
    }


def plan():
    return plan_demo_closed_history(EPIC, START, END, ASOF)


class SyntheticMultiframeRestartTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.directory = pathlib.Path(temp.name)
        os.chmod(self.directory, 0o700)
        self.plan = plan()
        self.assertEqual(self.plan["status"], "INERT_PLAN_ONLY")
        self.assertEqual(self.plan["requestCount"], 3)
        self.assertEqual(self.plan["expectedClosedBarCounts"],
                         {"M15": 16, "H1": 4, "H4": 1})

    def save(self, *, pages=None):
        frames = make_pages() if pages is None else pages
        for frame in ("M15", "H1", "H4"):
            chunk = self.plan["requests"][frame][0]
            body = {"epic": EPIC,
                    "resolution": RESOLUTIONS[frame], "prices": frames[frame]}
            receipt = commit_fixture_page(
                chunk, body, self.directory, OBS,
                explicit_synthetic_rehearsal=True)
            self.assertEqual(receipt["storedRows"], len(frames[frame]))

    def assert_never_eligible(self, out):
        self.assertEqual(out["signal"], "WAIT")
        self.assertEqual(out["providerRequestsMade"], 0)
        self.assertEqual(out["ordersSent"], 0)
        for key in ("marketRightsVerified", "genuineProviderDataVerified",
                    "actualSessionCalendarVerified", "firstSeenExternallyAttested",
                    "independentOffsiteBackupVerified", "paperTradingAuthorized",
                    "realTradingAuthorized", "executable", "paperOrdersAllowed",
                    "liveOrdersAllowed"):
            self.assertFalse(out[key], key)
        printed = json.dumps(out)
        for secret in ("4000", "TEST.GOLD.EPIC", "C"*32, str(self.directory)):
            self.assertNotIn(secret, printed)

    def test_full_closed_both_sides_parity_and_restart_replay(self):
        self.save()
        out = replay_saved_synthetic_mtf(self.plan, self.directory)
        self.assert_never_eligible(out)
        self.assertEqual(out["status"], "SYNTHETIC_LOCAL_MTF_PARITY_VERIFIED_ONLY")
        self.assertEqual(out["validatedLocalPageCounts"],
                         {"M15": 1, "H1": 1, "H4": 1})
        self.assertEqual(out["receivedClosedCounts"],
                         {"M15": 16, "H1": 4, "H4": 1})
        self.assertEqual(out["unverifiedMissingUTCGridSlots"],
                         {"M15": 0, "H1": 0, "H4": 0})
        self.assertTrue(out["locallyMatchedBidAskH1H4"])
        self.assertTrue(out["sealedLocalRehearsalPagesVerified"])
        # Repeat independent read as a simulated process restart; never
        # mutate the archive, merge live feeds, or create paper trades.
        self.assertEqual(out, replay_saved_synthetic_mtf(self.plan,self.directory))
        self.assertEqual(len(list(self.directory.glob("capital-synthetic-page-*.json"))),3)

    def test_missing_synthetic_m15_constituent_never_qualifies_parity(self):
        frames = make_pages()
        frames["M15"].pop(3)
        self.save(pages=frames)
        out = replay_saved_synthetic_mtf(self.plan, self.directory)
        self.assert_never_eligible(out)
        self.assertEqual(out["status"], "INCOMPLETE_SYNTHETIC_LOCAL_REPLAY_ONLY")
        self.assertEqual(out["receivedClosedCounts"]["M15"], 15)
        self.assertEqual(out["unverifiedMissingUTCGridSlots"]["M15"], 1)
        self.assertFalse(out["locallyMatchedBidAskH1H4"])

    def test_conflicting_h1_full_bar_rejected_despite_valid_file_seal(self):
        frames = make_pages()
        frames["H1"][1]["highPrice"]["bid"] += 5
        frames["H1"][1]["highPrice"]["ask"] += 5
        self.save(pages=frames)
        out = replay_saved_synthetic_mtf(self.plan, self.directory)
        self.assert_never_eligible(out)
        self.assertEqual(out["status"], "BLOCKED")
        self.assertEqual(out["reason"], "CLOSED_BID_ASK_MTF_PARITY_OR_PAGES_REJECTED")
        self.assertFalse(out["sealedLocalRehearsalPagesVerified"])

    def test_missing_or_corrupted_or_bad_permissions_block_all(self):
        self.save()
        self.assertEqual(replay_saved_synthetic_mtf(
            self.plan, self.directory)["status"], "SYNTHETIC_LOCAL_MTF_PARITY_VERIFIED_ONLY")
        target = next(self.directory.glob("capital-synthetic-page-*.json"))
        original = target.read_bytes()
        target.write_bytes(original.replace(b"4000", b"4001", 1))
        failed = replay_saved_synthetic_mtf(self.plan, self.directory)
        self.assert_never_eligible(failed)
        self.assertEqual(failed["status"], "BLOCKED")
        target.write_bytes(original)
        os.chmod(target, 0o644)
        self.assertEqual(replay_saved_synthetic_mtf(
            self.plan, self.directory)["status"], "BLOCKED")
        os.chmod(target, 0o600)
        target.unlink()
        self.assertEqual(replay_saved_synthetic_mtf(
            self.plan, self.directory)["status"], "BLOCKED")

    def test_wrong_real_epic_spoofed_plan_and_no_archive(self):
        out = replay_saved_synthetic_mtf(self.plan, self.directory)
        self.assert_never_eligible(out)
        self.assertEqual(out["status"], "BLOCKED")
        fake = copy.deepcopy(self.plan)
        for frame in fake["requests"]:
            for chunk in fake["requests"][frame]:
                chunk["request"]["path"] = "/api/v1/prices/REAL.GOLD.EPIC"
        spoofed = replay_saved_synthetic_mtf(fake, self.directory)
        self.assert_never_eligible(spoofed)
        self.assertEqual(spoofed["reason"], "REAL_OR_UNVERIFIED_EPIC_REJECTED")
        altered = copy.deepcopy(self.plan)
        altered["expectedClosedBarCounts"]["M15"] += 1
        self.assertEqual(replay_saved_synthetic_mtf(
            altered, self.directory)["reason"], "UNTRUSTED_OR_CHANGED_HISTORY_PLAN")


if __name__ == "__main__":
    unittest.main()
