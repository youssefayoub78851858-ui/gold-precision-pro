'use strict';
const a=require('node:assert/strict');
const {inspectRanges,staticStatus}=require('./gold_api_ohlc_review');
const t=Date.parse('2026-11-10T08:00:00.000Z'),WIDTH=900000;
const data=(n)=>Array.from({length:n},(_,i)=>{
 const start=t+i*WIDTH,stamp=start/1000;
 return {httpStatus:200,requestStartTimestamp:stamp,requestEndTimestamp:stamp+900,
   response:{open:3900,high:3902,low:3898,close:3901,
     startTimestamp:stamp,endTimestamp:stamp+900}};
});
const opts=(rows)=>({
 asOfUTC:new Date(t+rows*WIDTH+60000).toISOString(),
 independentScheduleReference:'UNIT_TEST_INDEPENDENT_SESSION_ONLY',
 independentExpectedOpenTimes:Array.from({length:rows},(_,i)=>new Date(t+i*WIDTH).toISOString())
});
const s=staticStatus();
a.equal(s.monthlyUsd,10);
a.equal(s.signal,'WAIT');
a.equal(s.executable,false);
a.equal(s.premiumKeyConfigured,false);
a.equal(s.liveOHLCVerified,false);
a.equal(s.providerRequestsMade,0);
let report=inspectRanges(data(16),opts(16));
a.equal(report.geometryCheckPassed,true);
a.deepEqual(report.counts,{M15:16,H1:4,H4:1});
a.equal(report.researchEligible,false);
a.equal(report.signal,'WAIT');
a.equal(report.executable,false);
a.equal(report.brokerBidAskAvailable,false);
a.equal(report.finalizedSeriesVerified,false);
report=inspectRanges(data(800),opts(800));
a.equal(report.counts.H4,50);
a.equal(report.geometryCheckPassed,true);
a.equal(report.paperOrdersAllowed,false);
const probe=(f,expected)=>{const r=f();a.equal(r.status,'BLOCKED');a.ok(r.reasonCodes.includes(expected),JSON.stringify(r));a.equal(r.signal,'WAIT');a.equal(r.researchEligible,false);};
probe(()=>inspectRanges(data(16),{...opts(16),independentScheduleReference:''}),'INDEPENDENT_SESSION_CALENDAR_REQUIRED');
probe(()=>inspectRanges(data(15),opts(16)),'RANGE_COUNT_OR_SESSION_GAP');
probe(()=>{let d=data(16);d[3].requestStartTimestamp+=900;return inspectRanges(d,opts(16));},'RANGE_BOUNDARY_OR_PROVIDER_TIMESTAMP_MISMATCH');
probe(()=>{let d=data(16);d[1].response.high=3899;return inspectRanges(d,opts(16));},'INVALID_OHLC_VALUES');
probe(()=>{let d=data(16);d[1].response.close=Infinity;return inspectRanges(d,opts(16));},'INVALID_OHLC_VALUES');
probe(()=>{let d=data(16);d[4].httpStatus=401;return inspectRanges(d,opts(16));},'PREMIUM_OHLC_HTTP_OR_JSON_REJECTED');
probe(()=>inspectRanges(data(16),{...opts(16),asOfUTC:new Date(t+16*WIDTH).toISOString()}),'UNCLOSED_OR_UNSETTLED_M15');
probe(()=>{let p=opts(16);p.independentExpectedOpenTimes[2]=p.independentExpectedOpenTimes[1];return inspectRanges(data(16),p);},'UNVERIFIED_EXPECTED_BAR_ORDER');
console.log('PASS Gold API $10 Premium single-OHLC-range auditor: independent UTC schedule, complete H1/H4 math, HTTP/JSON refusal, no BID/ASK, no signal and WAIT');
