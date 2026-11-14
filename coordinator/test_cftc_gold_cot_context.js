'use strict';
const assert=require('node:assert/strict');
const {DATASET,CODE,MARKET,reviewCFTC,getCFTCGoldWeekly}=require('./cftc_gold_cot_context');
const asOf='2026-11-14T18:00:00.000Z';
const first={market_and_exchange_names:MARKET,cftc_contract_market_code:CODE,
 report_date_as_yyyy_mm_dd:'2026-11-03T00:00:00.000',
 open_interest_all:'400000',m_money_positions_long_all:'120000',
 m_money_positions_short_all:'80000'};
const previous={...first,report_date_as_yyyy_mm_dd:'2026-10-27T00:00:00.000',
 m_money_positions_long_all:'115000'};
const good=reviewCFTC([first,previous],asOf);
assert.equal(good.status,'WEEKLY_REFERENCE_ONLY');
assert.equal(good.managedMoneyNetContracts,40000);
assert.equal(good.previousNetContracts,35000);
assert.equal(good.observationDate,'2026-11-03');
assert.equal(good.backtestAsOfAdmission,false);
assert.equal(good.historicalReleaseTimingProven,false);
assert.equal(good.signal,'WAIT');
assert.equal(good.executable,false);
assert.equal(good.researchEligible,false);
assert.equal(good.orderFlowAvailable,false);
const rejected=(r,code)=>{const x=reviewCFTC(r,asOf);assert.equal(x.status,'BLOCKED');assert.equal(x.reasonCode,code);assert.equal(x.signal,'WAIT');};
rejected([],'CFTC_DATASET_EMPTY_OR_OVERSIZE');
rejected([{...first,cftc_contract_market_code:'123456'}],'CFTC_GOLD_CONTRACT_OR_SCHEMA_MISMATCH');
rejected([{...first,market_and_exchange_names:'SILVER - COMMODITY EXCHANGE INC.'}],'CFTC_GOLD_CONTRACT_OR_SCHEMA_MISMATCH');
rejected([{...first,report_date_as_yyyy_mm_dd:'2026-11-17T00:00:00.000'}],'CFTC_REPORT_DATE_OR_POSITIONS_INVALID');
rejected([{...first,m_money_positions_long_all:'100000000'}],'CFTC_REPORT_DATE_OR_POSITIONS_INVALID');
rejected([first,first],'CFTC_REPORT_DATE_OR_POSITIONS_INVALID');
rejected([{...first,report_date_as_yyyy_mm_dd:'2026-08-01T00:00:00.000'}],'CFTC_WEEKLY_REPORT_STALE');
(async()=>{
 let requests=0;
 const offline=await getCFTCGoldWeekly({offline:true});assert.equal(offline.status,'BLOCKED');assert.equal(requests,0);
 const fake=async url=>{
  requests++;assert.equal(new URL(url).origin,'https://publicreporting.cftc.gov');
  assert.equal(new URL(url).searchParams.get('$limit'),'2');
  return {ok:true,text:async()=>JSON.stringify([first,previous])};
 };
 const live=await getCFTCGoldWeekly({offline:false,fetchFn:fake,nowMs:Date.parse(asOf)});
 assert.equal(live.status,'WEEKLY_REFERENCE_ONLY');assert.equal(live.requestCount,1);
 const again=await getCFTCGoldWeekly({offline:false,fetchFn:()=>{throw Error('duplicate call');},nowMs:Date.parse(asOf)+1000});
 assert.equal(again.managedMoneyNetContracts,40000);assert.equal(requests,1);
 console.log('PASS CFTC free weekly gold COT: official code, full schema, date, stale/replay, cache and NO real-time/trading vote');
})().catch(e=>{console.error(e);process.exitCode=1;});
