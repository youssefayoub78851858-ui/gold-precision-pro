"use strict";
const assert=require("node:assert/strict");
const {makeMtfReadiness}=require("./biquote_mtf_readiness");
const {analyzeChart}=require("./biquote_private_structure");
const NOW=Date.parse("2026-11-17T12:00:00Z");
const widths={M15:900000,H1:3600000,H4:14400000};
function chart(decreasing=false,partial=false){
 return Object.fromEntries(Object.entries(widths).map(([tf,w])=>{
   const end=Math.floor(NOW/w)*w;
   return [tf,Array.from({length:48},(_,i)=>{
     let t=end-(48-i)*w;
     if(partial&&tf!=="M15"&&i<38)t-=w; // gap before last ten
     const p=decreasing?4200-i*0.4:3900+i*0.4;
     return {time:new Date(t).toISOString(),
       open:p,high:p+0.8,low:p-0.8,close:p+0.2};
   })];
 }));
}
const quality=(incomplete=0,mismatch=0)=>({
 H1:{completeMatches:40,completeMismatches:0,incompleteM15Groups:0},
 H4:{completeMatches:9,completeMismatches:mismatch,incompleteM15Groups:incomplete}
});
function blocked(x){
 assert.equal(x.mode,"PRIVATE_READONLY_MTF_READINESS");
 assert.equal(x.signal,"WAIT");
 assert.equal(x.executable,false);
 assert.equal(x.researchEligible,false);
 assert.equal(x.tradeEligible,false);
 assert.equal(x.paperOrdersAllowed,false);
 assert.equal(x.validForEntry,false);
 assert.equal(x.sessionCalendarVerified,false);
 assert.equal(x.underlyingBrokerRightsVerified,false);
 assert.equal(x.macroAndNewsIntegrated,false);
 assert.equal(x.orderFlowIntegrated,false);
 assert.ok(x.blockerCodes.includes("BROKER_SESSION_CALENDAR_UNVERIFIED"));
 assert.ok(x.blockerCodes.includes("PROFITABILITY_NOT_INDEPENDENTLY_VALIDATED"));
 assert.ok(!("entry" in x)&&!("stopLoss" in x)&&!("takeProfit" in x));
}
let up=makeMtfReadiness(analyzeChart(chart(),NOW),quality());
blocked(up);
assert.equal(up.alignment,"OBSERVATION_ALL_ABOVE_EMA20");
assert.equal(up.quality,"MATCHED_COMPARED_WINDOWS_ONLY");
assert.equal(up.blockerCodes.includes("LESS_THAN_20_CONTIGUOUS_BARS_IN_HIGHER_FRAME"),false);
assert.deepEqual(up.framesRequired,["H4","H1","M15"]);
for(const tf of up.framesRequired){
 const x=up.frameSummaries[tf];
 assert.equal(x.direction,"ABOVE_EMA20");
 assert.equal(x.ema20Available,true);
 assert.equal(x.tradeEligible,false);
}
let down=makeMtfReadiness(analyzeChart(chart(true),NOW),quality());
blocked(down);
assert.equal(down.alignment,"OBSERVATION_ALL_BELOW_EMA20");
let gap=makeMtfReadiness(analyzeChart(chart(false,true),NOW),quality(3));
blocked(gap);
assert.equal(gap.alignment,"NOT_ASSESSABLE");
assert.equal(gap.quality,"PARTIAL_M15_CONSTITUENTS");
assert.ok(gap.blockerCodes.includes("LESS_THAN_20_CONTIGUOUS_BARS_IN_HIGHER_FRAME"));
assert.ok(gap.blockerCodes.includes("SESSION_GAPS_UNCLASSIFIED"));
assert.ok(gap.blockerCodes.includes("INCOMPLETE_M15_CONSTITUENTS"));
for(const tf of ["H1","H4"]){
 const item=gap.frameSummaries[tf];
 assert.equal(item.coverage,"PARTIAL_POST_GAP");
 assert.equal(item.contiguousBars,10);
 assert.equal(item.direction,"UNDETERMINED");
 assert.equal(item.ema20Available,false);
}
assert.equal(gap.frameSummaries.M15.coverage,"FULL_CONTIGUOUS_TECHNICAL");
const mismatch=makeMtfReadiness(analyzeChart(chart(),NOW),quality(0,1));
blocked(mismatch);
assert.equal(mismatch.quality,"OHLC_MISMATCH");
assert.ok(mismatch.blockerCodes.includes("CROSS_FRAME_OHLC_MISMATCH"));
const noParity=makeMtfReadiness(analyzeChart(chart(),NOW));
blocked(noParity);
assert.equal(noParity.quality,"UNVERIFIED");
assert.ok(noParity.blockerCodes.includes("CROSS_FRAME_QUALITY_NOT_PROVEN"));
// Tampered invalid evidence must never receive a plausible MTF alignment.
const corrupt=analyzeChart(chart(),NOW);
corrupt.frames.H4.executable=true;
const refused=makeMtfReadiness(corrupt,quality());
assert.equal(refused.state,"INVALID_INPUT_BLOCKED");
assert.equal(refused.signal,"WAIT");
assert.equal(refused.executable,false);
assert.equal(refused.alignment,"NOT_ASSESSABLE");
assert.deepEqual(refused.frameSummaries,{});
console.log("PASS private BiQuote MTF synthesis: H4/H1/M15 alignment, gap/parity guards, all paths WAIT and no trading");
