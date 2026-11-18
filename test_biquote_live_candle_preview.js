"use strict";
const a=require("node:assert/strict");
const preview=require("./biquote-live-candle-preview");
const ms=s=>Date.parse(s);
const stamp=n=>new Date(n).toISOString();
const TF=["M15","H1","H4"];
function makeClosed(){
 const time={M15:"2026-11-18T09:15:00.000Z",
  H1:"2026-11-18T08:00:00.000Z",
  H4:"2026-11-18T04:00:00.000Z"};
 return Object.fromEntries(TF.map(tf=>[tf,[
  {t:ms(time[tf])-preview.WIDTH[tf],open:3773,high:3775,low:3771,close:3772},
  {t:ms(time[tf]),open:3772,high:3774,low:3770,close:3771}
 ]]));
}
function packet(quoteUTC,mid=3771.3,options={}){
 const tick=ms(quoteUTC);
 return {status:"WAIT_CROSS_FRAME_GAPS",signal:"WAIT",executable:false,
  researchEligible:false,paperOrdersAllowed:false,rawQuoteShown:true,
  privateChartReadOnly:true,privateChartDataBasis:"MID_WITH_POSSIBLE_BID_SEED",
  bid:mid-0.05,ask:mid+0.05,
  quoteUTC,observedUTC:stamp(tick+2000),quoteAgeSeconds:2,...options};
}
function openAfter(x,tf,time){
 const p=x[tf];a(p,"No preview: "+tf);
 a.equal(p.t,ms(time),tf);
 a.equal(p.partial,true);a(p.samples>=1);
 a.equal(p.firstTickMs<=p.lastTickMs,true);
}
{
 const candles=makeClosed();
 const src=JSON.stringify(candles);
 const first=packet("2026-11-18T09:35:01.000Z",3771.3);
 const one=preview.update(null,first,candles,ms(first.observedUTC));
 for(const tf of TF)openAfter(one,tf,{
  M15:"2026-11-18T09:30:00.000Z",
  H1:"2026-11-18T09:00:00.000Z",
  H4:"2026-11-18T08:00:00.000Z"}[tf]);
 a.equal(one.H1.open,3771.3);
 a.equal(one.H1.high,3771.3);
 a.equal(one.H1.low,3771.3);
 a.equal(one.H1.samples,1);
 const next=packet("2026-11-18T09:35:22.000Z",3772.7);
 const two=preview.update(one,next,candles,ms(next.observedUTC));
 a.equal(two.H1.open,3771.3);a.equal(two.H1.high,3772.7);
 a.equal(two.H1.close,3772.7);a.equal(two.H1.low,3771.3);
 a.equal(two.H1.samples,2);
 const last=packet("2026-11-18T09:37:05.000Z",3768.9);
 const three=preview.update(two,last,candles,ms(last.observedUTC));
 a.equal(three.H1.low,3768.9);a.equal(three.H1.high,3772.7);
 a.equal(three.M15.samples,3);a.equal(three.H4.samples,3);
 a.equal(JSON.stringify(candles),src,"Never revise provider CLOSED candles");
 a.equal(three.H1.partial,true,"Only sampled prices, not official OHLC");
 const dup=preview.update(three,last,candles,ms(last.observedUTC));
 a.equal(dup.H1.samples,3,"Cache/replay cannot fabricate ticks");
 const cached=packet("2026-11-18T09:37:05.000Z",3768.9,{
  quoteAgeSeconds:18,observedUTC:"2026-11-18T09:37:07.000Z"});
 const cachedPreview=preview.update(three,cached,candles,ms("2026-11-18T09:37:23.000Z"));
 a.equal(cachedPreview.H1.samples,3,"Cache age must be supported");
 const tampered={...last,bid:3600,ask:3601};
 a.equal(preview.update(three,tampered,candles,ms(tampered.observedUTC)).H1,null,
   "Conflicting same-timestamp quote cannot silently mutate preview");
 const stale={...last,quoteAgeSeconds:31};
 a.equal(preview.update(three,stale,candles,ms(stale.observedUTC)).H1,null,
   "Stale must clear on-source preview");
 const tooOld=preview.update(three,last,candles,ms(last.observedUTC)+41000);
 a.equal(tooOld.H1,null,"Client must not show old quotes");
 const anonymous={...last,rawQuoteShown:false};
 a.equal(preview.update(three,anonymous,candles,ms(last.observedUTC)).H1,null);
 for(const change of [{signal:"BUY"},{executable:true},{paperOrdersAllowed:true},
    {privateChartDataBasis:"MT5_PROVEN"},{status:"UNKNOWN"},
    {quoteUTC:"2026-11-18T09:37:05+02:00"}]){
  const r=preview.update(three,{...last,...change},candles,ms(last.observedUTC));
  a.equal(r.H1,null,"Reject unsafe/fake quote status");
 }
 const older=packet("2026-11-18T09:34:00.000Z",3770.7);
 a.equal(preview.update(three,older,candles,ms(older.observedUTC)).H1,null,
  "Out-of-order quote cannot change a formed H1 high/low");
 const boundary=packet("2026-11-18T10:00:05.000Z",3766.2);
 const newClosed=makeClosed();
 newClosed.H1.push({t:ms("2026-11-18T09:00:00.000Z"),
    open:3771,high:3772,low:3766,close:3767});
 newClosed.M15.push({t:ms("2026-11-18T09:30:00.000Z"),
    open:3771,high:3772,low:3766,close:3767});
 // M15 also needs 09:45 closed before 10:00 to be current.
 newClosed.M15.push({t:ms("2026-11-18T09:45:00.000Z"),
    open:3767,high:3768,low:3765,close:3766});
 const rolled=preview.update(three,boundary,newClosed,ms(boundary.observedUTC));
 openAfter(rolled,"H1","2026-11-18T10:00:00.000Z");
 a.equal(rolled.H1.samples,1,"New H1 starts from new tick, never previous candle");
 a.equal(rolled.H1.open,3766.2);
 a.equal(rolled.H4.samples,4,"H4 is still in 08:00-12:00 interval");
 a.equal(rolled.M15.samples,1);
 const unclosed=makeClosed();
 unclosed.H1.push({t:ms("2026-11-18T10:00:00.000Z"),open:3766,
   high:3767,low:3765,close:3766});
 a.equal(preview.update(three,boundary,unclosed,ms(boundary.observedUTC)).H1,null,
   "No overlay where the source wrongly claims a closed/current bar");
 const weekend=packet("2026-11-18T10:00:05.000Z",3766.2,
  {status:"WAIT_BIQUOTE_DATA_UNAVAILABLE"});
 a.equal(preview.update(three,weekend,newClosed,ms(weekend.observedUTC)).H1,null);
}
console.log("PASS sampled BiQuote forming H1/M15/H4 preview, UTC rollover, real quote monotonicity, zero synthetic ticks, stale/unauthorized protection and closed-candle isolation");
