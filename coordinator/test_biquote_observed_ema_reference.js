"use strict";
const assert=require("node:assert/strict");
const {examine,frameCandidate}=require("./biquote_observed_ema_reference");
const NOW=Date.parse("2026-11-17T11:15:00Z");
const W={M15:900000,H1:3600000,H4:14400000};
function row(t,i=0){
 const c=3900+i*.3;
 return {time:new Date(t).toISOString(),open:c,high:c+.8,low:c-.8,close:c+.1};
}
function bars(tf,n=48,missing=false){
 const w=W[tf],end=Math.floor(NOW/w)*w;
 const result=Array.from({length:n},(_,i)=>row(end-(n-i)*w,i));
 if(missing){
   // Missing one midweek hour or 15m candle, not a session pause:
   for(let i=0;i<n-12;i++)
     result[i].time=new Date(Date.parse(result[i].time)-w).toISOString();
 }
 return result;
}
function strict(x){
 assert.equal(x.signal,"WAIT");
 assert.equal(x.executable,false);
 assert.equal(x.tradeEligible,false);
 assert.equal(x.researchEligible,false);
 assert.equal(x.paperOrdersAllowed,false);
 assert.equal(x.validForEntry,false);
 assert.equal(x.brokerSessionVerified,false);
 assert.equal(x.upstreamRightsVerified,false);
 assert.equal(x.observationOnly,true);
 assert.equal(x.gapsAssumedClosed,false);
}
const sampleH1=[
 ...Array.from({length:22},(_,i)=>row(Date.parse("2026-11-12T01:00:00Z")+3600000*i,i)),
 ...Array.from({length:26},(_,i)=>row(Date.parse("2026-11-13T01:00:00Z")+3600000*i,i+22))
];
// Use deterministic fully valid H1 bars over regular day pause.
function sessionRows(tf,n=48){
 const w=W[tf];let cursor=Date.parse("2026-11-17T08:00:00Z");
 cursor=Math.floor(cursor/w)*w;
 const out=[];
 while(out.length<n){
  const date=new Date(cursor),day=date.getUTCDay(),h=date.getUTCHours();
  const closed=(day===5&&h>=22)||day===6||
      (day===0&&h<23)||(day>=1&&day<=4&&h===22);
  // H4 bars beginning 20 UTC on Friday include an open-market overlap;
  // since candles span the reference close, include them as observed.
  if(!closed)out.push(row(cursor,n-out.length));
  cursor-=w;
 }
 return out.reverse();
}
const all=examine(Object.fromEntries(Object.keys(W).map(tf=>[tf,sessionRows(tf)])),NOW);
strict(all);
assert.equal(all.mode,"PRIVATE_MID_OBSERVED_EMA_REFERENCE_ONLY");
assert.equal(all.decisionReady,false);
assert.equal(all.alignmentForTrading,"NOT_ASSESSABLE");
for(const tf of ["M15","H1","H4"]){
 const x=all.frames[tf];
 strict(x);
 assert.ok(["REFERENCE_PAUSE_CANDIDATE_ONLY","NOT_ASSESSABLE"].includes(x.status));
 if(x.status==="REFERENCE_PAUSE_CANDIDATE_ONLY"){
   assert.ok(x.ema20>0);
   assert.ok(x.lastClose>0);
   assert.equal(x.reason,"REFERENCE_CALENDAR_NOT_UNDERLYING_BROKER_VERIFIED");
   assert.equal(x.missingDuringReferenceTradingHours,0);
   assert.equal(x.missingOutsideReference,0);
 }else assert.equal(x.ema20,null);
}
// A verified sample of a single daily pause can only be labelled as a candidate.
const h1=Array.from({length:48},(_,i)=>{
 const open=Date.parse("2026-11-16T00:00:00Z")+i*3600000;
 return row(open,i);
}).filter(x=>x.time!=="2026-11-16T22:00:00.000Z");
const candidate=frameCandidate(h1,"H1",Date.parse("2026-11-19T00:00:00Z"));
strict(candidate);
assert.equal(candidate.status,"REFERENCE_PAUSE_CANDIDATE_ONLY");
assert.equal(candidate.referencePauseCandidateSlots,1);
assert.equal(candidate.observedBars,47);
// Any missing candle during reference open market invalidates observed EMA.
const active=h1.filter(x=>x.time!=="2026-11-17T04:00:00.000Z");
const rejected=frameCandidate(active,"H1",Date.parse("2026-11-19T00:00:00Z"));
strict(rejected);
assert.equal(rejected.status,"NOT_ASSESSABLE");
assert.equal(rejected.ema20,null);
assert.equal(rejected.reason,"UNCLASSIFIED_OR_TRADING_TIME_GAP");
// No gap = existing strict 20-contiguous EMA, avoid duplicate display.
const noGap=frameCandidate(bars("M15"),"M15",NOW);
strict(noGap);
assert.equal(noGap.status,"NOT_ASSESSABLE");
assert.equal(noGap.reason,"NO_REFERENCE_PAUSE_TO_RESEARCH_USE_STRICT_EMA");
// Wrong alignment or open future candle is rejected.
const malformed=bars("M15"); malformed[0].time="2026-11-17T00:17:00Z";
const invalid=frameCandidate(malformed,"M15",NOW);
strict(invalid);
assert.equal(invalid.status,"NOT_ASSESSABLE");
assert.equal(invalid.ema20,null);
const forming=bars("H1");forming.at(-1).time=new Date(Math.floor(NOW/3600000)*3600000).toISOString();
assert.equal(frameCandidate(forming,"H1",NOW).status,"NOT_ASSESSABLE");
console.log("PASS reference-only EMA uses observed closed candles; reference pause hypothesis never becomes broker verification, signals remain WAIT");
