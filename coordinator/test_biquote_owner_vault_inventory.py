"""Isolated, synthetic-only tests for read-only owner vault inventory."""
import json
import os
import pathlib
import socket
import tempfile
import unittest
from unittest.mock import patch

from biquote_private_forward_vault import FILE, ingest
from biquote_owner_vault_inventory import inspect_private_vault
from test_biquote_private_forward_vault import NOW, iso, sample


class OwnerInventoryTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="gpp-owner-vault-inventory-")
        self.addCleanup(tmp.cleanup)
        self.root = pathlib.Path(tmp.name)
        self.vault = self.root / "private-vault"
        self.vault.mkdir(mode=0o700)

    def create_synthetic(self):
        with patch.object(socket, "socket",
                          side_effect=AssertionError("NO_NETWORK_ALLOWED")):
            ingest(self.vault, sample(NOW), received_utc=iso(NOW))

    def assert_safe(self, data):
        self.assertEqual(data["mode"], "GPP_OWNER_VAULT_INVENTORY_READONLY_V1")
        self.assertEqual(data["signal"], "WAIT")
        self.assertFalse(data["executable"])
        for key in ("independentOffsiteBackupVerified", "sourceRightsVerified",
                    "reviewDeployApproved", "coordinatorRestartApproved",
                    "rawPricesPrinted"):
            self.assertFalse(data[key])
        self.assertEqual(data["sourceFileWrites"], 0)
        self.assertEqual(data["providerRequestsMade"], 0)
        self.assertEqual(data["brokerOrdersSent"], 0)
        output = json.dumps(data)
        for secret in (str(self.root), str(self.vault), '"bid"', '"ask"',
                       '"open"', '"close"', "3900.", "API_SECRET"):
            self.assertNotIn(secret, output)

    def test_existing_sealed_synthetic_vault_reports_counts_without_prices(self):
        self.create_synthetic()
        original = (self.vault / FILE).read_bytes()
        with patch.object(socket, "socket",
                          side_effect=AssertionError("NO_NETWORK_ALLOWED")):
            result = inspect_private_vault(self.vault, data_volume=self.root)
        self.assert_safe(result)
        self.assertEqual(result["status"],
                         "PRIVATE_SOURCE_VALIDATED_BACKUP_STILL_REQUIRED")
        self.assertTrue(result["ownerOnlyVaultPresent"])
        self.assertTrue(result["sealedVaultValidated"])
        self.assertGreater(result["quoteObservations"], 0)
        self.assertEqual((self.vault / FILE).read_bytes(), original)

    def test_missing_empty_corrupt_source_never_claims_backup(self):
        for variant in ("missing", "empty", "corrupt"):
            if variant == "empty":
                self.vault.joinpath(FILE).write_bytes(b"")
            if variant == "corrupt":
                self.vault.joinpath(FILE).write_bytes(b"invalid sealed archive")
            result = inspect_private_vault(self.vault, data_volume=self.root)
            self.assert_safe(result)
            self.assertFalse(result["sealedVaultValidated"])
            self.assertEqual(result["status"], "BLOCKED")

    def test_symlink_and_public_permissions_rejected(self):
        self.create_synthetic()
        os.chmod(self.vault, 0o755)
        result = inspect_private_vault(self.vault, data_volume=self.root)
        self.assert_safe(result)
        self.assertEqual(result["reason"], "PRIVATE_VAULT_DIR_INSECURE")
        os.chmod(self.vault, 0o700)
        destination = self.root / "symlink"
        destination.symlink_to(self.vault, target_is_directory=True)
        result = inspect_private_vault(destination, data_volume=self.root)
        self.assert_safe(result)
        self.assertEqual(result["reason"], "PRIVATE_VAULT_PATH_SYMLINK")

    def test_missing_config_or_outside_root_fails_closed(self):
        for config in ("", None, "/", "/tmp/stranger", self.root):
            result = inspect_private_vault(config, data_volume=self.root)
            self.assert_safe(result)
            self.assertEqual(result["status"], "BLOCKED")

    def test_changed_inode_during_read_is_not_verified(self):
        self.create_synthetic()
        from biquote_owner_vault_inventory import load_vault as original_load
        def race(directory):
            data = original_load(directory)
            p = self.vault / FILE
            content = p.read_bytes()
            p.unlink()
            p.write_bytes(content)
            os.chmod(p, 0o600)
            return data
        with patch("biquote_owner_vault_inventory.load_vault", side_effect=race):
            result = inspect_private_vault(self.vault, data_volume=self.root)
        self.assert_safe(result)
        self.assertEqual(result["reason"], "SEALED_VAULT_CHANGED_DURING_READ")


if __name__ == "__main__":
    unittest.main()
