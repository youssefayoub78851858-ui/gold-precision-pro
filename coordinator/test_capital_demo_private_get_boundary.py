"""Never connect without explicit environment, allowlist, session and operator."""
import copy
import os
import unittest
from unittest.mock import patch

from capital_demo_private_get_boundary import (
    inspect_private_demo_page, ENABLE_ENV, RIGHTS_ENV, ENABLE_VALUE
)
from capital_demo_historical_batch_plan import plan_demo_closed_history

PLAN = plan_demo_closed_history(
    "TEST.GOLD.EPIC", "2026-11-20T08:00:00Z",
    "2026-11-20T12:00:00Z", "2026-11-20T12:01:00Z"
)
CHUNK = PLAN["requests"]["M15"][0]


def request():
    return copy.deepcopy(CHUNK)


def quote(open_utc):
    return {"snapshotTimeUTC": open_utc,
            "openPrice": {"bid": 4000, "ask": 4000.4},
            "highPrice": {"bid": 4001, "ask": 4001.4},
            "lowPrice": {"bid": 3999, "ask": 3999.4},
            "closePrice": {"bid": 4000.1, "ask": 4000.5}}


def fake_transport(call_list, payload=None, status=200, redirected=False):
    def fake(method, url, headers):
        call_list.append((method, url, headers))
        return {"httpStatus": status, "response": (
            payload if payload is not None else {
                "epic": "TEST.GOLD.EPIC", "resolution": "MINUTE_15",
                "prices": [quote("2026-11-20T08:00:00")]
            }), "redirected": redirected}
    return fake


class PrivateDemoGetTests(unittest.TestCase):
    def gate(self, **kw):
        defaults=dict(cst="C"*32, security_token="S"*32,
                      explicit_operator_approval=True)
        defaults.update(kw)
        return inspect_private_demo_page(request(), **defaults)

    def safe(self, output):
        self.assertEqual(output["signal"], "WAIT")
        self.assertFalse(output["executable"])
        self.assertFalse(output["paperOrdersAllowed"])
        self.assertFalse(output["liveOrdersAllowed"])
        self.assertFalse(output["orderRouteSupported"])
        self.assertFalse(output["liveHostAllowed"])
        self.assertFalse(output["sourceRightsIndependentlyAttested"])
        self.assertEqual(output["brokerOrdersSent"], 0)
        self.assertNotIn("4000", str(output))
        self.assertNotIn("C"*32, str(output))
        self.assertNotIn("S"*32, str(output))

    def test_default_no_network_even_with_tokens(self):
        calls=[]
        with patch.dict(os.environ, {ENABLE_ENV:"", RIGHTS_ENV:""}):
            out=self.gate(transport=fake_transport(calls),
                          deliver_private=lambda _:self.fail("private delivery forbidden"))
        self.safe(out);self.assertEqual(out["status"],"BLOCKED")
        self.assertEqual(calls, [])

    def test_one_approved_bounded_demo_get_only_and_private_sink(self):
        calls=[];delivered=[]
        with patch.dict(os.environ, {ENABLE_ENV:ENABLE_VALUE, RIGHTS_ENV:ENABLE_VALUE}):
            out=self.gate(transport=fake_transport(calls),
                          deliver_private=delivered.append)
        self.safe(out)
        self.assertEqual(out["status"], "PRIVATE_DEMO_GEOMETRY_ONLY_NOT_ADMITTED")
        self.assertEqual(out["providerRequestsMade"], 1)
        self.assertEqual(out["pageRowsChecked"], 1)
        self.assertEqual(
            out["unclassifiedMissingClosedSlots"],
            CHUNK["expectedClosedSlots"] - 1
        )
        self.assertFalse(out["completeUTCGridWindowObserved"])
        self.assertFalse(out["originalBrokerSessionVerified"])
        self.assertEqual(len(delivered), 1)
        self.assertEqual(len(calls), 1)
        method,url,headers=calls[0]
        self.assertEqual(method,"GET")
        self.assertTrue(url.startswith(
            "https://demo-api-capital.backend-capital.com/api/v1/prices/TEST.GOLD.EPIC?"))
        self.assertNotIn("api-capital.backend-capital.com/api/v1/positions",url)
        self.assertNotIn("C"*32,url)
        self.assertEqual(set(headers),{"CST", "X-SECURITY-TOKEN"})

    def test_spoofed_routes_and_metadata_are_blocked_before_transport(self):
        malformed=[]
        for key,value in (
            ("method","POST"),("baseUrl","https://api-capital.backend-capital.com"),
            ("path","/api/v1/positions"),("path","/api/v1/session"),
            ("path","/api/v1/prices/TEST/../../positions"),
            ("enabled",True)):
            entry=request();entry["request"][key]=value;malformed.append(entry)
        for key,value in (
            ("firstExpectedOpenUTC","2026-11-20T07:45:00Z"),
            ("expectedEndExclusiveUTC","2026-11-20T12:15:00Z"),
            ("expectedClosedSlots",17),
            ("providerToBoundMayBeInclusive",False),
            ("responseWindowMustBeVerified",False)):
            entry=request();entry[key]=value;malformed.append(entry)
        entry=request();entry["request"]["query"]["to"]="2026-11-20T13:00:00";malformed.append(entry)
        calls=[]
        with patch.dict(os.environ, {ENABLE_ENV:ENABLE_VALUE, RIGHTS_ENV:ENABLE_VALUE}):
            for data in malformed:
                with self.subTest(data=str(data)[:90]):
                    out=inspect_private_demo_page(
                        data,cst="C"*32,security_token="S"*32,
                        explicit_operator_approval=True,
                        transport=fake_transport(calls),
                        deliver_private=lambda _:self.fail("unexpected delivery"))
                    self.safe(out);self.assertEqual(out["status"],"BLOCKED")
        self.assertEqual(calls,[])

    def test_missing_approval_or_missing_tokens_reject_before_transport(self):
        calls=[]
        with patch.dict(os.environ, {ENABLE_ENV:ENABLE_VALUE, RIGHTS_ENV:ENABLE_VALUE}):
            for overrides in (
                {"explicit_operator_approval":False},
                {"cst":"bad"}, {"security_token":"bad"},
                {"cst":"C"*32+"\n"}, {"transport":None}):
                with self.subTest(case=overrides):
                    params={"transport":fake_transport(calls),
                            "deliver_private":lambda _:self.fail("unsafe")}
                    params.update(overrides)
                    out=self.gate(**params)
                    self.safe(out);self.assertEqual(out["status"],"BLOCKED")
        self.assertEqual(calls,[])

    def test_complete_synthetic_utc_grid_does_not_authorize_trading(self):
        # Offline-only FULL-grid fixture: complete geometry is NOT provider
        # rights, first-seen proof, or independent broker session evidence.
        full = [
            quote(f"2026-11-20T{8 + i // 4:02d}:{(i % 4)*15:02d}:00")
            for i in range(CHUNK["expectedClosedSlots"])
        ]
        payload = {
            "epic": "TEST.GOLD.EPIC",
            "resolution": "MINUTE_15",
            "prices": full,
        }
        calls = []
        delivered = []
        with patch.dict(os.environ, {
            ENABLE_ENV: ENABLE_VALUE, RIGHTS_ENV: ENABLE_VALUE
        }):
            out = self.gate(
                transport=fake_transport(calls, payload=payload),
                deliver_private=delivered.append,
            )
        self.safe(out)
        self.assertEqual(out["status"], "PRIVATE_DEMO_GEOMETRY_ONLY_NOT_ADMITTED")
        self.assertEqual(out["pageRowsChecked"], CHUNK["expectedClosedSlots"])
        self.assertEqual(out["unclassifiedMissingClosedSlots"], 0)
        self.assertTrue(out["completeUTCGridWindowObserved"])
        self.assertFalse(out["originalBrokerSessionVerified"])
        self.assertFalse(out["researchEligible"])
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(delivered), 1)

    def test_empty_or_over_capacity_pages_never_reach_private_archive(self):
        # An HTTP 200 with no bars is not proof of a captured interval.
        # Returning more rows than approved CLOSED slots is equally invalid.
        requests = request()
        capacity = requests["expectedClosedSlots"]
        self.assertGreater(capacity, 1)
        for supplied in ([], [quote("2026-11-20T08:00:00")] * (capacity + 1)):
            with self.subTest(size=len(supplied)):
                calls = []
                delivered = []
                payload = {
                    "epic": "TEST.GOLD.EPIC",
                    "resolution": "MINUTE_15",
                    "prices": supplied,
                }
                with patch.dict(os.environ, {
                    ENABLE_ENV: ENABLE_VALUE, RIGHTS_ENV: ENABLE_VALUE
                }):
                    out = self.gate(
                        transport=fake_transport(calls, payload=payload),
                        deliver_private=delivered.append,
                    )
                self.safe(out)
                self.assertEqual(out["status"], "BLOCKED")
                self.assertEqual(len(calls), 1)
                self.assertEqual(delivered, [])
                self.assertEqual(out["pageRowsChecked"], 0)
                self.assertEqual(out["reason"], (
                    "BROKER_PRICE_PAGE_EMPTY_NOT_OBSERVED"
                    if len(supplied) == 0
                    else "BROKER_PRICE_PAGE_EXCEEDS_APPROVED_WINDOW"
                ))

    def test_bad_price_identity_future_crossing_redirect_dont_deliver(self):
        choices=[
            {"payload":{"epic":"NOT_GOLD","resolution":"MINUTE_15","prices":[]}},
            {"payload":{"epic":"TEST.GOLD.EPIC","resolution":"HOUR","prices":[]}},
            {"payload":{"epic":"TEST.GOLD.EPIC","resolution":"MINUTE_15",
                        "prices":[quote("2026-11-20T12:00:00")]}},
            {"payload":{"epic":"TEST.GOLD.EPIC","resolution":"MINUTE_15",
                        "prices":[quote("2026-11-20T08:00:00")]*2}},
            {"payload":{"epic":"TEST.GOLD.EPIC","resolution":"MINUTE_15",
                        "prices":[{**quote("2026-11-20T08:00:00"),
                                   "highPrice":{"bid":3990,"ask":3990.4}}]}},
            {"status":302}, {"redirected":True},
        ]
        with patch.dict(os.environ, {ENABLE_ENV:ENABLE_VALUE, RIGHTS_ENV:ENABLE_VALUE}):
            for case in choices:
                calls=[];delivered=[]
                out=self.gate(
                    transport=fake_transport(calls,**case),
                    deliver_private=delivered.append)
                self.safe(out);self.assertEqual(out["status"],"BLOCKED")
                self.assertEqual(delivered,[])

    def test_explicit_archive_refusal_and_unexpected_exception_fail_closed(self):
        calls = []
        with patch.dict(os.environ, {
            ENABLE_ENV: ENABLE_VALUE, RIGHTS_ENV: ENABLE_VALUE
        }):
            refused = self.gate(
                transport=fake_transport(calls),
                deliver_private=lambda _: False
            )
            self.safe(refused)
            self.assertEqual(refused["status"], "BLOCKED")
            self.assertEqual(refused["reason"], "PRIVATE_DEMO_ARCHIVE_REFUSED_PAGE")
            self.assertEqual(refused["pageRowsChecked"], 0)

            # Unanticipated provider/sink failures are reduced to fixed,
            # non-sensitive error codes, not leaked into logs or UI.
            failed = self.gate(
                transport=fake_transport(calls),
                deliver_private=lambda _: (_ for _ in ()).throw(
                    RuntimeError("SECRET_PROVIDER_TOKEN_IN_EXCEPTION"))
            )
            self.safe(failed)
            self.assertEqual(failed["status"], "BLOCKED")
            self.assertEqual(
                failed["reason"], "PRIVATE_DEMO_TRANSPORT_OR_ARCHIVE_ERROR"
            )
            self.assertNotIn("SECRET_PROVIDER_TOKEN", str(failed))
            transport_failed = self.gate(
                transport=lambda *args: (_ for _ in ()).throw(
                    RuntimeError("SECRET_TRANSPORT_TOKEN_IN_EXCEPTION")),
                deliver_private=lambda _: self.fail("must not archive")
            )
            self.safe(transport_failed)
            self.assertEqual(
                transport_failed["reason"], "PRIVATE_DEMO_TRANSPORT_OR_ARCHIVE_ERROR"
            )
            self.assertNotIn("SECRET_TRANSPORT_TOKEN", str(transport_failed))
        self.assertEqual(len(calls), 2)

    def test_transport_failure_does_not_echo_or_approve(self):
        with patch.dict(os.environ, {ENABLE_ENV:ENABLE_VALUE, RIGHTS_ENV:ENABLE_VALUE}):
            out=self.gate(
                transport=lambda *args: (_ for _ in ()).throw(
                    OSError("SECRET_CREDENTIAL_XXXXXX")),
                deliver_private=lambda _:self.fail("not allowed"))
        self.safe(out)
        self.assertNotIn("SECRET_CREDENTIAL",str(out))


if __name__ == "__main__":
    unittest.main()
