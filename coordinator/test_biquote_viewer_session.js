"use strict";
const a=require("node:assert/strict"),fs=require("node:fs"),crypto=require("node:crypto");
const s=require("./biquote_viewer_session");
const old=process.env[s.KEY_NAME];
const k="A".repeat(64),other="B".repeat(64),now=Date.parse("2026-11-17T18:00:00Z");
try{
 delete process.env[s.KEY_NAME];
 a.throws(()=>s.issue(now),/SESSION_DISABLED/);
 a.equal(s.authenticated({cookie:"foo=bar"},now),false);
 process.env[s.KEY_NAME]=k;
 const created=s.issue(now),cookie=created.cookie;
 a(cookie.length<300);
 a(!cookie.includes("MONITOR_READONLY_TOKEN"));
 a(!cookie.includes("Bearer "));
 a.equal(s.verify(cookie,now),true);
 a.equal(s.TTL_SECONDS,365*24*60*60,"A year of inactivity does not demand weekly logins");
 a.equal(cookie.startsWith("v2."),true);
 a.equal(s.verify(cookie,now+s.TTL_SECONDS*1000-1000),true);
 a.equal(s.verify(cookie,now+s.TTL_SECONDS*1000),false);
 a.equal(s.verify(cookie,now-31000),false);
 a.equal(s.verify(cookie.slice(0,-2)+"AA",now),false);
 a.equal(s.verify(cookie.split(".").slice(0,4).join(".")+".spoof",now),false);
 const header="tracking=abc; "+s.COOKIE+"="+cookie+"; foo=bar";
 a.equal(s.renewal({cookie:header,"sec-fetch-site":"same-origin"},
    now+(s.RENEW_AFTER_SECONDS-1)*1000),null,"Do not churn cookie at every two-minute chart poll");
 const renewedHeader=s.renewal({cookie:header,"sec-fetch-site":"same-origin"},
    now+s.RENEW_AFTER_SECONDS*1000);
 a(renewedHeader&&renewedHeader.includes("HttpOnly")&&renewedHeader.includes("SameSite=Strict"));
 const renewed=renewedHeader.split(";")[0].slice((s.COOKIE+"=").length);
 a(s.verify(renewed,now+s.RENEW_AFTER_SECONDS*1000));
 a(!s.verify(renewed,now+s.RENEW_AFTER_SECONDS*1000+s.TTL_SECONDS*1000));
 a(s.verify(renewed,now+s.TTL_SECONDS*1000),"Automatic renewal extends trust beyond original expiration");
 a.equal(s.renewal({cookie:header,"sec-fetch-site":"cross-site"},
    now+s.RENEW_AFTER_SECONDS*1000),null);
 a.equal(s.renewal({cookie:"garbage=forged"},now),null);
 // Previous 7-day cookies MUST migrate transparently on first new visit.
 const legacyIssued=Math.floor(now/1000),legacyExpiry=legacyIssued+s.LEGACY_TTL_SECONDS;
 const payload="v1."+legacyIssued+"."+legacyExpiry+"."+crypto.randomBytes(18).toString("base64url");
 const legacyCookie=payload+"."+crypto.createHmac("sha256",Buffer.from(k,"utf8"))
   .update("gpp-biquote-review-only-v1:"+payload).digest("base64url");
 a(s.verify(legacyCookie,now));
 a.equal(s.verify(legacyCookie,now+s.LEGACY_TTL_SECONDS*1000),false);
 const legacyHeaders={cookie:s.COOKIE+"="+legacyCookie,"sec-fetch-site":"same-origin"};
 const legacyRenewal=s.renewal(legacyHeaders,now+1000);
 a(legacyRenewal?.includes(s.COOKIE+"=v2."),"Old 7-day sessions upgrade without second token");
 const upgraded=legacyRenewal.split(";")[0].slice((s.COOKIE+"=").length);
 a(s.verify(upgraded,now+1000));
 a(s.verify(upgraded,now+s.LEGACY_TTL_SECONDS*1000+1000));
 a.equal(s.renewal(legacyHeaders,now+s.LEGACY_TTL_SECONDS*1000),null);
 a.equal(s.extract(header),cookie);
 a.equal(s.authenticated({cookie:header,"sec-fetch-site":"same-origin"},now),true);
 a.equal(s.authenticated({cookie:header,"sec-fetch-site":"cross-site"},now),false);
 a.equal(s.authenticated({cookie:header,"sec-fetch-site":"none"},now),true);
 a.equal(s.authenticated({cookie:header+"; "+s.COOKIE+"=fake"},now),false);
 a.equal(s.authenticated({cookie:"other="+cookie},now),false);
 a.equal(s.sameOrigin({origin:s.REVIEW_ORIGIN,"sec-fetch-site":"same-origin"}),true);
 a.equal(s.sameOrigin({origin:"https://attacker.invalid","sec-fetch-site":"same-origin"}),false);
 a.equal(s.sameOrigin({origin:s.REVIEW_ORIGIN,"sec-fetch-site":"cross-site"}),false);
 a.equal(s.sameOrigin({}),false);
 const set=s.setCookie(cookie);
 for(const required of ["; Secure","; HttpOnly","; SameSite=Strict","; Path=/","; Max-Age="+s.TTL_SECONDS]){
   a(set.includes(required),required);
   a(s.clearCookie().includes(required.replace(/; Max-Age=.*/, "; Max-Age=0"))||required.startsWith("; Max-Age="));
 }
 a(set.startsWith(s.COOKIE+"="+cookie+";"));
 a(s.clearCookie().includes("Max-Age=0"));
 a(!set.includes("Domain="));
 process.env[s.KEY_NAME]=other;
 a.equal(s.verify(cookie,now),false,"Rotating signing key invalidates old sessions");
 process.env[s.KEY_NAME]=k;
 a.equal(s.verify(cookie,now),true);
 const root=fs.readFileSync("server.js","utf8");
 a(root.includes('"/api/v3/ultimate/biquote-viewer-session"'));
 a(root.includes('viewerSessionAuthenticated:authorizedDevice'));
 a(root.includes('viewerSession.renewal(req.headers)'));
 a(root.includes('const refreshed=authorizedDevice?viewerSession.renewal(req.headers):null'));
 a(root.includes('...(refreshed?{"Set-Cookie":refreshed}:{})'));
 a(root.includes('method:"POST"')===false,"Service should read HTTP POST request, not originate network POST");
 a(root.includes('req.method==="DELETE"'));
 a(root.includes("session.sameOrigin(req.headers)"));
 a(root.includes('session.clearCookie()'));
 a(root.includes('session.setCookie(issued.cookie)'));
 a(root.includes('privateMonitor.relay(token,{approved:true})') ||
   root.includes('proxy.relay(token,{approved:true})'));
 // Read-only paper report routes may explicitly reject unsafe live-order
 // flags. Require the denial; never confuse a guard with an order endpoint.
 a(root.includes('result.body.liveOrdersAllowed!==false'));
 a(!root.includes('order_send('));
 a(!root.includes('executeBrokerOrder('));
 const frontend=fs.readFileSync("biquote-mobile-ui.js","utf8");
 a(frontend.includes('credentials:"same-origin"'));
 a(frontend.includes('"/api/v3/ultimate/biquote-viewer-session"'));
 a(frontend.includes('method:"DELETE"'));
 a(!frontend.includes("localStorage"));
 a(!frontend.includes("sessionStorage"));
 const page=fs.readFileSync("ultimate.html","utf8");
 a(page.includes('id="biquote-viewer-logout"'));
 a(page.includes('id="biquote-viewer-session-state"'));
 a.equal(s.WAIT.signal,"WAIT");
 a.equal(s.WAIT.executable,false);
 a.equal(s.WAIT.paperOrdersAllowed,false);
 console.log("PASS long-lived 365-day sliding read-only device trust, legacy cookie migration, HMAC renewal, CSRF, expiry, logout and no token persistence");
}finally{
 if(old===undefined)delete process.env[s.KEY_NAME];
 else process.env[s.KEY_NAME]=old;
}
