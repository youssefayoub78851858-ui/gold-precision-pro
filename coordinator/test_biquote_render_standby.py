"""Isolated Render standby integration contract. No HTTP or container needed.

CI additionally builds/restarts the real Docker image under --network=none
via test_container_standby.py; this tests that BiQuote remains opt-in.
"""
from __future__ import annotations

import pathlib
import unittest
from unittest.mock import patch

from biquote_24h_observer import (
    AUTHORIZATION_ENV, AUTHORIZATION_VALUE, observe_24h,
    MAX_SAMPLES, MAX_PUBLIC_REQUESTS
)

ROOT = pathlib.Path(__file__).resolve().parent


class BiQuoteRenderStandbySafety(unittest.TestCase):
    def test_docker_copies_required_modules_without_changing_startup_contract(self):
        docker=(ROOT/"Dockerfile").read_text()
        for name in ("biquote_offline_source_audit.py",
                     "biquote_overlap_evidence.py",
                     "biquote_session_gap_audit.py",
                     "biquote_public_one_shot.py",
                     "biquote_24h_observer.py"):
            self.assertIn(name, docker)
        for name in ("biquote_forward_shadow_review.py","biquote_24h_final_verdict.py",
                     "ultimate_batch_acceptance.py","v3_ultimate.js",
                     "ultimate_four_stage_review.js","ultimate_signal_quality.js",
                     "ultimate_signal_quality_report.js","ultimate_shadow_admission.js"):
            self.assertIn(name,docker)
        self.assertIn("ultimate_batch_acceptance.py",docker)
        self.assertIn("private_forward_capacity_preflight.py",docker)
        self.assertIn("biquote_seven_day_review.py",docker)
        self.assertIn("from biquote_seven_day_review import", (ROOT/"entrypoint.py").read_text())
        self.assertIn("biquote_24h_final_verdict.py",docker)
        self.assertIn('CMD ["python3", "/app/entrypoint.py"]', docker)
        self.assertIn('DATA_DIR=/var/data/gold-live', docker)
        self.assertNotIn("CUTOVER_MODE=live", docker)

    def test_standby_requires_explicit_two_part_opt_in(self):
        entry=(ROOT/"entrypoint.py").read_text()
        self.assertIn("biquote_review_enabled=(mode=='standby'", entry)
        self.assertIn("os.environ.get(AUTHORIZATION_ENV)==AUTHORIZATION_VALUE",entry)
        self.assertIn("GPP_BIQUOTE_REVIEW_START_UTC",entry)
        self.assertIn("four_stage_batch_review(",entry)
        self.assertIn("vault_metadata=body['biquotePrivateForwardVault']",entry)
        self.assertIn("shadow_status=body['biquoteForwardShadow']",entry)
        self.assertIn("if biquote_review_enabled:",entry)
        self.assertIn("daemon=True,name='biquote-public-24h-review'",entry)
        self.assertIn("if mode=='live':",entry)
        self.assertIn("if mode!='standby':",entry)
        self.assertIn("'signal':'WAIT','executable':False",entry)
        self.assertEqual(AUTHORIZATION_ENV,"GPP_BIQUOTE_PUBLIC_24H_REVIEW")
        self.assertEqual(AUTHORIZATION_VALUE,"APPROVED_READONLY_NO_TRADING")

    def test_observer_does_not_read_broker_secrets_or_offer_trading(self):
        script=(ROOT/"biquote_24h_observer.py").read_text()
        public=(ROOT/"biquote_public_one_shot.py").read_text()
        for bad in ("TWELVE_DATA_API_KEY","CUTOVER_MODE=live",
                    "broker_process.py","api-capital.backend-capital.com",
                    "https://api-capital.backend-capital.com"):
            self.assertNotIn(bad, script+public)
        self.assertNotIn("requests.post(",script+public)
        self.assertNotIn("urllib.request.urlopen(",script)
        self.assertEqual(MAX_SAMPLES,720)
        self.assertEqual(MAX_PUBLIC_REQUESTS,2880)

    def test_importing_monitor_does_not_make_any_network_calls(self):
        from biquote_24h_observer import QualityCounters
        from biquote_public_one_shot import one_shot_probe
        with patch("urllib.request.urlopen", side_effect=AssertionError("NETWORK_FORBIDDEN")):
            counters=QualityCounters()
            result=counters.report(
                __import__("datetime").datetime(2026,11,16,tzinfo=__import__("datetime").timezone.utc),
                __import__("datetime").datetime(2026,11,16,tzinfo=__import__("datetime").timezone.utc),
                missed_slots=720,complete_window=False)
            self.assertEqual(result["signal"],"WAIT")
            self.assertFalse(result["executable"])
            self.assertEqual(result["requestsAttempted"],0)

if __name__=="__main__":
    unittest.main()
