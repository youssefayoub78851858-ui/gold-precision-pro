"""Offline pre-release calendar guard, without modifying frozen V2."""
import json
import socket
import unittest
from unittest.mock import patch
from offline_calendar_release_gate import inspect_calendar_release

TIME = "2026-09-01T12:01:00Z"


def exported(**event_overrides):
    event = dict(timeUTC="2026-09-01T13:00:00Z",
                 publishedUTC="2026-09-01T11:00:00Z", impact="high",
                 **event_overrides)
    return dict(mode="recorded", source="SANITIZED_OFFLINE_FIXTURE",
                instrument="USD_EVENTS", entitlementVerified=True,
                observedUTC="2026-09-01T12:00:00Z",
                availableUTC=TIME, coverageStartUTC="2026-09-01T11:00:00Z",
                coverageEndUTC="2026-09-01T14:00:00Z", events=[event])


class CalendarReleaseGateTests(unittest.TestCase):
    def assert_safe(self, output):
        self.assertEqual(output["signal"], "WAIT")
        for flag in ("executable", "researchEligible", "paperOrdersAllowed",
                     "liveOrdersAllowed", "sourceRightsIndependentlyVerified",
                     "publicationTimeIndependentlyVerified",
                     "independentHoldoutValidated"):
            self.assertIs(output[flag], False, flag)
        self.assertEqual(output["providerRequestsMade"], 0)
        self.assertEqual(output["brokerOrdersSent"], 0)
        self.assertNotIn("PRIVATE_SECRET", json.dumps(output))

    def test_future_event_schedule_only_and_point_in_time(self):
        out = inspect_calendar_release(exported(actual=None), as_of_utc=TIME)
        self.assert_safe(out)
        self.assertEqual(out["status"], "UNATTESTED_CHRONOLOGY_ONLY")
        self.assertEqual(out["scheduledEvents"], 1)
        self.assertEqual(out["historicalEvents"], 0)
        self.assertEqual(inspect_calendar_release(
            exported(), as_of_utc="2026-09-01T12:00:59Z"
        )["reason"], "EXPORT_NOT_AVAILABLE_AT_AUDIT_CUTOFF")

    def test_future_actual_zero_surprise_revision_and_status_block(self):
        for key, val in (
            ("actual", 0), ("actualValue", 2.0), ("actual_value", 4),
            ("surprise", -.5), ("surpriseValue", 1),
            ("surprise_value", 0), ("revisedActual", 1),
            ("revised_actual", 0), ("revision", 3),
            ("status", "RELEASED"), ("status", "completed"),
            ("status", "published_actual"),
        ):
            with self.subTest(key=key):
                o = inspect_calendar_release(exported(**{key: val}),
                                             as_of_utc=TIME)
                self.assert_safe(o)
                self.assertEqual(o["status"], "BLOCKED")

    def test_postrelease_actual_only_descriptive_never_permission(self):
        doc = exported(actual=3.5, surprise=.5)
        doc["observedUTC"] = "2026-09-01T13:00:00Z"
        doc["availableUTC"] = "2026-09-01T13:01:00Z"
        out = inspect_calendar_release(doc, as_of_utc="2026-09-01T13:02:00Z")
        self.assert_safe(out)
        self.assertEqual(out["status"], "UNATTESTED_CHRONOLOGY_ONLY")
        self.assertEqual(out["historicalEvents"], 1)

    def test_invalid_or_forged_and_no_network(self):
        for doc in (
            {**exported(), "entitlementVerified": False},
            {**exported(), "instrument": "DXY"},
            {**exported(), "events": ["NOT_AN_EVENT"]},
            {**exported(), "events": [{
                **exported()["events"][0],
                "publishedUTC": "2026-09-01T12:05:00Z"}]},
            None,
        ):
            o = inspect_calendar_release(doc, as_of_utc=TIME)
            self.assert_safe(o)
            self.assertEqual(o["status"], "BLOCKED")
        with patch.object(socket, "socket", side_effect=AssertionError("NO NETWORK")):
            self.assert_safe(inspect_calendar_release(exported(),
                                                       as_of_utc=TIME))


if __name__ == "__main__":
    unittest.main()
