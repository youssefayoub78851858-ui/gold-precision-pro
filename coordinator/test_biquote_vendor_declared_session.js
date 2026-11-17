"use strict";
const assert=require("node:assert/strict");
const {evaluateFrames,evaluateGap,slotClosed}=require("./biquote_vendor_declared_session");
const ms=s=>Date.parse(s),r=s=>({time:s});
function safe(x){
 assert.equal(x.signal,"WAIT");
 assert.equal(x.executable,false);
 assert.equal(x.tradeEligible,false);
 assert.equal(x.canIssueTradePlan,false);
 assert.equal(x.allowsGapBridging,false);
 assert.equal(x.originalBrokerUpstreamRightsWarranted,false);
 assert.equal(x.brokerIndependentScheduleVerified,false);
 assert.equal(x.providerSaysPrivateRenderResearchAllowed,true);
 assert.equal(x.dstChangesIndependentlyVerified,false);
}
assert.equal(slotClosed(ms("2026-11-16T22:00:00Z"),3600000),true);
assert.equal(slotClosed(ms("2026-11-16T21:00:00Z"),3600000),false);
assert.equal(slotClosed(ms("2026-11-13T21:45:00Z"),900000),false);
assert.equal(slotClosed(ms("2026-11-13T22:00:00Z"),900000),true);
assert.equal(slotClosed(ms("2026-11-14T08:00:00Z"),14400000),true);
assert.equal(slotClosed(ms("2026-11-15T20:00:00Z"),14400000),false);
assert.equal(slotClosed(ms("2026-11-15T22:45:00Z"),900000),true);
assert.equal(slotClosed(ms("2026-11-15T23:00:00Z"),900000),false);
// Provider warned DST shift; outside the supported November window
// no presumption of a fixed UTC schedule is allowed.
assert.equal(slotClosed(ms("2026-11-08T22:00:00Z"),900000),null);
assert.equal(slotClosed(ms("2026-12-01T22:00:00Z"),900000),null);
const daily=evaluateGap([
 r("2026-11-16T21:00:00Z"),r("2026-11-16T23:00:00Z")],"H1");
safe(daily);
assert.equal(daily.gapGroups,1);
assert.equal(daily.providerDeclaredPauseSlots,1);
assert.equal(daily.missingDuringProviderTradingSlots,0);
assert.equal(daily.examples[0].classification,"MATCHES_PROVIDER_DECLARED_CLOSURE_NOT_PROVEN");
const missed=evaluateGap([
 r("2026-11-17T10:00:00Z"),r("2026-11-17T12:00:00Z")],"H1");
safe(missed);
assert.equal(missed.gapGroups,1);
assert.equal(missed.providerDeclaredPauseSlots,0);
assert.equal(missed.missingDuringProviderTradingSlots,1);
assert.equal(missed.examples[0].classification,"MISSING_WHEN_PROVIDER_DECLARES_MARKET_OPEN");
const weekend=evaluateGap([
 r("2026-11-13T20:00:00Z"),r("2026-11-15T20:00:00Z")],"H4");
safe(weekend);
assert.equal(weekend.gapGroups,1);
assert.equal(weekend.missingSlots,11);
assert.equal(weekend.providerDeclaredPauseSlots,11);
const partialH4=evaluateGap([
 r("2026-11-16T16:00:00Z"),r("2026-11-17T00:00:00Z")],"H4");
safe(partialH4);
assert.equal(partialH4.providerDeclaredPauseSlots,0);
assert.equal(partialH4.missingDuringProviderTradingSlots,1);
const old=evaluateGap([
 r("2026-11-08T20:00:00Z"),r("2026-11-09T00:00:00Z")],"H1");
safe(old);
assert.equal(old.outsideDeclaredDateWindowSlots,3);
assert.equal(old.providerDeclaredPauseSlots,0);
assert.equal(old.missingDuringProviderTradingSlots,0);
const invalid=evaluateGap([r("2026-11-17T10:13:00Z"),r("2026-11-17T11:00:00Z")],"H1");
safe(invalid);
assert.equal(invalid.error,"BAD_BAR_ORDER_OR_GRID");
const all=evaluateFrames({
 M15:[r("2026-11-16T21:45:00Z"),r("2026-11-16T23:00:00Z")],
 H1:[r("2026-11-16T21:00:00Z"),r("2026-11-16T23:00:00Z")],
 H4:[r("2026-11-13T20:00:00Z"),r("2026-11-15T20:00:00Z")]
});
safe(all);
assert.deepEqual(Object.keys(all.frames),["M15","H1","H4"]);
for(const x of Object.values(all.frames))safe(x);
assert.equal(all.frames.M15.providerDeclaredPauseSlots,4);
assert.ok(!JSON.stringify(all).includes('"bid"'));
assert.ok(!JSON.stringify(all).includes('"ask"'));
console.log("PASS BiQuote support-declared November schedule audit: known pause vs missing-trading bars; DST and upstream unresolved; all WAIT");
