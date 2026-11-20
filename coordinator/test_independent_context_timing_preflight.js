"use strict";
const a=require("node:assert/strict");
const {inspect}=require("./independent_context_timing_preflight");
const K={
 DXY:"INDEX_QUOTE_NOT_EXCHANGE_DXY",
 GC_TRADES:"COMEX_GC_EXCHANGE_TRADES_NOT_CFD",
 GC_DEPTH:"COMEX_GC_MBP_OR_MBO_NOT_CFD",
 US02Y:"OFFICIAL_PUBLISHED_DAILY_YIELD",
 US10Y:"OFFICIAL_PUBLISHED_DAILY_YIELD",
 CALENDAR:"PUBLISHED_US_MACRO_CALENDAR",
 HEADLINES:"PUBLISHED_NEWS_HEADLINE"
};
const decision="2026-11-20T06:00:00Z",asOf="2026-11-20T06:01:00Z";
const item=(name,observed,available,received)=>({
 kind:K[name],observedUTC:observed,firstAvailableUTC:available,receivedUTC:received,
 ...(name.startsWith("GC_")?{contract:"GCZ2026"}:{})
});
const packet=()=>({
 origin:"UNATTESTED_SANITIZED_CONTEXT_TIMES_ONLY",
 decisionUTC:decision,asOfUTC:asOf,
 items:{
 DXY:item("DXY","2026-11-20T05:58:00Z","2026-11-20T05:58:01Z","2026-11-20T05:58:02Z"),
 GC_TRADES:item("GC_TRADES","2026-11-20T05:59:00Z","2026-11-20T05:59:01Z","2026-11-20T05:59:02Z"),
 GC_DEPTH:item("GC_DEPTH","2026-11-20T05:59:10Z","2026-11-20T05:59:11Z","2026-11-20T05:59:12Z"),
 US02Y:item("US02Y","2026-11-19T21:00:00Z","2026-11-19T21:01:00Z","2026-11-19T21:02:00Z"),
 US10Y:item("US10Y","2026-11-19T21:00:00Z","2026-11-19T21:01:00Z","2026-11-19T21:02:00Z"),
 CALENDAR:item("CALENDAR","2026-11-20T13:30:00Z","2026-11-19T08:00:00Z","2026-11-20T05:50:00Z"),
 HEADLINES:item("HEADLINES","2026-11-20T05:30:00Z","2026-11-20T05:30:01Z","2026-11-20T05:31:00Z")
 },
 privatePrice:"SECRET_QUOTE",
 apiKey:"NEVER_LEAK_SECRET",
 brokerRightsApproved:true
});
function safe(r){
 a.equal(r.mode,"GOLD_EXTERNAL_CONTEXT_TIMING_PREFLIGHT_OFFLINE_V1");
 a.equal(r.signal,"WAIT");
 for(const k of ["executable","researchEligible","recommendationAllowed",
  "tradeEligible","paperOrdersAllowed","liveOrdersAllowed",
  "sourceRightsVerified","independentFeedIdentityVerified",
  "brokerSessionVerified","comexOrderFlowLicensed",
  "macroPublicationIndependentlyVerified","allLayersQualified",
  "independentHoldoutValidated"])a.equal(r[k],false,k);
 a.equal(r.brokerOrdersSent,0);a.equal(r.paperOrdersSent,0);
 a.equal(r.providerRequestsMade,0);a.equal(r.verifiedLiveLayerCount,0);
 a.equal(r.requiredLayerCount,7);
 const raw=JSON.stringify(r);
 for(const secret of ["SECRET_QUOTE","NEVER_LEAK_SECRET",
  '"bid"','"ask"','"price"','"apiKey"'])a(!raw.includes(secret),secret);
 for(const f of Object.values(r.perLayer)){
  a.equal(f.sourceQualified,false);
 }
}
const perfect=inspect(packet());safe(perfect);
a.equal(perfect.status,"ONLY_UNATTESTED_CLOCKS_NOT_TRADING_PROOF");
a.deepEqual(perfect.summary,{recent:4,daily:2,scheduled:1,missing:0,blocked:0});
a.equal(perfect.perLayer.CALENDAR.status,"FUTURE_EVENT_SCHEDULE_ONLY");
a.equal(perfect.perLayer.US02Y.status,"DAILY_REFERENCE_ONLY_NOT_INTRADAY");
a.equal(perfect.perLayer.GC_TRADES.status,"PLAUSIBLE_UNATTESTED_CLOCK_ONLY");
a.equal(perfect.allLayersQualified,false);
a.equal(perfect.gcTradeDepthCrossCheck.status,
 "MATCHED_UNATTESTED_GC_LABELS_AND_CLOCKS_ONLY");
a.equal(perfect.gcTradeDepthCrossCheck.exchangeProven,false);
a.equal(perfect.gcTradeDepthCrossCheck.contractRollVerified,false);
const noGC=packet();delete noGC.items.GC_DEPTH;
const no=inspect(noGC);safe(no);
a.equal(no.status,"INCOMPLETE_CONTEXT");
a.equal(no.perLayer.GC_DEPTH.status,"MISSING");
a.equal(no.summary.missing,1);
const cases=[
 x=>{x.items.GC_DEPTH.receivedUTC="2026-11-20T06:00:01Z";},
 x=>{x.items.DXY.firstAvailableUTC="2026-11-20T06:01:00Z";},
 x=>{x.items.HEADLINES.observedUTC="2026-11-20T07:30:00Z";},
 x=>{x.items.HEADLINES.firstAvailableUTC="2026-11-20T05:00:00Z";},
 x=>{x.items.GC_TRADES.kind="CFD_XAUUSD_MARKET_LABELLED_COMEX";},
 x=>{x.items.GC_DEPTH.contract="GCG2027";},
 x=>{x.items.GC_TRADES.contract="XAUUSD";},
 x=>{x.items.GC_TRADES.contract="GCZ20_26";},
 x=>{x.items.GC_TRADES.contract=undefined;},
 x=>{x.items.GC_TRADES.observedUTC="2026-11-20T05:59:59Z";
      x.items.GC_TRADES.firstAvailableUTC="2026-11-20T05:59:59Z";
      x.items.GC_TRADES.receivedUTC="2026-11-20T05:59:59Z";
      x.items.GC_DEPTH.observedUTC="2026-11-20T05:58:01Z";
      x.items.GC_DEPTH.firstAvailableUTC="2026-11-20T05:58:02Z";
      x.items.GC_DEPTH.receivedUTC="2026-11-20T05:58:03Z";},
 x=>{x.items.GC_TRADES.kind="COMEX_GC_EXCHANGE_TRADES_NOT_CFD";x.items.GC_TRADES.observedUTC="2026-11-20T05:00:00Z";},
 x=>{x.items.US10Y.observedUTC="2026-11-01T21:00:00Z";},
 x=>{x.items.DXY.sourceRightsVerified=true;},
 x=>{x.items.DXY.receivedUTC="garbled";},
 x=>{x.items.DXY.firstAvailableUTC="2026-11-20T05:59:00Z";},
 x=>{x.items.CALENDAR.observedUTC="2026-11-20T05:00:00Z";
       x.items.CALENDAR.firstAvailableUTC="2026-11-19T08:00:00Z";},
];
for(const mutate of cases){
 const p=packet();mutate(p);
 const res=inspect(p);safe(res);
 a.equal(res.status,"CONTEXT_TIMING_CONFLICTS");
 a(res.summary.blocked>=1);
}
for(const bad of [
 {...packet(),origin:"BROKER_ATTESTED_BY_USER"},
 {...packet(),decisionUTC:"2026-11-20T09:00:00Z"},
 {...packet(),asOfUTC:"2026-11-20T06:00:00+00:00"},
 {...packet(),items:{...packet().items,XAUUSD:{}}},
 {...packet(),items:[]}
]){
 const res=inspect(bad);safe(res);a.equal(res.status,"BLOCKED");
}
const mismatched=packet();
mismatched.items.GC_DEPTH.contract="GCG2027";
const wrongContract=inspect(mismatched);safe(wrongContract);
a.equal(wrongContract.gcTradeDepthCrossCheck.status,"GC_CONTRACT_MISMATCH");
a.equal(wrongContract.perLayer.GC_TRADES.timeSuitable,false);
a.equal(wrongContract.perLayer.GC_DEPTH.timeSuitable,false);
a.equal(wrongContract.summary.blocked,2);
a.equal(wrongContract.summary.recent,2);
safe(inspect({}));safe(inspect(null));
console.log("PASS offline context time-preflight: no COMEX-CFD substitution, future macro actual, late news, daily yields remain daily, no orders");
