'use strict';
const a=require('node:assert/strict');
const {MassiveQuoteStandby,transportPlan}=require('./massive_ws_standby');
const cfg=transportPlan();
a.equal(cfg.websocketTopic,'C.XAU-USD');a.equal(cfg.websocketPair,'XAU/USD');
a.equal(cfg.restTicker,'C:XAUUSD');
a.equal(cfg.documentedEndpoint,'wss://socket.massive.com/forex');
a.equal(cfg.sequence,'CONNECT_THEN_AUTH_THEN_SUBSCRIBE');
a.equal(cfg.transportImplemented,false);a.equal(cfg.connectionApproved,false);
a.equal(cfg.networkRequestsMade,0);a.equal(cfg.entitlementVerified,false);
a.equal(cfg.cloudLicenseVerified,false);a.equal(cfg.executable,false);
const step=900000,start=Date.parse('2026-11-10T08:00:00.000Z');
let now=start+1000;
const quote=(t,b=3900,aPrice=3900.4,p='XAU/USD')=>({ev:'C',p,t,b,a:aPrice,x:44});
function feed(s){return s.handle({ev:'status',status:'auth_success'});}
function subscribe(s){return s.handle({ev:'status',status:'success',message:'subscribed to: C.XAU-USD'});}
let s=new MassiveQuoteStandby(()=>now);
a.equal(s.handle(quote(now)).reason,'QUOTE_BEFORE_SUBSCRIPTION');
a.equal(s.snapshot().syntheticFramesProcessed,0);
a.equal(s.handle({ev:'status',status:'connected'}).kind,'ignored');
a.equal(feed(s).kind,'authenticated');
a.equal(s.handle(quote(now)).reason,'QUOTE_BEFORE_SUBSCRIPTION');
a.equal(feed(s).kind,'authenticated');a.equal(subscribe(s).kind,'subscribed');
a.equal(s.handle(quote(now,3900,3900.4,'EUR/USD')).kind,'ignored'); // unrelated pair
let w=new MassiveQuoteStandby(()=>now);
a.equal(feed(w).kind,'authenticated');
a.equal(subscribe(w).kind,'subscribed');
const pre=quote(start+30000);
now=pre.t+500;
a.equal(w.handle([pre]).kind,'synthetic_quote');
a.equal(w.snapshot().frames.M15.length,0);
a.equal(w.snapshot().signal,'WAIT');a.equal(w.snapshot().executable,false);
a.equal(w.snapshot().sourceDataMode,'SYNTHETIC_TEST_ONLY');
for(let i=0;i<16;i++){
 for(let j=0;j<15;j++){
  const ts=start+i*step+j*60000+30000;
  // First synthetic quote above was already delivered.
  if(i===0&&j===0)continue;
  now=ts+500;
  const bid=3900+i*.01+j*.002;
  a.equal(w.handle(quote(ts,bid,bid+.4)).kind,'synthetic_quote');
 }
}
now=start+16*step+30500;
a.equal(w.handle(quote(start+16*step+30000,3901.2,3901.6)).kind,'synthetic_quote');
let out=w.snapshot();
a.deepEqual([out.frames.M15.length,out.frames.H1.length,out.frames.H4.length],[16,4,1]);
a.deepEqual([out.bidFrames.H4.length,out.askFrames.H4.length],[1,1]);
a.equal(out.researchEligible,false);a.equal(out.historicalLiveParityVerified,false);
a.equal(out.subscribedToActualProvider,false);
a.equal(out.quoteActivityIsTradeVolume,false);
// Distinct BBO values at same timestamp are legal (same millisecond).
const previous=w.snapshot().syntheticFramesProcessed;
now+=1;
a.equal(w.handle(quote(start+16*step+30000,3901.4,3901.8)).kind,'synthetic_quote');
a.equal(w.snapshot().syntheticFramesProcessed,previous+1);
a.equal(w.snapshot().lastSyntheticQuote.bid,3901.4);
let before=w.snapshot().frames.M15.length;
now+=1;
a.equal(w.handle(quote(start+16*step+29000)).reason,'REVERSED_OR_GAPPED_QUOTE');
a.equal(w.snapshot().frames.M15.length,before);
a.equal(w.snapshot().lastSyntheticQuote,null);
a.equal(w.snapshot().syntheticStatus,'NOT_CONNECTED');
for(const bad of [
 {ev:'status',status:'auth_failed'},
 {ev:'status',status:'max_connections'},
 {ev:'status',status:'error'},
]){const check=new MassiveQuoteStandby(()=>now);a.equal(check.handle(bad).reason,'AUTH_OR_ENTITLEMENT_REFUSED');}
for(const x of [quote(now,3901,3900),quote(now,NaN,3902),quote(now,0,3902)]){
 const k=new MassiveQuoteStandby(()=>now);feed(k);subscribe(k);
 a.equal(k.handle(x).reason,'INVALID_OR_CROSSED_BBO');
}
let z=new MassiveQuoteStandby(()=>now);feed(z);subscribe(z);
const old=now-31000;
a.equal(z.handle(quote(old)).reason,'STALE_OR_FUTURE_QUOTE');
let t=new MassiveQuoteStandby(()=>now);feed(t);subscribe(t);
a.equal(t.handle(quote(now+6000)).reason,'STALE_OR_FUTURE_QUOTE');
// A 1ms future quote is not available at decision time. A tolerated
// +5s clock drift would introduce look-ahead into replay/adapters.
for(const skew of [1,2500,4999,5000]){
 const candidate=new MassiveQuoteStandby(()=>now);
 feed(candidate);subscribe(candidate);
 a.equal(candidate.handle(quote(now+skew)).reason,'STALE_OR_FUTURE_QUOTE');
 a.equal(candidate.snapshot().syntheticFramesProcessed,0);
 a.equal(candidate.snapshot().syntheticStatus,'NOT_CONNECTED');
 a.equal(candidate.snapshot().signal,'WAIT');
 a.equal(candidate.snapshot().executable,false);
}
let gap=new MassiveQuoteStandby(()=>now);feed(gap);subscribe(gap);
a.equal(gap.handle(quote(now)).kind,'synthetic_quote');
now+=91000;
a.equal(gap.handle(quote(now)).reason,'REVERSED_OR_GAPPED_QUOTE');
a.equal(gap.snapshot().frames.M15.length,0);
// Socket connected + subscribed but silent is NOT a healthy feed.
let heartbeat=new MassiveQuoteStandby(()=>now);feed(heartbeat);subscribe(heartbeat);
now+=60000;
a.equal(heartbeat.expired(),false); // no first accepted quote: no live status to extend
a.equal(heartbeat.snapshot().syntheticFramesProcessed,0);
a.equal(heartbeat.checkIdle().kind,'wait');
a.equal(heartbeat.snapshot().researchEligible,false);
// An open/authorized connection with ZERO quotes must time out, too.
let noQuotes=new MassiveQuoteStandby(()=>now);
feed(noQuotes);subscribe(noQuotes);
now+=179999;
a.equal(noQuotes.checkIdle().kind,'wait');
now+=1;
a.equal(noQuotes.expired(),true);
a.equal(noQuotes.checkIdle().reason,'QUOTE_STREAM_SILENT');
a.equal(noQuotes.snapshot().syntheticStatus,'NOT_CONNECTED');
a.equal(noQuotes.snapshot().syntheticFramesProcessed,0);
now+=1;
a.equal(heartbeat.handle(quote(now)).reason,'QUOTE_STREAM_SILENT');
feed(heartbeat);subscribe(heartbeat);
a.equal(heartbeat.handle(quote(now)).kind,'synthetic_quote');
now+=180000;
a.equal(heartbeat.checkIdle().reason,'QUOTE_STREAM_SILENT');
a.equal(heartbeat.snapshot().lastSyntheticQuote,null);
// Public review module has no transport or credentials even when imported.
const fs=require('node:fs');
const src=fs.readFileSync(require.resolve('./massive_ws_standby'),'utf8');
a(!/\bnew\s+WebSocket\s*\(/.test(src));
a(!/process\.env/.test(src));
a(!/\bfetch\s*\(/.test(src));
a(!/\bcreateConnection\s*\(/.test(src));
a(!/apiKey\s*[:=]/.test(src));
console.log('PASS Massive standby quote protocol, 16 M15 BID/ASK bars, same-time quote events, stale/gaps/no-transport');
