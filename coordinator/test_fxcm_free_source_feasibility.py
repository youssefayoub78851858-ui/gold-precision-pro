"""FXCM no-cost source viability: static, fail-closed, no vendor calls."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fxcm_free_source_feasibility import assess_fxcm_free_source


class FxcmDecisionAudit(unittest.TestCase):
    def assert_wait(self, result):
        self.assertEqual(result["decision"], "NO_GO_UNTIL_PROVEN")
        self.assertEqual(result["signal"], "WAIT")
        self.assertFalse(result["executable"])
        self.assertFalse(result["researchEligible"])
        self.assertFalse(result["readyForPaper"])
        self.assertFalse(result["readyForTrading"])
        self.assertEqual(result["payments"], 0)
        self.assertEqual(result["secretReads"], 0)
        self.assertEqual(result["sourceRequestsMade"], 0)
        self.assertEqual(result["vendorLogins"], 0)
        self.assertTrue(result["blockingReasons"])

    def test_current_python311_has_no_verified_public_compatible_linux_wheel(self):
        r = assess_fxcm_free_source(python_version=(3, 11))
        self.assert_wait(r)
        self.assertEqual(r["currentPythonABI"], "cp311")
        self.assertFalse(r["publishedLinuxWheelMatchesCurrentPython"])
        self.assertTrue(any("3_11" in code for code in r["blockingReasons"]))

    def test_legacy_python37_wheel_does_not_authorize_demo_or_trades(self):
        r = assess_fxcm_free_source(python_version=(3, 7))
        self.assert_wait(r)
        self.assertTrue(r["publishedLinuxWheelMatchesCurrentPython"])
        self.assertFalse(r["unverifiedLiveConditions"]["xauusdOnOurDemoAccount"])
        self.assertFalse(r["unverifiedLiveConditions"]["safeReadOnlyAuthentication"])
        self.assertIn("FXCM_LEGACY_PYTHON_3_7_RUNTIME_ISOLATION_NOT_TESTED",
                      r["blockingReasons"])

    def test_missing_or_unexpected_container_blocks(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "coordinator").mkdir()
            (root / "coordinator" / "Dockerfile").write_text("FROM busybox\n")
            x = assess_fxcm_free_source(root, python_version=(3, 7))
            self.assert_wait(x)
            self.assertFalse(x["reviewDockerShapeVerified"])
            self.assertIn("CURRENT_REVIEW_DOCKERFILE_NOT_VERIFIED", x["blockingReasons"])

    def test_unknown_python_versions_are_not_allowlisted(self):
        r = assess_fxcm_free_source(python_version=(3, 12))
        self.assert_wait(r)
        self.assertFalse(r["publishedLinuxWheelMatchesCurrentPython"])
        with self.assertRaises(ValueError):
            assess_fxcm_free_source(python_version=(True, 7))
        with self.assertRaises(ValueError):
            assess_fxcm_free_source(python_version=(3, "11"))

    def test_no_network_and_no_credentials_ever_used(self):
        with patch("socket.socket", side_effect=AssertionError("Forbidden network")):
            r = assess_fxcm_free_source(python_version=(3, 11))
        self.assert_wait(r)
        self.assertFalse(r["unverifiedLiveConditions"]["modernLinuxRuntimeSuccessfullyTested"])
        self.assertNotIn("password=", repr(r))
        self.assertNotIn("token=", repr(r))


if __name__ == "__main__":
    unittest.main()
