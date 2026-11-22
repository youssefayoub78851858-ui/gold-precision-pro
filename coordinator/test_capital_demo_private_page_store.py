"""Offline Capital Demo synthetic page -> durable private file -> restart audit.

All quote rows are fabricated. No external credentials, provider calls,
real market-data rights or trade/paper activation.
"""
import copy
import json
import os
import pathlib
import stat
import tempfile
import unittest
from unittest.mock import patch

from capital_demo_private_page_store import commit_fixture_page, verify_fixture_page
from capital_demo_private_get_boundary import (
    inspect_private_demo_page, ENABLE_ENV, RIGHTS_ENV, ENABLE_VALUE
)
from capital_demo_https_transport import demo_https_price_get
from test_capital_demo_private_get_boundary import request, quote
from test_capital_demo_private_end_to_end import FakeOpener

PAGE = {"epic": "TEST.GOLD.EPIC", "resolution": "MINUTE_15",
        "prices": [quote("2026-11-20T08:00:00"), quote("2026-11-20T08:15:00")]}
OBS = "2026-11-20T12:04:00Z"
NEXT = "2026-11-20T13:00:00Z"


class CapitalSyntheticArchiveRehearsal(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.d = pathlib.Path(self.temp.name)
        os.chmod(self.d, 0o700)

    def sink(self, page, *, observed=OBS, directory=None, enabled=True):
        return commit_fixture_page(request(), page, self.d if directory is None else directory,
                                   observed, explicit_synthetic_rehearsal=enabled)

    def files(self):
        return list(self.d.glob("capital-synthetic-page-*.json"))

    def test_default_disabled_no_file_or_provider(self):
        with self.assertRaisesRegex(ValueError, "EXPLICITLY_DISABLED"):
            self.sink(PAGE, enabled=False)
        self.assertEqual(self.files(), [])
        self.assertEqual(verify_fixture_page(request(), self.d)["status"],
                         "BLOCKED_LOCAL_SYNTHETIC_ARCHIVE_NOT_VERIFIED")

    def test_mock_https_get_to_persistent_private_file_and_restart(self):
        opener = FakeOpener(copy.deepcopy(PAGE))
        with patch.dict(os.environ, {ENABLE_ENV: ENABLE_VALUE,
                                      RIGHTS_ENV: ENABLE_VALUE}):
            out = inspect_private_demo_page(
                request(), cst="C"*32, security_token="S"*32,
                explicit_operator_approval=True,
                transport=lambda m, u, h: demo_https_price_get(
                    m, u, h, opener=opener, explicit_operator_approval=True),
                deliver_private=self.sink)
        self.assertEqual(len(opener.calls), 1)
        self.assertEqual(out["status"], "PRIVATE_DEMO_GEOMETRY_ONLY_NOT_ADMITTED")
        self.assertEqual(out["signal"], "WAIT")
        self.assertFalse(out["researchEligible"])
        self.assertFalse(out["paperOrdersAllowed"])
        self.assertFalse(out["sourceRightsIndependentlyAttested"])
        self.assertEqual(out["pageRowsChecked"], 2)
        self.assertEqual(len(self.files()), 1)
        archive = self.files()[0]
        st = archive.lstat()
        self.assertTrue(stat.S_ISREG(st.st_mode))
        self.assertEqual(stat.S_IMODE(st.st_mode), 0o600)
        self.assertEqual(st.st_nlink, 1)
        stored = json.loads(archive.read_bytes())
        self.assertEqual(stored["payload"]["firstLocalTestReceiptUTC"], OBS)
        self.assertEqual(len(stored["payload"]["rows"]), 2)
        audit = verify_fixture_page(request(), self.d)
        self.assertEqual(audit["status"], "SYNTHETIC_PAGE_LOCAL_RESTORE_VERIFIED_ONLY")
        self.assertEqual(audit["rowsVerified"], 2)
        self.assertFalse(audit["brokerRightsVerified"])
        self.assertFalse(audit["realBrokerPageVerified"])
        self.assertFalse(audit["independentBackupVerified"])
        self.assertEqual(audit["signal"], "WAIT")
        self.assertFalse(audit["executable"])
        self.assertFalse(audit["paperOrdersAllowed"])
        self.assertFalse(audit["liveOrdersAllowed"])
        for sensitive in ("4000", "C"*32, "S"*32, str(archive)):
            self.assertNotIn(sensitive, json.dumps(audit))
            self.assertNotIn(sensitive, json.dumps(out))

    def test_idempotent_no_overwrite_first_receipt_and_conflicting_page(self):
        self.assertEqual(self.sink(PAGE), {"committed": True, "storedRows": 2})
        target = self.files()[0]
        before = target.read_bytes()
        self.assertEqual(self.sink(PAGE, observed=NEXT),
                         {"committed": True, "storedRows": 2})
        self.assertEqual(target.read_bytes(), before)
        changed = copy.deepcopy(PAGE)
        changed["prices"][1]["closePrice"]["bid"] = 4000.2
        with self.assertRaisesRegex(ValueError, "CONFLICT_NEVER_OVERWRITE"):
            self.sink(changed)
        self.assertEqual(target.read_bytes(), before)
        self.assertEqual(len(self.files()), 1)

    def test_corrupt_seal_or_price_geometry_never_accepted_on_restore(self):
        self.sink(PAGE)
        target = self.files()[0]
        stored = json.loads(target.read_bytes())
        stored["payload"]["rows"][0]["bid"]["close"] = 2000
        target.write_text(json.dumps(stored))
        self.assertEqual(verify_fixture_page(request(), self.d)["status"],
                         "BLOCKED_LOCAL_SYNTHETIC_ARCHIVE_NOT_VERIFIED")
        with self.assertRaisesRegex(ValueError, "PRIVATE_ARCHIVE_HASH_MISMATCH"):
            self.sink(PAGE)

    def test_reject_symlink_world_readable_and_wrong_epic(self):
        os.chmod(self.d, 0o755)
        with self.assertRaisesRegex(ValueError, "PRIVATE_DIRECTORY_OWNER_ONLY_REQUIRED"):
            self.sink(PAGE)
        os.chmod(self.d, 0o700)
        wrong = copy.deepcopy(PAGE)
        wrong["epic"] = "NOT.GOLD.EPIC"
        with self.assertRaisesRegex(ValueError, "TEST_PRICE_PAGE_IDENTITY_REQUIRED"):
            self.sink(wrong)
        self.sink(PAGE)
        original = self.files()[0]
        other = self.d / "private-target"
        other.write_bytes(original.read_bytes())
        original.unlink()
        original.symlink_to(other)
        with self.assertRaisesRegex(ValueError, "PRIVATE_ARCHIVE_FILE_UNSAFE"):
            self.sink(PAGE)
        self.assertEqual(verify_fixture_page(request(), self.d)["status"],
                         "BLOCKED_LOCAL_SYNTHETIC_ARCHIVE_NOT_VERIFIED")

    def test_reject_unclosed_crossed_duplicate_or_unplanned_page(self):
        failures = []
        crossed = copy.deepcopy(PAGE)
        crossed["prices"][0]["openPrice"]["ask"] = 3999
        failures.append(crossed)
        duplicated = copy.deepcopy(PAGE)
        duplicated["prices"][1]["snapshotTimeUTC"] = "2026-11-20T08:00:00"
        failures.append(duplicated)
        outside = copy.deepcopy(PAGE)
        outside["prices"][1]["snapshotTimeUTC"] = "2026-11-20T12:00:00"
        failures.append(outside)
        leaked = copy.deepcopy(PAGE)
        leaked["prices"][0]["token"] = "SECRET"
        failures.append(leaked)
        for value in failures:
            with self.subTest(test=value["prices"][-1]["snapshotTimeUTC"]):
                with self.assertRaises(ValueError):
                    self.sink(value)
        with self.assertRaisesRegex(ValueError, "REAL_BROKER_EPIC_NEVER_ALLOWED"):
            forged = request()
            forged["request"]["path"] = "/api/v1/prices/REAL.GOLD.EPIC"
            commit_fixture_page(forged, PAGE, self.d, OBS,
                                explicit_synthetic_rehearsal=True)
        self.assertEqual(self.files(), [])


if __name__ == "__main__":
    unittest.main()
