"use strict";
const assert=require("node:assert/strict");
const {candidateTime,auditRows}=require("./biquote_session_reference");
const ms=s=>Date.parse(s),r=s=>({time:s});
function verify(result,count,ref){
 assert.equal(result.signal,"WAIT");assert.equal(result.executable,false);
 assert.equal(result.brokerCalendarVerified,false);
 assert.equal(result.sessionCalendarVerified,false);
 assert.equal(result.bridgeBarsAllowed,false);
 assert.equal(result.gapCount,1);assert.equal(result.missingSlots,count);
 assert.equal(result.referencePauseCandidates,ref);
}
// Generic reference windows are hypotheses, never actual BiQuote permissions.
verify(auditRows([r("2026-11-16T21:45:00Z"),r("2026-11-16T23:00:00Z")],"M15"),4,4);
verify(auditRows([r("2026-11-16T21:00:00Z"),r("2026-11-16T23:00:00Z")],"H1"),1,1);
verify(auditRows([r("2026-11-13T20:00:00Z"),r("2026-11-15T20:00:00Z")],"H4"),11,11);
const bad=auditRows([r("2026-11-17T10:00:00Z"),r("2026-11-17T12:00:00Z")],"H1");
verify(bad,1,0);
assert.equal(bad.missingDuringReferenceTradingHours,1);
assert.equal(bad.examples[0].label,"MISSING_IN_REFERENCE_TRADING_HOURS");
assert.equal(candidateTime(ms("2026-11-15T22:45:00Z"),"M15"),true);
assert.equal(candidateTime(ms("2026-11-15T23:00:00Z"),"M15"),false);
assert.equal(candidateTime(ms("2026-11-13T12:00:00Z"),"M15"),false);
assert.equal(candidateTime(ms("2026-11-13T21:45:00Z"),"M15"),false);
assert.equal(candidateTime(ms("2026-11-13T22:00:00Z"),"M15"),true);
assert.equal(candidateTime(ms("2026-11-14T01:00:00Z"),"M15"),true);
assert.equal(candidateTime(ms("2026-11-13T20:00:00Z"),"H4"),false);
assert.equal(candidateTime(ms("2026-11-14T16:00:00Z"),"H4"),true);
assert.equal(candidateTime(ms("2026-08-17T22:00:00Z"),"M15"),null);
const invalid=auditRows([r("2026-11-17T10:00:00Z"),r("2026-11-17T10:00:00Z")],"M15");
assert.equal(invalid.error,"INVALID_OR_UNSORTED_CANDLE_OPEN");
assert.equal(invalid.executable,false);
assert.equal(invalid.sessionCalendarVerified,false);
const none=auditRows([],"H1");
assert.equal(none.error,"INVALID_INPUT");
const missing=auditRows([r("2026-11-17T10:00:00Z"),r("2026-11-17T12:00:00Z")],"H4");
assert.equal(missing.error,"MISALIGNED_CANDLE_GAP");
console.log("PASS BiQuote timestamp gap hypotheses: daily/weekend reference vs missing active hours, broker session NOT verified, fail WAIT");
