"use strict";
// Tests only the EXISTING local BID development recordings; never market data.
const assert=require("node:assert/strict");
const fs=require("node:fs"),path=require("node:path");
const {inspect}=require("./archived_bid_cost_sensitivity");
const report=inspect();
assert.equal(report.signal,"WAIT");
assert.equal(report.executable,false);
assert.equal(report.tradeEligible,false);
assert.equal(report.paperOrdersAllowed,false);
assert.equal(report.providerRequestsMade,0);
assert.equal(report.ordersSent,0);
assert.equal(report.strategyChanged,false);
assert.equal(report.isIndependentHoldout,false);
assert.equal(report.independentHoldoutRequired,true);
assert.equal(report.tradingReady,false);
assert.equal(report.independentPerformanceProven,false);
assert.equal(report.empiricalWinProbability,null);
assert.equal(report.realBrokerHistoricalSpreadKnown,false);
assert.equal(report.historicalSlippageCommissionKnown,false);
assert.equal(report.sourceAuthenticityIndependentlyVerified,false);
assert.equal(report.notUltimateV3Performance,true);
assert.equal(report.archivedBidM15Bars,4884);
assert.equal(report.archivedAskM15Bars,0);
assert.deepEqual(report.scenariosUSDperOz,[0.4,0.8,1.2]);
assert.equal(report.periods.length,2);
assert.equal(report.periods.reduce((a,p)=>a+p.m15Bars,0),4884);
for(const p of report.periods){
 const expected=p.file.startsWith("2026-09")?2448:2436;
 assert.equal(p.m15Bars,expected);
 assert.equal(p.priceBasis,"BID_ONLY");
 assert.match(p.sha256,/^[a-f0-9]{64}$/);
 for(const x of p.scenarios){
  assert.equal(typeof x.assumedRoundTripPriceFrictionUSDperOz,"number");
  assert.ok(x.closedTrades>=0&&x.rawHistoricalSignals>=x.closedTrades);
  assert.ok(x.openAtEnd===0||x.openAtEnd===1);
  assert.ok(Math.abs(x.grossR-x.assumedFrictionR-x.netR)<.000003);
 }
 for(let i=1;i<p.scenarios.length;i++){
  const higher=p.scenarios[i],lower=p.scenarios[i-1];
  assert.equal(higher.closedTrades,lower.closedTrades);
  assert.equal(higher.rawHistoricalSignals,lower.rawHistoricalSignals);
  assert.equal(higher.grossR,lower.grossR);
  assert.ok(higher.netR<=lower.netR+0.000001);
  assert.ok(higher.assumedFrictionR>=lower.assumedFrictionR);
 }
}
for(let i=0;i<3;i++){
 const x=report.aggregate[i];
 assert.equal(x.closedTrades,report.periods.reduce((a,p)=>a+p.scenarios[i].closedTrades,0));
 assert.ok(Math.abs(x.netR-report.periods.reduce((a,p)=>a+p.scenarios[i].netR,0))<.000003);
 assert.equal(x.maxDrawdownR,null); // no invented cross-month capital curve
}
assert.deepEqual(inspect(),report);
const code=fs.readFileSync(path.join(__dirname,"archived_bid_cost_sensitivity.js"),"utf8");
assert.ok(!/\bfetch\s*\(|\bWebSocket\b|process\.env|https?:\/\/|child_process/.test(code));
console.log("PASS actual historical BID-only development archive sensitivity and all cost invariants, no out-of-sample claims/trades");
