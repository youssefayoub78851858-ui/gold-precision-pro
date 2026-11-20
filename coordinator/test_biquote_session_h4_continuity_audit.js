"use strict";
const a=require("node:assert/strict");
const {inspect}=require("./biquote_session_h4_continuity_audit");
const {slotClosed}=require("./biquote_vendor_declared_session");
const ORIGIN="UNATTESTED_VENDOR_NOV2026_H4_OPEN_AND_RECEIPT_TIMES_ONLY";
const iso=t=>new Date(t).toISOString().replace(".000Z","Z");
const bar=(open,seen)=>({openUTC:open,firstSeenClosedUTC:seen});
const bars=[
 bar("2026-11-20T16:00:00Z","2026-11-20T20:00:30Z"),
 bar("2026-11-20T20:00:00Z","2026-11-22T23:01:00Z"),
 bar("2026-11-22T20:00:00Z","2026-11-23T00:00:30Z"),
 bar("2026-11-23T00:00:00Z","2026-11-23T04:00:30Z"),
 bar("2026-11-23T04:00:00Z","2026-11-23T08:00:30Z")
];
const packet=(b=bars,asOfUTC="2026-11-23T09:00:00Z")=>({
 origin:ORIGIN,asOfUTC,bars:b,sourceRightsVerified:true,
 licensedExchange:true,bid:98235.12,token:"PRIVATE_KEY_DO_NOT_ECHO"
});
function safe(r){
 a.equal(r.mode,"BIQUOTE_VENDOR_SESSION_H4_OFFLINE_DIAGNOSTIC_V1");
 a.equal(r.signal,"WAIT");
 for(const flag of ["executable","tradeEligible","recommendationAllowed",
 "paperOrdersAllowed","liveOrdersAllowed","sourceRightsVerified",
 "originalBrokerIdentified","originalBrokerSessionCalendarVerified",
 "marketCalendarIndependentlyVerified","firstSeenVendorAuthenticated",
 "independentOHLCParityVerified","brokerBidAskCostsVerified",
 "forwardHoldoutProven","tradeAdmissionPossible"])a.equal(r[flag],false,flag);
 a.equal(r.brokerOrdersSent,0);a.equal(r.paperOrdersSent,0);
 a.equal(r.providerRequestsMade,0);
 a.equal(r.providerDeclaredScheduleOnly,true);
 const v=JSON.stringify(r);
 for(const secret of ["PRIVATE_KEY_DO_NOT_ECHO",'98235.12',
  '"bid"','"ask"','"openUTC"','"firstSeenClosedUTC"','"token"'])
  a(!v.includes(secret),secret);
}
const got=inspect(packet());safe(got);
a.equal(got.status,"VENDOR_CONDITIONAL_COUNTS_ONLY_NOT_TRADE_READY");
a.equal(got.barsWithLocalReceipt,5);
a.equal(got.rawUtcGridTail,3);
a.equal(got.vendorConditionalSessionTail,5);
a.equal(got.providerDeclaredFullyClosedH4SlotsBridged,11);
a.equal(got.missingProviderOpenH4Slots,0);
a.equal(got.unknownScheduleSlots,0);
a.equal(got.conditional21H4Reached,false);
a.equal(got.conditional50H4Reached,false);
a.equal(slotClosed(Date.parse("2026-11-21T04:00:00Z"),14400000),true);
// An H4 bar missing while the vendor says that 4h slot can trade
// breaks the CONDITIONAL session sequence. It is not a "weekend".
const openGap=inspect(packet([...bars,
 bar("2026-11-23T12:00:00Z","2026-11-23T16:00:10Z")],
 "2026-11-23T17:00:00Z"));safe(openGap);
a.equal(openGap.status,"VENDOR_CONDITIONAL_COUNTS_ONLY_NOT_TRADE_READY");
a.equal(openGap.vendorConditionalSessionTail,1);
a.equal(openGap.missingProviderOpenH4Slots,1);
// Two full business weeks in a SYNTHETIC vendor calendar can contain 50
// eligible H4 bars, despite the impossible 50*4h strict UTC tail.
// This is NOT evidence of original MT5 calendar or feed permissions.
const stream=[];
for(let t=Date.parse("2026-11-02T00:00:00Z");
 t<Date.parse("2026-11-14T00:00:00Z");t+=14400000){
 if(slotClosed(t,14400000)===false)
  stream.push(bar(iso(t),iso(t+14400000+1000)));
}
const twoWeeks=inspect(packet(stream,"2026-11-16T02:00:00Z"));
safe(twoWeeks);
a.equal(twoWeeks.status,"VENDOR_CONDITIONAL_COUNTS_ONLY_NOT_TRADE_READY");
a(twoWeeks.barsWithLocalReceipt>=50);
a(twoWeeks.vendorConditionalSessionTail>=50);
a(twoWeeks.rawUtcGridTail<50);
a.equal(twoWeeks.conditional50H4Reached,true);
a.equal(twoWeeks.tradeAdmissionPossible,false);
a.equal(twoWeeks.originalBrokerSessionCalendarVerified,false);
const fail=[
 {...packet(),origin:"BROKER_CERTIFIED"},
 packet([bar("2026-11-21T04:00:00Z","2026-11-21T08:00:10Z")]),
 packet([bars[0],bars[0]]),
 packet([bars[1],bars[0]]),
 packet([{...bars[0],price:100}]),
 packet([{...bars[0],firstSeenClosedUTC:"2026-11-20T18:00:00Z"}]),
 packet([{...bars[0],firstSeenClosedUTC:"2026-11-23T10:00:00Z"}]),
 packet([{...bars[0],openUTC:"2026-11-20T17:00:00Z"}]),
 packet([{...bars[0],openUTC:"2026-12-01T00:00:00Z",
  firstSeenClosedUTC:"2026-12-01T04:00:01Z"}],
  "2026-12-01T05:00:00Z"),
 packet([bars[0],{...bars[1],firstSeenClosedUTC:
  "2026-11-20T23:00:00Z"},bars[2]]),
 {...packet(),asOfUTC:"2026-11-23T09:00:00+00:00"},
 {...packet(),bars:"invalid"},
 {...packet(),bars:Array.from({length:251},()=>bars[0])},
];
for(const bad of fail){
 const out=inspect(bad);safe(out);a.equal(out.status,"BLOCKED",out.reason);
}
safe(inspect({}));safe(inspect(null));
const empty=inspect(packet([]));safe(empty);
a.equal(empty.status,"NO_OBSERVED_H4");
console.log("PASS offline 24/5 H4 session-continuity diagnostic: weekend no fake bars, missing open slot breaks, still no trading");
