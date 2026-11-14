"""Compile a synthetic-only C++ source and test it against the existing
FXCM native -> shared research WAIT bridge. No SDK linked or loaded.
"""
import datetime as dt
import json
import pathlib
import subprocess
import tempfile
import unittest

from fxcm_native_pipeline_bridge import review_fxcm_native_standby

ROOT = pathlib.Path(__file__).resolve().parent
NOW = dt.datetime(2026, 11, 13, 16, 0, tzinfo=dt.timezone.utc)

class FXCMCppToResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="fxcm-offline-cpp-")
        cls.exe = pathlib.Path(cls.tmp.name) / "fixture"
        subprocess.run(["g++", "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror",
                        str(ROOT / "fxcm_cpp_fixture_emitter.cpp"), "-o", str(cls.exe)],
                       check=True, capture_output=True, text=True, timeout=45)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def packet(self, mode="--fixture"):
        run = subprocess.run([str(self.exe), mode], check=True, timeout=5,
                             capture_output=True, text=True)
        packet = json.loads(run.stdout)
        self.assertEqual(packet["dataOrigin"], "SYNTHETIC_CPP_OFFLINE_TEST_ONLY")
        return packet

    def guarded(self, mode="--fixture"):
        report = review_fxcm_native_standby(self.packet(mode), NOW)
        self.assertEqual(report["status"], "WAIT_FXCM_NATIVE_INTAKE_STANDBY")
        self.assertEqual(report["signal"], "WAIT")
        self.assertEqual(report["researchCandidate"], "NONE")
        for key in ("executable", "researchEligible", "paperRunning",
                    "paperOrdersAllowed", "sourcePolicyAuthorized",
                    "sdkLoaded", "rawCandlesIncluded", "tradingEnabled"):
            self.assertIs(report[key], False, key)
        self.assertEqual(report["providerRequestsMade"], 0)
        self.assertEqual(report["credentialsRead"], 0)
        self.assertEqual(set(report["engines"].values()), {"SKIPPED"})
        serialized = json.dumps(report)
        self.assertNotIn('"bid"', serialized)
        self.assertNotIn('"ask"', serialized)
        return report

    def test_cpp_to_existing_research_gate_remains_wait(self):
        report = self.guarded()
        self.assertIs(report["structuralAuditPassed"], True, report["blockingReasons"])
        self.assertEqual(report["frameCounts"], {"M15": 16, "H1": 4, "H4": 1})
        self.assertEqual(report["checkedOverlaps"], {"H1": 4, "H4": 1})
        self.assertEqual(report["sharedResearchIntakeStatus"], "WAIT_INTAKE_BLOCKED")

    def test_cpp_forged_permissions_cannot_authorize(self):
        report = self.guarded("--fixture-forged-rights")
        self.assertIs(report["structuralAuditPassed"], True)
        self.assertIn("FXCM_EULA_AND_PRIVATE_CLOUD_RIGHTS_UNVERIFIED",
                      report["blockingReasons"])

    def test_cpp_bad_bars_are_rejected(self):
        for mode, reason in (
            ("--fixture-crossed", "CROSSED_BID_ASK"),
            ("--fixture-stale", "STALE_LATEST_CLOSED_CANDLE"),
            ("--fixture-missing-h1", "MISSING_HIGHER_TIMEFRAME_BAR"),
            ("--fixture-unclosed", "UNALIGNED_OR_UNCLOSED_CANDLE"),
            ("--fixture-gap", "PARTIAL_M15_COVERAGE"),
        ):
            with self.subTest(mode=mode):
                report = self.guarded(mode)
                self.assertIs(report["structuralAuditPassed"], False)
                self.assertIn(reason, report["blockingReasons"])
                self.assertEqual(report["sharedResearchIntakeStatus"],
                                 "WAIT_INTAKE_BLOCKED")

    def test_unknown_live_mode_is_not_supported(self):
        run = subprocess.run([str(self.exe), "--connect-live"], timeout=5,
                             capture_output=True, text=True)
        self.assertEqual(run.returncode, 2)
        self.assertEqual(run.stdout, "")

    def test_cpp_output_is_byte_for_byte_reproducible(self):
        args = [str(self.exe), "--fixture"]
        self.assertEqual(subprocess.check_output(args, timeout=5),
                         subprocess.check_output(args, timeout=5))

if __name__ == "__main__":
    unittest.main()
