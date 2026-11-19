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
// Receipt-time replay excludes candles until their REAL LOCAL FIRST-SEEN
// timestamp, even if the historical OHLC was already closed. These are
// synthetic receipts, NEVER proof of independent live market delivery.
const known=Object.fromEntries(Object.entries(frames).map(([tf,rows])=>
 [tf,Object.fromEntries(rows.map(bar=>[
  bar.datetime,iso(Date.parse(bar.datetime)+
   ({M15:900000,H1:3600000,H4:14400000}[tf])+1000)
 ]))]));
const withReceipts=inspect({...origin,firstObservedClosedUTC:known});
const observed=withReceipts.firstSeenReceiptAudit;
a.equal(observed.signal,"WAIT");
a.equal(observed.executable,false);
a.equal(observed.paperOrdersAllowed,false);
a.equal(observed.independentReceiptVerified,false);
a.equal(observed.sourceRightsVerified,false);
a(observed.observedDecisionCount>0);
a.equal(observed.status,"LOCAL_RECEIPT_WATCHES_NOT_TRADE_PROOF");
a.equal(observed.netExpectancy,null);
// A collector decision may occur at millisecond precision, but only
// receipts <= the EXACT decision instant may enter point-in-time analysis.
const edge=START+400*900000;
const half=inspect({...origin,firstObservedClosedUTC:known,
 decisionCutoffUTC:iso(edge+500)});
const afterReceipt=inspect({...origin,firstObservedClosedUTC:known,
 decisionCutoffUTC:iso(edge+1500)});
a.equal(half.signalDataReadiness.asOfUTC,iso(edge+500));
a.equal(afterReceipt.signalDataReadiness.asOfUTC,iso(edge+1500));
a.equal(half.signalDataReadiness.signal,"WAIT");
a.equal(half.signalDataReadiness.brokerOrdersSent,0);
a.equal(half.signalDataReadiness.independentAvailabilityVerified,false);
a.equal(afterReceipt.signalDataReadiness.observedAtDecision.H4,
 half.signalDataReadiness.observedAtDecision.H4+1);
a.equal(afterReceipt.signalDataReadiness.observedAtDecision.M15,
 half.signalDataReadiness.observedAtDecision.M15+1);
const laterFirstSeen=Object.fromEntries(Object.entries(frames).map(([tf,rows])=>
 [tf,Object.fromEntries(rows.map(bar=>[
  bar.datetime,iso(START+500*900000)
 ]))]));
const delayed=inspect({...origin,firstObservedClosedUTC:laterFirstSeen});
a.equal(delayed.firstSeenReceiptAudit.observedDecisionCount,0);
a.equal(delayed.firstSeenReceiptAudit.status,"NO_TIME_ELIGIBLE_WATCHES");
const missingLegacy=structuredClone(known);
for(const key of Object.keys(missingLegacy.H4))delete missingLegacy.H4[key];
const legacy=inspect({...origin,firstObservedClosedUTC:missingLegacy});
a.equal(legacy.firstSeenReceiptAudit.observedDecisionCount,0);
a.equal(legacy.firstSeenReceiptAudit.legacyMissingReceiptCounts.H4,frames.H4.length);
for(const forged of [
 {...known,H4:{...known.H4,UNKNOWN:"2026-11-20T00:00:00Z"}},
 {...known,H1:{...known.H1,[frames.H1.at(-1).datetime]:"2026-11-18T00:00:00Z"}},
]){
 const bad=inspect({...origin,firstObservedClosedUTC:forged});
 a.equal(bad.firstSeenReceiptAudit.status,"BLOCKED");
 a.equal(bad.firstSeenReceiptAudit.observedDecisionCount,0);
}
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
