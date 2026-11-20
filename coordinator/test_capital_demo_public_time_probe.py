"""Mock-only public Capital Demo time contract checks; zero network calls."""
import json
import unittest
from urllib.request import Request
from capital_demo_public_time_probe import probe, RejectRedirect, URL

class Reply:
    def __init__(self, *,status=200,url=URL,ctype="application/json",data=b'{"serverTime":0}'):
        self.status=status; self.url=url; self.headers={"Content-Type":ctype}; self.data=data
    def __enter__(self):return self
    def __exit__(self,*_):return False
    def geturl(self):return self.url
    def read(self,n):return self.data[:n]

class Fake:
    def __init__(self,reply):
        self.reply=reply;self.calls=[]
    def open(self,request,timeout):
        self.calls.append((request,timeout))
        return self.reply

class PublicTimeTests(unittest.TestCase):
    def test_fixed_public_demo_time_get_only(self):
        x=Fake(Reply())
        out=probe(opener=x)
        self.assertTrue(out["demoTimeEndpointReachable"])
        self.assertFalse(out["marketDataRightsVerified"])
        self.assertFalse(out["renderConnectionVerified"])
        self.assertEqual(out["signal"],"WAIT")
        self.assertFalse(out["executable"])
        self.assertFalse(out["paperOrdersAllowed"])
        self.assertFalse(out["liveOrdersAllowed"])
        self.assertEqual(out["goldCandlesRetrieved"],0)
        self.assertFalse(out["apiKeyUsed"])
        self.assertFalse(out["credentialsUsed"])
        self.assertEqual(out["ordersSent"],0)
        self.assertEqual(len(x.calls),1)
        request,timeout=x.calls[0]
        self.assertEqual(request.get_method(),"GET")
        self.assertEqual(request.full_url,URL)
        self.assertEqual(timeout,8)
        self.assertEqual(set(request.headers),{"Accept"})

    def test_wrong_status_mime_url_body_and_oversize_fail_closed(self):
        cases=[
            Reply(status=302),Reply(url="https://api-capital.backend-capital.com/api/v1/time"),
            Reply(ctype="text/html"),Reply(data=b"bad"),
            Reply(data=b"[]"),Reply(data=b" "*4100),
        ]
        for item in cases:
            with self.subTest(status=item.status,url=item.url):
                out=probe(opener=Fake(item))
                self.assertEqual(out["status"],"BLOCKED")
                self.assertEqual(out["signal"],"WAIT")
                self.assertFalse(out["marketDataRequested"])
                self.assertFalse(out["executable"])
                self.assertEqual(out["ordersSent"],0)

    def test_redirect_cannot_follow_to_live_host(self):
        with self.assertRaisesRegex(ValueError,"DEMO_TIME_REDIRECT_NOT_PERMITTED"):
            RejectRedirect().redirect_request(
                Request(URL,method="GET"),None,302,"Moved",{},
                "https://api-capital.backend-capital.com/api/v1/positions")

    def test_exception_never_exports_private_details(self):
        class Broken:
            def open(self,*args,**kwargs):
                raise RuntimeError("top_secret")
        data=probe(opener=Broken())
        self.assertEqual(data["status"],"BLOCKED")
        self.assertNotIn("top_secret",json.dumps(data))

if __name__ == "__main__":
    unittest.main()
