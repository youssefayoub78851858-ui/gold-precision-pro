"""Native fixture subprocess supervision: no network, orders, SDK or secrets."""
import datetime as dt
import hashlib
import pathlib
import subprocess
import tempfile
import unittest
from fxcm_cpp_offline_supervisor import review_pinned_cpp_fixture

ROOT=pathlib.Path(__file__).resolve().parent
NOW=dt.datetime(2026,11,13,16,0,tzinfo=dt.timezone.utc)

class IsolatedFXCMCppSupervisor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix="fxcm-supervisor-")
        cls.binary=pathlib.Path(cls.temp.name)/"fixture"
        subprocess.run(["g++","-std=c++17","-O2","-Wall","-Wextra","-Werror",
                        str(ROOT/"fxcm_cpp_fixture_emitter.cpp"),"-o",str(cls.binary)],
                       check=True, capture_output=True, text=True, timeout=45)
        cls.sha=hashlib.sha256(cls.binary.read_bytes()).hexdigest()
    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def check(self, mode, *, sha=None, timeout=2):
        result=review_pinned_cpp_fixture(
            self.binary,self.sha if sha is None else sha,mode,NOW,
            timeout_seconds=timeout)
        self.assertEqual(result["signal"],"WAIT")
        self.assertEqual(result["status"],"WAIT_FXCM_CPP_SUPERVISOR_TEST_ONLY")
        self.assertFalse(result["executable"])
        self.assertFalse(result["researchEligible"])
        self.assertFalse(result["paperOrdersAllowed"])
        self.assertFalse(result["tradingEnabled"])
        self.assertFalse(result["rawCandlesIncluded"])
        self.assertFalse(result["sdkLoaded"])
        self.assertFalse(result["engineInvoked"])
        self.assertEqual(result["providerRequestsMade"],0)
        self.assertEqual(result["credentialsRead"],0)
        return result

    def test_good_fixture_remains_wait(self):
        result=self.check("--fixture")
        self.assertTrue(result["structuralAuditPassed"],result)
        self.assertEqual(result["bridgeStatus"],"WAIT_FXCM_NATIVE_INTAKE_STANDBY")
        self.assertEqual(result["blockingReason"],"GEOMETRY_CHECK_ONLY_UNLICENSED_SOURCE")

    def test_forged_authorization_cannot_unlock(self):
        self.assertTrue(self.check("--fixture-forged-rights")["structuralAuditPassed"])

    def test_incomplete_feed_stays_blocked(self):
        result=self.check("--fixture-missing-h1")
        self.assertFalse(result["structuralAuditPassed"])
        self.assertEqual(result["blockingReason"],"CANDIDATE_REJECTED_BY_OFFLINE_INTAKE")

    def test_unknown_live_flag_never_starts_process(self):
        self.assertEqual(self.check("--connect-live")["blockingReason"],
                         "OFFLINE_MODE_NOT_ALLOWED")

    def test_wrong_binary_digest_fails_closed(self):
        self.assertEqual(self.check("--fixture",sha="f"*64)["blockingReason"],
                         "OFFLINE_BINARY_HASH_MISMATCH")

    def test_unexpected_binary_exit_fails_closed(self):
        self.assertEqual(self.check("--fixture-exit")["blockingReason"],
                         "OFFLINE_FIXTURE_PROCESS_EXIT_NONZERO")

    def test_invalid_json_fails_closed(self):
        self.assertEqual(self.check("--fixture-malformed")["blockingReason"],
                         "OFFLINE_BINARY_OR_PAYLOAD_FAILURE")

    def test_output_limit_kills_process(self):
        self.assertEqual(self.check("--fixture-large")["blockingReason"],
                         "OFFLINE_FIXTURE_OUTPUT_EXCEEDED_LIMIT")

    def test_hung_process_killed_by_deadline(self):
        self.assertEqual(self.check("--fixture-hang",timeout=.20)["blockingReason"],
                         "OFFLINE_FIXTURE_TIMEOUT")

if __name__=="__main__":
    unittest.main()
