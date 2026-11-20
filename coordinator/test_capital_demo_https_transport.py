"""No-network GET allowlist tests. No API account or provider calls."""
import json
import unittest
from urllib.request import Request
from capital_demo_https_transport import demo_https_price_get, NoRedirect, MAX_BYTES

URL=("https://demo-api-capital.backend-capital.com/api/v1/prices/TEST.GOLD.EPIC"
     "?resolution=MINUTE_15&from=2026-11-20T08%3A00%3A00"
     "&to=2026-11-20T11%3A45%3A01&max=1000")
TOKENS={"CST":"C"*32,"X-SECURITY-TOKEN":"S"*32}


class FakeReply:
    def __init__(self, data=b"{}", status=200, content_type="application/json"):
        self.status=status;self.data=data
        self.headers={"Content-Type":content_type}
    def __enter__(self):return self
    def __exit__(self,*_):return False
    def read(self,n):return self.data[:n]


class FakeOpener:
    def __init__(self, reply):
        self.reply=reply;self.calls=[]
    def open(self, request, timeout):
        self.calls.append((request,timeout))
        return self.reply


class DemoHttpsTests(unittest.TestCase):
    def test_only_fixed_demo_get(self):
        fake=FakeOpener(FakeReply(json.dumps({
            "epic":"TEST.GOLD.EPIC","resolution":"MINUTE_15","prices":[]
        }).encode()))
        r=demo_https_price_get("GET",URL,TOKENS,opener=fake)
        self.assertEqual(r["httpStatus"],200)
        self.assertFalse(r["redirected"])
        self.assertEqual(r["response"]["prices"],[])
        req,timeout=fake.calls[0]
        self.assertEqual(req.get_method(),"GET")
        self.assertEqual(timeout,8)
        self.assertNotIn("C"*32,req.full_url)
        self.assertNotIn("S"*32,req.full_url)

    def test_all_other_routes_and_methods_blocked_before_network(self):
        forbidden=[
            ("POST",URL,TOKENS),
            ("GET",URL.replace("demo-api-","api-"),TOKENS),
            ("GET",URL.replace("/prices/","/positions/"),TOKENS),
            ("GET",URL.replace("/prices/","/session/"),TOKENS),
            ("GET",URL.replace("TEST.GOLD.EPIC","..%2Fpositions"),TOKENS),
            ("GET",URL+"&apiKey=secret",TOKENS),
            ("GET",URL.replace("max=1000","max=2000"),TOKENS),
            ("GET",URL.replace("https://","http://"),TOKENS),
            ("GET",URL+"#redirect",TOKENS),
            ("GET",URL,dict(TOKENS,**{"X-CAP-API-KEY":"K"*32})),
            ("GET",URL,{"CST":"C"*32+"\n","X-SECURITY-TOKEN":"S"*32}),
        ]
        fake=FakeOpener(FakeReply())
        for m,u,h in forbidden:
            with self.subTest(method=m,url=u[:90]):
                with self.assertRaises(ValueError):
                    demo_https_price_get(m,u,h,opener=fake)
        self.assertEqual(fake.calls,[])

    def test_invalid_responses_blocked(self):
        for reply in [
            FakeReply(b"not-json"),
            FakeReply(b"[]"),
            FakeReply(b"{}"+b" "*MAX_BYTES),
            FakeReply(status=302),
            FakeReply(content_type="text/html")
        ]:
            fake=FakeOpener(reply)
            with self.subTest(size=len(reply.data),status=reply.status):
                with self.assertRaises(ValueError):
                    demo_https_price_get("GET",URL,TOKENS,opener=fake)
            self.assertEqual(len(fake.calls),1)

    def test_redirect_never_followed(self):
        with self.assertRaisesRegex(ValueError,"DEMO_REDIRECT_BLOCKED"):
            NoRedirect().redirect_request(
                Request(URL,method="GET"),None,302,"Found",{},
                "https://api-capital.backend-capital.com/api/v1/positions")


if __name__=="__main__":
    unittest.main()
