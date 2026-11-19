"use strict";
const a=require("node:assert/strict");
const {observe}=require("./biquote_vendor_h4_session_tail");
const H4=4*3600000;
const ts=s=>Date.parse(s);
const iso=n=>new Date(n).toISOString();
function rows(base,n){
 return Array.from({length:n},(_,i)=>({
  time:iso(ts(base)+i*H4),open:2000,high:2001,low:1999,close:2000.5
 }));
}
const pre=rows("2026-11-13T20:00:00Z",1);
const extraPre=rows("2026-11-12T08:00:00Z",9);
const post=rows("2026-11-15T20:00:00Z",15);
const fixture=()=>({
 origin:"AUTHENTICATED_PERSONAL_BIQUOTE_PRIVATE_CHART",
 asOfUTC:"2026-11-18T09:00:00Z",
 h4:[...extraPre,...pre,...post],
 privateToken:"NEVER_PUBLIC_TOKEN",
 brokerMarketCalendarVerified:true,tradeSignal:"BUY"
});
function safe(x){
 a.equal(x.mode,"BIQUOTE_VENDOR_DECLARED_H4_ADJACENCY_RESEARCH_ONLY");
 a.equal(x.signal,"WAIT");a.equal(x.technicalCandidate,"NONE");
 a.equal(x.executable,false);a.equal(x.paperOrdersAllowed,false);
 a.equal(x.liveOrdersAllowed,false);a.equal(x.brokerOrdersSent,0);
 a.equal(x.paperOrdersSent,0);a.equal(x.providerRequestsMade,0);
 a.equal(x.originalBrokerCalendarVerified,false);
 a.equal(x.brokerMarketDataRightsVerified,false);
 a.equal(x.all21H4M15ParityVerified,false);
 a.equal(x.perBarFirstSeenVerified,false);
 a.equal(x.researchWarmupApproved,false);
 a.equal(x.missingCandlesSynthesized,0);
 a(!JSON.stringify(x).includes("NEVER_PUBLIC_TOKEN"));
 for(const prop of ['"open"','"high"','"low"','"close"','"bid"','"ask"'])
  a(!JSON.stringify(x).includes(prop),prop);
}
// A bogus weekend bar must not be counted as a real session candle.
const impossibleWeekend=fixture();
impossibleWeekend.h4.splice(10,0,{
 time:"2026-11-14T04:00:00.000Z",
 open:2000,high:2001,low:1999,close:2000.5
});
const implausible=observe(impossibleWeekend);safe(implausible);
a.equal(implausible.status,"WAIT_SOURCE_SCHEDULE_CONTRADICTION");
a.equal(implausible.reason,"OBSERVED_H4_INSIDE_PROVIDER_DECLARED_FULL_CLOSURE");
a.equal(implausible.providerScenarioReached21H4,false);
const actual=observe(fixture());safe(actual);
a.equal(actual.status,"PROVIDER_DECLARED_PAUSE_SCENARIO_NOT_TRADING_PROOF");
a.equal(actual.observedClosedH4Bars,25);
a.equal(actual.strictUtcH4Tail,15);
a.equal(actual.providerDeclaredSessionAdjacentH4Tail,25);
a.equal(actual.providerDeclaredPauseGapPairs,1);
a.equal(actual.providerDeclaredPauseMissingH4Slots,11);
a.equal(actual.unexplainedGapPairs,0);
a.equal(actual.unknownCalendarGapPairs,0);
a.equal(actual.providerScenarioReached21H4,true);
a.equal(actual.researchWarmupApproved,false);
// The same timestamp gap inside DECLARED TRADING hours must never count.
const missingInside=fixture();
missingInside.h4=missingInside.h4.filter(x=>x.time!=="2026-11-17T04:00:00.000Z");
const broken=observe(missingInside);safe(broken);
a.equal(broken.status,"PROVIDER_DECLARED_PAUSE_SCENARIO_NOT_TRADING_PROOF");
a.equal(broken.unexplainedGapPairs,1);
a.equal(broken.strictUtcH4Tail,6);
a.equal(broken.providerDeclaredSessionAdjacentH4Tail,6);
a.equal(broken.providerScenarioReached21H4,false);
// A gap outside support's Nov2..Nov29 scope cannot be deemed closed.
const beyond=observe({...fixture(),asOfUTC:"2026-12-01T12:00:00Z",
 h4:[...rows("2026-11-29T20:00:00Z",1),...rows("2026-12-01T00:00:00Z",2)]});
safe(beyond);a.equal(beyond.unknownCalendarGapPairs,1);
a.equal(beyond.providerDeclaredSessionAdjacentH4Tail,2);
// All missing periods are necessary. Mixed pause + active missing is NOT
// a declared-only gap even if 11 of the slots fit support's weekend.
const mixed=observe({...fixture(),h4:[
 ...extraPre,...pre,...rows("2026-11-16T00:00:00Z",9)
]});
safe(mixed);
a.equal(mixed.unexplainedGapPairs,1);
a.equal(mixed.providerDeclaredSessionAdjacentH4Tail,9);
for(const mutate of [
 x=>{x.origin="PUBLIC_ANONYMOUS";},
 x=>{x.asOfUTC="INVALID";},
 x=>{x.h4.reverse();},
 x=>{x.h4[5].time=x.h4[4].time;},
 x=>{x.h4[4].time="2026-11-13T10:00:00Z";},
 x=>{x.h4.at(-1).time="2026-11-20T00:00:00Z";},
 x=>{x.h4[9].low=2500;},
 x=>{x.h4[9].close=NaN;},
 x=>{x.h4=[];},
 x=>{delete x.h4;},
 ]){
 const x=fixture();mutate(x);const y=observe(x);safe(y);
 a.equal(y.status,"BLOCKED");a.equal(y.providerScenarioReached21H4,false);
}
safe(observe({}));
console.log("PASS provider-declared H4 research adjacency: 25 observed across 11 closed slots, 15 strict, unverified broker, unknown/open gaps block, no orders");
