"use strict";
const assert=require("node:assert/strict");
const {stageOfficialContext,collectOfficialContext}=require("./official_context_stage");
const now="2026-11-12T17:00:00.000Z";
function macro(){
 return {mode:"OFFICIAL_MACRO_REVIEW",signal:"WAIT",executable:false,checkedUTC:now,
   feeds:{fed:"OFFICIAL_REFRESHED",bls:"OFFICIAL_REFRESHED"},
   calendar:[{kind:"CPI",scheduledUTC:"2026-11-12T17:20:00.000Z",
              source:"U.S. Bureau of Labor Statistics",eventType:"SCHEDULED_NOT_RELEASED"},
             {kind:"JOBS",scheduledUTC:"2026-11-12T21:00:00.000Z",
              source:"U.S. Bureau of Labor Statistics",eventType:"SCHEDULED_NOT_RELEASED"},
             {kind:"CPI",scheduledUTC:"2026-11-12T16:00:00.000Z",
              source:"Example Inc",eventType:"SCHEDULED_NOT_RELEASED"}],
   headlineReview:{status:"RESEARCH_ONLY",
     items:[{id:"fed-release-1",publishedUTC:"2026-11-12T16:59:00.000Z",
             availableUTC:"2026-11-12T17:00:00.000Z",
             category:"HAWKISH_MONETARY",goldPressure:"DOWNWARD_PRESSURE",
             confidence:"LOW",status:"RULE_TAGGED"}]}
 };
}
function daily(){
 return {mode:"OFFICIAL_RECORDED_DAILY_CONTEXT",signal:"WAIT",executable:false,
         allowedRole:"MACRO_DAILY_CONTEXT_ONLY",sourceStatus:"OFFICIAL_FED_RSS_REFRESHED",
         observedDate:"2026-11-11",
         rates:[{series:"DGS2",latestYieldPct:3.4},{series:"DGS10",latestYieldPct:4.1}]};
}
function assertSafe(x){
 assert.equal(x.signal,"WAIT");assert.equal(x.executable,false);
 assert.equal(x.researchEligible,false);assert.equal(x.directionalVote,false);
 assert.equal(x.geopoliticalWorldNewsCoverage,false);
 assert.equal(x.completeUsdCalendarCoverage,false);
 assert.equal(x.xauPrice,null);
 assert.ok(Object.values(x.ultimateLayerAdmission).every(v=>v===false));
}
(async()=>{
 const r=stageOfficialContext(macro(),daily(),now);
 assertSafe(r);
 assert.equal(r.sourceStatus.fed,"OFFICIAL_PARTIAL_ONLY");
 assert.equal(r.rates.length,2);
 assert.equal(r.rates[0].frequency,"DAILY_NOT_INTRADAY");
 assert.equal(r.calendar.length,2);
 assert.equal(r.headlines.length,1);
 assert.equal(r.headlines[0].confidence,"LOW");
 assert.equal(r.alerts.length,1);
 assert.equal(r.knownEventWindowVeto,true);
 const stale=stageOfficialContext({...macro(),checkedUTC:"2026-11-12T12:00:00.000Z"},daily(),now);
 assertSafe(stale);
 assert.equal(stale.calendar.length,0);
 assert.equal(stale.headlines.length,0);
 assert.ok(stale.blockingReasons.includes("BLS_CALENDAR_UNAVAILABLE_OR_STALE"));
 const unavailable=stageOfficialContext(macro(),{...daily(),sourceStatus:"STORED_FALLBACK"},now);
 assertSafe(unavailable);
 assert.equal(unavailable.rates.length,0);
 assert.ok(unavailable.blockingReasons.includes("H15_DAILY_CONTEXT_UNAVAILABLE_OR_FALLBACK"));
 const fake=stageOfficialContext({...macro(),signal:"BUY"},daily(),now);
 assertSafe(fake);
 assert.deepEqual(fake.blockingReasons,["OFFICIAL_CONTEXT_CONTRACT_INVALID"]);
 const offline=await collectOfficialContext({offline:true,nowMs:Date.parse(now),
   fetchFn:()=>{throw Error("NO_NETWORK");}});
 assertSafe(offline);
 assert.equal(offline.sourceStatus.fed,"UNAVAILABLE");
 assert.equal(offline.sourceStatus.bls,"UNAVAILABLE");
 assert.equal(offline.sourceRequestsMadeHere,0);
 console.log("PASS official Fed/BLS/H15 optional staging: partial coverage, blackout and WAIT only");
})().catch(e=>{console.error(e);process.exitCode=1});
