"""Paper admission safety: no fake or unauthenticated input can arm orders."""
import copy
import json
import socket
import unittest
from unittest.mock import patch

from paper_admission_gate import assess_paper_gate

GOOD = {
    "status": "WAIT_EODHD_INTAKE",
    "dataStatus": "WAIT_REVIEW_OBSERVATION_ONLY",
    "signal": "WAIT", "executable": False, "researchEligible": False,
    "paperRunning": False, "engineStatus": "NOT_INVOKED", "sourceRequestsMade": 0,
    "closedBarCounts": {"M15": 100, "H1": 100, "H4": 100},
}
AUDIT = {"status": "AUDIT_OK", "signal": "WAIT", "executable": False,
         "paperRunning": False, "ageSeconds": 0}

class PaperAdmissionTests(unittest.TestCase):
    def check(self, monitor, audit):
        result = assess_paper_gate(monitor, audit)
        self.assertEqual(result["mode"], "PAPER_ADMISSION_REVIEW_ONLY")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["signal"], "WAIT")
        self.assertFalse(result["executable"])
        self.assertFalse(result["paperOrdersAllowed"])
        self.assertFalse(result["paperRunning"])
        self.assertFalse(result["ledgerCreatedByGate"])
        self.assertFalse(result["simulationEvidenceIsLive"])
        self.assertIn("PAPER_LIVE_ACTIVATION_NOT_APPROVED", result["reasonCodes"])
        self.assertEqual(result["costReadiness"]["status"], "BLOCKED")
        self.assertFalse(result["costReadiness"]["ordersAllowed"])
        self.assertFalse(result["costReadiness"]["realBrokerFeesVerified"])
        self.assertEqual(len(result["costReadiness"]["reasonCodes"]), 4)
        self.assertNotIn("BUY", json.dumps(result))
        self.assertNotIn("SELL", json.dumps(result))
        return result

    def test_not_connected_or_expired_monitor_blocks(self):
        for state in ("NOT_CONNECTED", "BLOCKED", "WAIT_STALE",
                      "WAIT_NO_VERIFIED_QUOTE"):
            x = self.check({**GOOD, "dataStatus": state,
                            "closedBarCounts": {"M15": 0, "H1": 0, "H4": 0}}, AUDIT)
            self.assertIn("EODHD_SOURCE_NOT_READY", x["reasonCodes"])
            self.assertIn("CLOSED_MULTITIMEFRAME_HISTORY_INCOMPLETE", x["reasonCodes"])
        for status in ("AUDIT_STALE", "AUDIT_UNAVAILABLE", "AUDIT_DISABLED"):
            self.assertIn("MONITOR_HEARTBEAT_UNVERIFIED",
                          self.check(GOOD, {**AUDIT, "status": status})["reasonCodes"])
        self.assertIn("MONITOR_HEARTBEAT_UNVERIFIED",
                      self.check(GOOD, {**AUDIT, "ageSeconds": 121})["reasonCodes"])

    def test_forged_and_synthetic_cannot_arm_paper(self):
        for mod in ({"signal": "BUY"}, {"researchEligible": True},
                    {"executable": True}, {"paperRunning": True},
                    {"engineStatus": "INVOKED"}, {"dataStatus": "FRESH"},
                    {"sourceRequestsMade": 5}, {"status": "OK"}):
            x = self.check({**GOOD, **mod, "apiKey": "SECRET-KEY"}, AUDIT)
            self.assertIn("MARKET_RESEARCH_CONTRACT_UNVERIFIED", x["reasonCodes"])
            self.assertNotIn("SECRET-KEY", json.dumps(x))
        for counts in ({"M15": 100, "H1": 100, "H4": 0},
                       {"M15": 100, "H1": 100}, {"M15": True, "H1": 100, "H4": 100}):
            x = self.check({**GOOD, "closedBarCounts": counts}, AUDIT)
            self.assertIn("CLOSED_MULTITIMEFRAME_HISTORY_INCOMPLETE", x["reasonCodes"])

    def test_no_account_files_network_or_broker(self):
        with patch.object(socket, "socket", side_effect=AssertionError("No network")):
            x = self.check(GOOD, AUDIT)
        self.assertEqual(x["reasonCodes"], [
            "PAPER_LIVE_ACTIVATION_NOT_APPROVED",
            "SOURCE_LICENSE_AND_HISTORY_NOT_VERIFIED",
            "RISK_AND_BROKER_COSTS_NOT_VERIFIED",
        ])
        self.check(None, None)
        self.check({"signal": "BUY", "executable": True}, {"status": "AUDIT_OK"})

if __name__ == "__main__":
    unittest.main()
