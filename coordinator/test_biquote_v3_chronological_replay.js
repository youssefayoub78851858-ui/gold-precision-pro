"use strict";
const a=require("node:assert/strict");
const {inspect}=require("./biquote_v3_chronological_replay");
const START=Date.parse("2026-11-18T00:00:00Z");
const iso=t=>new Date(t).toISOString().replace(".000Z","Z");
function sample(n=448){
 const m15=[];
 for(let i=0;i<n;i++){
  const o=2000+i*.06;
  m15.push({datetime:iso(START+i*900000),
   open:o,high:o+0.45,low:o-0.20,close:o+0.10});
 }
 const aggregate=(n)=>Array.from({length:Math.floor(m15.length/n)},(_,i)=>{
  const r=m15.slice(i*n,i*n+n);
  return{datetime:r[0].datetime,open:r[0].open,
   high:Math.max(...r.map(x=>x.high)),low:Math.min(...r.map(x=>x.low)),
   close:r.at(-1).close};
 });
 return {M15:m15,H1:aggregate(4),H4:aggregate(16)};
}
const frames=sample();
const origin={dataOrigin:"SYNTHETIC_TEST_ONLY",frames};
const good=inspect(origin);
a(good.retrospectiveDecisionCount>0);
a.equal(good.status,"RETROSPECTIVE_WATCH_COUNTS_ONLY");
a.equal(good.signal,"WAIT");a.equal(good.executable,false);
a.equal(good.paperOrdersAllowed,false);a.equal(good.liveOrdersAllowed,false);
a.equal(good.hypotheticalNetPnL,null);a.equal(good.winRate,null);
a.equal(good.individualCandleFirstAvailableUTCVerified,false);
a.equal(good.replayOnlyNotPointInTime,true);
a.equal(good.technicalWatchCounts.BUY+good.technicalWatchCounts.SELL+
 good.technicalWatchCounts.NONE,good.retrospectiveDecisionCount);
a.equal(good.providerRequestsMade,0);
a.equal(good.brokerOrdersSent,0);
const printed=JSON.stringify(good);
for(const s of ['"open"','"high"','"low"','"close"','"bid"','"ask"','"spread"'])
 a.equal(printed.includes(s),false,"No prices or quotes in report");
// Fixed cutoff makes previous observations immutable to future price edits.
const cutoff=iso(START+400*900000);
const before=inspect({...origin,decisionCutoffUTC:cutoff});
const changed=structuredClone(frames);
for(const f of Object.values(changed))
 for(const c of f)if(Date.parse(c.datetime)>=Date.parse(cutoff)){
  c.open+=500;c.high+=500;c.low+=500;c.close+=500;
 }
const after=inspect({...origin,frames:changed,decisionCutoffUTC:cutoff});
a.deepEqual(after,before,"Future candles must not alter a past replay");
const insufficient=inspect({...origin,frames:sample(200)});
a.equal(insufficient.status,"BLOCKED");
a.equal(insufficient.retrospectiveDecisionCount,0);
// Gaps are never stitched across an invented broker session.
// A gap before the 21st H4 leaves fewer than 21 on BOTH sides:
 // no old watch can be carried across an unclassified missing session.
const gapped=structuredClone(frames);gapped.H4.splice(20,1);
const noBridge=inspect({...origin,frames:gapped});
a.equal(noBridge.status,"BLOCKED");
a.equal(noBridge.technicalWatchCounts.BUY,0);
// Earlier covered H4/H1 bars must NOT mask a missing last closed candle.
const cutM15=frames.M15.slice(-128);
const cutH1=frames.H1.slice(-26);
const cutH4=frames.H4.slice(-7);
const {parity}=require("./biquote_v3_chronological_replay");
a.equal(parity({M15:cutM15,H1:cutH1,H4:cutH4}),true);
const latestH4Open=Date.parse(cutH4.at(-1).datetime);
const brokenH4={M15:cutM15.filter(x=>Date.parse(x.datetime)!==latestH4Open+15*900000),
 H1:cutH1,H4:cutH4};
a.equal(parity(brokenH4),false,
 "Missing one M15 in the LAST closed H4 must veto overlap proof");
const latestH1Open=Date.parse(cutH1.at(-1).datetime);
const brokenH1={M15:cutM15.filter(x=>Date.parse(x.datetime)!==latestH1Open+3*900000),
 H1:cutH1,H4:cutH4};
a.equal(parity(brokenH1),false,
 "Missing one M15 in the LAST closed H1 must veto overlap proof");
// A contradicting H4 close cannot be accepted as matched M15 geometry.
const conflict=structuredClone(frames);
for(const candle of conflict.H4)candle.high+=50;
a.equal(inspect({...origin,frames:conflict}).status,"BLOCKED");
// Rejected input never prints its price content.
for(const bad of [
 {...origin,dataOrigin:"LIVE_LICENSED"},
 {...origin,frames:{...frames,M15:[...frames.M15,{...frames.M15.at(-1)}]}},
 {...origin,frames:{...frames,H1:[{...frames.H1[0],open:NaN}]}},
 {...origin,decisionCutoffUTC:"tomorrow"}
]){
 const x=inspect(bad);a.equal(x.signal,"WAIT");a.equal(x.status,"BLOCKED");
 a.equal(x.retrospectiveDecisionCount,0);
}
console.log("PASS offline retrospective V3 watch, no-lookahead fixed cutoff, strict closed parity and gap veto, zero orders or actual net performance");
