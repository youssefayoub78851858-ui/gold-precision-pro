"""Private sealed-archive one-shot copy drills; SYNTHETIC vaults only.

No Render filesystem, remote uploads, subscriptions or trading.
The positive test copies across two folders on the SAME temporary device,
which must NEVER be presented as independently durable offsite recovery.
"""
import json
import os
import pathlib
import shutil
import socket
import tempfile
import unittest
from unittest.mock import patch

from biquote_private_forward_vault import FILE, ingest, load_vault
from biquote_owner_private_copy_once import check, copy_once
from test_biquote_private_forward_vault import NOW, iso, sample


class OwnerOnlyArchiveCopy(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gpp-private-copy-drill-")
        self.addCleanup(self.temp.cleanup)
        root = pathlib.Path(self.temp.name)
        self.src, self.backup = root / "original", root / "recovery"
        self.src.mkdir(mode=0o700)
        self.backup.mkdir(mode=0o700)
        with patch.object(socket, "socket",
                          side_effect=AssertionError("NO_NETWORK")):
            ingest(self.src, sample(NOW), received_utc=iso(NOW))

    def safe(self, result):
        self.assertEqual(result["mode"], "BIQUOTE_OWNER_PRIVATE_COPY_ONCE_NO_DEPLOY_V1")
        self.assertEqual(result["signal"], "WAIT")
        self.assertFalse(result["executable"])
        for key in ("externallyDurableBackupVerified", "reviewDeployApproved",
                    "coordinatorRestartApproved", "sourceRightsVerified",
                    "rawPricesPrinted"):
            self.assertIs(result[key], False)
        self.assertEqual(result["providerRequestsMade"], 0)
        self.assertEqual(result["brokerOrdersSent"], 0)
        payload = json.dumps(result)
        for disallowed in (str(self.src), str(self.backup), '"open"',
                           '"close"', '"bid"', '"ask"', "3900.", "api_key"):
            self.assertNotIn(disallowed, payload)

    def test_default_preflight_never_copies_and_cannot_approve_deploy(self):
        original = (self.src / FILE).read_bytes()
        with patch.object(socket, "socket",
                          side_effect=AssertionError("NO_NETWORK")):
            dry = check(self.src, self.backup)
            refused = copy_once(self.src, self.backup,
                                operator_approved=False, now_utc=NOW)
        self.safe(dry); self.safe(refused)
        self.assertEqual(dry["status"], "PRIVATE_SOURCE_PRECHECK_ONLY_NO_BACKUP")
        self.assertEqual(refused["reason"],
                         "EXPLICIT_OPERATOR_COPY_APPROVAL_REQUIRED")
        self.assertFalse((self.backup / FILE).exists())
        self.assertEqual((self.src / FILE).read_bytes(), original)

    def test_explicit_private_copy_is_byte_exact_and_restorable_but_not_offsite(self):
        before = (self.src / FILE).read_bytes()
        with patch.object(socket, "socket",
                          side_effect=AssertionError("NO_NETWORK")):
            done = copy_once(self.src, self.backup,
                             operator_approved=True, now_utc=NOW)
        self.safe(done)
        self.assertEqual(done["status"], "LOCAL_OWNER_ONLY_SEALED_COPY_VERIFIED")
        self.assertIs(done["privateCopyVerified"], True)
        self.assertIs(done["isolatedRestorePassed"], True)
        self.assertIs(done["sameDeviceDetected"], True)
        self.assertGreater(done["quoteObservationsCopied"], 0)
        self.assertEqual(before, (self.backup / FILE).read_bytes())
        self.assertEqual(before, (self.src / FILE).read_bytes())
        self.assertEqual(load_vault(self.src), load_vault(self.backup))
        self.assertEqual((self.backup / FILE).stat().st_mode & 0o077, 0)
        self.assertFalse(any(".sealed-private-copy-" in f.name
                             for f in self.backup.iterdir()))
        second = copy_once(self.src, self.backup,
                           operator_approved=True, now_utc=NOW)
        self.safe(second)
        self.assertFalse(second["privateCopyVerified"])
        self.assertEqual(before, (self.backup / FILE).read_bytes())

    def test_refuses_existing_backup_or_symlink_without_writing(self):
        target = self.backup / FILE
        target.write_bytes(b"NO_OVERWRITE")
        result = copy_once(self.src, self.backup,
                           operator_approved=True, now_utc=NOW)
        self.safe(result)
        self.assertEqual(target.read_bytes(), b"NO_OVERWRITE")
        target.unlink()
        target.symlink_to(self.src / FILE)
        result = copy_once(self.src, self.backup,
                           operator_approved=True, now_utc=NOW)
        self.safe(result)
        self.assertTrue(target.is_symlink())
        self.assertEqual((self.src / FILE).read_bytes(), target.read_bytes())

    def test_corrupt_source_or_owner_permissions_refused(self):
        original = (self.src / FILE).read_bytes()
        (self.src / FILE).write_bytes(b"NOT_A_VALID_SEALED_VAULT")
        out = copy_once(self.src, self.backup,
                        operator_approved=True, now_utc=NOW)
        self.safe(out)
        self.assertFalse((self.backup / FILE).exists())
        (self.src / FILE).write_bytes(original)
        os.chmod(self.backup, 0o755)
        out = copy_once(self.src, self.backup,
                        operator_approved=True, now_utc=NOW)
        self.safe(out)
        self.assertFalse((self.backup / FILE).exists())

    def test_directory_fsync_failure_blocks_and_cleans_unverified_backup(self):
        original = (self.src / FILE).read_bytes()
        # No "successful copy" may be claimed when the backup filename
        # has not been made crash-durable, even if bytes matched earlier.
        with patch("biquote_owner_private_copy_once._sync_directory",
                   side_effect=OSError("synthetic directory fsync failure")):
            result = copy_once(self.src, self.backup,
                               operator_approved=True, now_utc=NOW)
        self.safe(result)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["privateCopyVerified"])
        self.assertEqual((self.src / FILE).read_bytes(), original)
        self.assertEqual(list(self.backup.iterdir()), [])

    def test_recovery_failure_removes_only_this_attempt_copy(self):
        original = (self.src / FILE).read_bytes()
        with patch("biquote_owner_private_copy_once.rehearse_restore",
                   return_value={"status": "BLOCKED",
                                 "isolatedLocalRestorePassed": False}):
            result = copy_once(self.src, self.backup,
                               operator_approved=True, now_utc=NOW)
        self.safe(result)
        self.assertFalse((self.backup / FILE).exists())
        self.assertEqual((self.src / FILE).read_bytes(), original)
        self.assertEqual(list(self.backup.iterdir()), [])

    def test_utc_and_identical_directory_fail_closed(self):
        self.safe(copy_once(self.src, self.backup, operator_approved=True,
                            now_utc=NOW.replace(tzinfo=None)))
        self.safe(copy_once(self.src, self.src, operator_approved=True,
                            now_utc=NOW))
        self.assertEqual((self.backup / FILE).exists(), False)
        self.assertEqual((self.src / FILE).exists(), True)


if __name__ == "__main__":
    unittest.main()
