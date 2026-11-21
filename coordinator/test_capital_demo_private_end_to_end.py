"""Offline mock integration: private gate -> strict HTTPS transport -> private sink."""
import json
import os
import unittest
from unittest.mock import patch

from capital_demo_https_transport import demo_https_price_get
from capital_demo_private_get_boundary import (
    inspect_private_demo_page, ENABLE_ENV, RIGHTS_ENV, ENABLE_VALUE
)
from test_capital_demo_private_get_boundary import request, quote


class FakeReply:
    status=200
    headers={"Content-Type":"application/json"}
    def __init__(self,data):
        self.data=json.dumps(data).encode()
    def __enter__(self):return self
    def __exit__(self,*_):return False
    def read(self,n):return self.data[:n]


class FakeOpener:
    def __init__(self,body):
        self.body=body
        self.calls=[]
    def open(self,req,timeout):
        self.calls.append((req,timeout))
        return FakeReply(self.body)


class IntegratedPriceTests(unittest.TestCase):
    def run_gateway(self, opener, sink):
        def verified_test_sink(page):
            # Synthetic test only; returned receipt is NOT a claim of
            # real persistence or authorization to use Capital data.
            sink(page)
            return {"committed": True, "storedRows": len(page["prices"])}
        return inspect_private_demo_page(
            request(),cst="C"*32,security_token="S"*32,
            explicit_operator_approval=True,
            transport=lambda m,u,h:demo_https_price_get(
                m,u,h,opener=opener,explicit_operator_approval=True),
            deliver_private=verified_test_sink)

    def test_private_only_synthetic_flow_without_orders(self):
        opener=FakeOpener({"epic":"TEST.GOLD.EPIC",
                           "resolution":"MINUTE_15",
                           "prices":[quote("2026-11-20T08:00:00")]})
        delivered=[]
        with patch.dict(os.environ, {
            ENABLE_ENV:ENABLE_VALUE, RIGHTS_ENV:ENABLE_VALUE}):
            r=self.run_gateway(opener,delivered.append)
        self.assertEqual(r["status"],"PRIVATE_DEMO_GEOMETRY_ONLY_NOT_ADMITTED")
        self.assertEqual(r["signal"],"WAIT")
        self.assertFalse(r["executable"])
        self.assertFalse(r["researchEligible"])
        self.assertFalse(r["paperOrdersAllowed"])
        self.assertFalse(r["sourceRightsIndependentlyAttested"])
        self.assertEqual(r["pageRowsChecked"],1)
        self.assertEqual(len(opener.calls),1)
        self.assertEqual(len(delivered),1)
        public=json.dumps(r)
        for secret in ("4000","C"*32,"S"*32,"bid","ask"):
            self.assertNotIn(secret,public)

    def test_default_never_fetches_or_delivers_even_with_tokens(self):
        opener=FakeOpener({"epic":"TEST.GOLD.EPIC",
                           "resolution":"MINUTE_15","prices":[]})
        delivered=[]
        with patch.dict(os.environ,{ENABLE_ENV:"",RIGHTS_ENV:""}):
            r=self.run_gateway(opener,delivered.append)
        self.assertEqual(r["status"],"BLOCKED")
        self.assertEqual(opener.calls,[])
        self.assertEqual(delivered,[])

    def test_provider_identity_conflict_fails_without_archiving(self):
        opener=FakeOpener({"epic":"WRONG.EPIC",
                           "resolution":"MINUTE_15",
                           "prices":[quote("2026-11-20T08:00:00")]})
        delivered=[]
        with patch.dict(os.environ,{
            ENABLE_ENV:ENABLE_VALUE,RIGHTS_ENV:ENABLE_VALUE}):
            r=self.run_gateway(opener,delivered.append)
        self.assertEqual(r["status"],"BLOCKED")
        self.assertEqual(r["reason"],"BROKER_PRICE_PAGE_IDENTITY_UNVERIFIED")
        self.assertEqual(len(opener.calls),1)
        self.assertEqual(delivered,[])


if __name__=="__main__":
    unittest.main()
