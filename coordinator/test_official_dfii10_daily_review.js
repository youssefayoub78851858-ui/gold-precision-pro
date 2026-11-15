'use strict';
const a=require('node:assert/strict');
const fs=require('node:fs');
const {reviewDFII10,compareNominal10Y}=require('./official_dfii10_daily_review');
const ASOF='2026-11-15T14:00:00Z',RECEIPT='2026-11-13T22:00:00Z';
const csv='observation_date,DFII10\n2026-11-06,2.63\n2026-11-09,2.66\n2026-11-10,2.78\n2026-11-11,.\n2026-11-12,2.86\n';
const mk=(s,extra={})=>reviewDFII10({csv:s,sourceDataMode:'SYNTHETIC_TEST_ONLY',
 asOfUTC:ASOF,receiptUTC:RECEIPT,...extra});
const yes=mk(csv);
a.equal(yes.status,'DAILY_REFERENCE_ONLY');
a.equal(yes.observationDate,'2026-11-12');
a.equal(yes.realYieldPercent,2.86);
a.equal(yes.priorObservedDate,'2026-11-10');
a.equal(yes.priorRealYieldPercent,2.78);
a.equal(yes.observedChangePercentagePoints,.08);
a.equal(yes.missingRows,1);
for(const flag of ['executable','researchEligible','paperOrdersAllowed','quoteLive',
 'firstAvailabilityVerified','historicalRevisionHistoryVerified',
 'pointInTimeBacktestEligible','intradayConfirmationEligible','licenseVerified'])
 a.equal(yes[flag],false,flag);
a.equal(yes.providerRequestsMade,0);a.equal(yes.ordersSent,0);
const recorded=mk(csv,{sourceDataMode:'LOCAL_RECORDED_UNVERIFIED'});
a.equal(recorded.status,'DAILY_REFERENCE_ONLY');
a.equal(recorded.firstAvailabilityVerified,false);
a.equal(recorded.pointInTimeBacktestEligible,false);
const nominal={
 mode:'OFFICIAL_RECORDED_DAILY_CONTEXT',sourceStatus:'OFFICIAL_FED_RSS_REFRESHED',
 allowedRole:'MACRO_DAILY_CONTEXT_ONLY',observedDate:'2026-11-12',
 rates:[{series:'DGS2',latestYieldPct:4.5},{series:'DGS10',latestYieldPct:4.15}]
};
const comparison=compareNominal10Y(yes,nominal);
a.equal(comparison.status,'DAILY_ARITHMETIC_ONLY');
a.equal(comparison.nominalMinusRealPercentagePoints,1.29);
a.equal(comparison.firstAvailabilityVerified,false);
a.equal(comparison.executable,false);
a.equal(compareNominal10Y(yes,{...nominal,observedDate:'2026-11-10'}).status,'BLOCKED');
a.equal(compareNominal10Y(yes,{...nominal,sourceStatus:'STORED_FALLBACK'}).status,'BLOCKED');
a.equal(compareNominal10Y(yes,{...nominal,rates:[]}).status,'BLOCKED');
const bad=[
 ['wrong headline','date,DFII10\n2026-11-12,2.86\n','DFII10_HEADER_OR_SIZE_INVALID'],
 ['duplicate','DATE,DFII10\n2026-11-12,2.86\n2026-11-12,2.90\n','DUPLICATE_OR_UNSORTED_OBSERVATION_DATE'],
 ['reversed','DATE,DFII10\n2026-11-12,2.86\n2026-11-11,.\n','DUPLICATE_OR_UNSORTED_OBSERVATION_DATE'],
 ['invalid date','DATE,DFII10\n2026-02-30,2.86\n','DUPLICATE_OR_UNSORTED_OBSERVATION_DATE'],
 ['nonfinite','DATE,DFII10\n2026-11-12,NaN\n','DFII10_DAILY_VALUE_INVALID'],
 ['huge','DATE,DFII10\n2026-11-12,999\n','DFII10_DAILY_VALUE_INVALID'],
 ['future observation','DATE,DFII10\n2026-11-14,2.86\n','FUTURE_OBSERVATION_RELATIVE_TO_RECEIPT'],
 ['no observation','DATE,DFII10\n2026-11-12,.\n','NO_OBSERVED_TIPS_YIELD']
];
for(const [name,raw,code] of bad) {
 const out=mk(raw);
 a.equal(out.status,'BLOCKED',name);
 a.equal(out.reasonCode,code,name);
 a.equal(out.signal,'WAIT');
}
a.equal(mk(csv,{receiptUTC:'2026-11-16T00:00:00Z'}).reasonCode,'INDEPENDENT_UTC_AND_KNOWN_RECEIPT_REQUIRED');
a.equal(mk(csv,{asOfUTC:'2026-11-30T00:00:00Z'}).reasonCode,'DAILY_REFERENCE_FUTURE_OR_STALE');
a.equal(mk(csv,{sourceDataMode:'LIVE_AUTHORIZED'}).status,'BLOCKED');
a.equal(mk(csv,{asOfUTC:'2026-11-15T14:00:00-05:00'}).status,'BLOCKED');
const src=fs.readFileSync(require.resolve('./official_dfii10_daily_review'),'utf8');
a(!/\bfetch\s*\(/.test(src));a(!/new\s+WebSocket\s*\(/.test(src));
a(!/process\.env/.test(src));
console.log('PASS DFII10 H15 offline CSV date/receipt, holiday missing, same-day nominal match, no false backtest or network admission');
