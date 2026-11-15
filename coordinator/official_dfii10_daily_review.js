'use strict';
// FRED DFII10 / Federal Reserve H.15 daily TIPS 10Y real-yield LOCAL FILE review.
// This file has no HTTP/SDK/secret/market/order side effects. Validating a CSV
// after retrieval CANNOT establish when any value first became available.
const SOURCE='https://fred.stlouisfed.org/series/DFII10';
const MAX_BYTES=1200000,MAX_ROWS=15000;
const unavailable=code=>({
 mode:'OFFLINE_DFII10_DAILY_REVIEW',status:'BLOCKED',reasonCode:code,
 signal:'WAIT',executable:false,researchEligible:false,
 paperOrdersAllowed:false,pointInTimeBacktestEligible:false,
 intradayConfirmationEligible:false,firstAvailabilityVerified:false,
 licenseVerified:false,providerRequestsMade:0,ordersSent:0
});
const iso=x=>typeof x==='string'&&/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,3})?Z$/.test(x)&&
 Number.isFinite(Date.parse(x))&&new Date(Date.parse(x)).toISOString().slice(0,19)===x.slice(0,19);
const date=x=>typeof x==='string'&&/^\d{4}-\d\d-\d\d$/.test(x)&&Number.isFinite(Date.parse(x+'T00:00:00Z'))&&
 new Date(Date.parse(x+'T00:00:00Z')).toISOString().slice(0,10)===x;
function reviewDFII10({csv,sourceDataMode,asOfUTC,receiptUTC}={}){
 if(!['SYNTHETIC_TEST_ONLY','LOCAL_RECORDED_UNVERIFIED'].includes(sourceDataMode))
  return unavailable('EXPLICIT_LOCAL_UNVERIFIED_OR_SYNTHETIC_ORIGIN_REQUIRED');
 if(!iso(asOfUTC)||!iso(receiptUTC)||Date.parse(receiptUTC)>Date.parse(asOfUTC))
  return unavailable('INDEPENDENT_UTC_AND_KNOWN_RECEIPT_REQUIRED');
 if(typeof csv!=='string'||Buffer.byteLength(csv,'utf8')>MAX_BYTES||csv.includes('\0'))
  return unavailable('UNSUPPORTED_OR_OVERSIZE_CSV');
 const normalized=csv.replace(/^\uFEFF/,'').replace(/\r\n/g,'\n').trim();
 const lines=normalized.split('\n');
 if(lines.length<2||lines.length>MAX_ROWS+1||
    !['observation_date,DFII10','DATE,DFII10'].includes(lines[0]))
  return unavailable('DFII10_HEADER_OR_SIZE_INVALID');
 let last='',total=0,missing=0,latest=null,prior=null;
 for(let i=1;i<lines.length;i++){
  const line=lines[i];
  const chunks=line.split(',');
  if(chunks.length!==2||!date(chunks[0])||chunks[0]<=last)
   return unavailable('DUPLICATE_OR_UNSORTED_OBSERVATION_DATE');
  last=chunks[0];total++;
  const v=chunks[1].trim();
  if(v===''||v==='.'){missing++;continue;}
  if(!/^-?\d{1,2}(?:\.\d{1,6})?$/.test(v))
   return unavailable('DFII10_DAILY_VALUE_INVALID');
  const y=Number(v);
  if(!Number.isFinite(y)||y< -20||y>30)
   return unavailable('DFII10_DAILY_VALUE_INVALID');
  const obsMs=Date.parse(chunks[0]+'T00:00:00Z');
  if(obsMs>Date.parse(receiptUTC))
   return unavailable('FUTURE_OBSERVATION_RELATIVE_TO_RECEIPT');
  prior=latest;
  latest={observationDate:chunks[0],realYieldPercent:y};
 }
 if(!latest)return unavailable('NO_OBSERVED_TIPS_YIELD');
 const latestAge=(Date.parse(asOfUTC)-Date.parse(latest.observationDate+'T00:00:00Z'))/86400000;
 if(latestAge<0||latestAge>14)return unavailable('DAILY_REFERENCE_FUTURE_OR_STALE');
 return {
  mode:'OFFLINE_DFII10_DAILY_REVIEW',
  status:'DAILY_REFERENCE_ONLY',
  source:'Board of Governors of the Federal Reserve System, H.15 via FRED',
  sourceURL:SOURCE,
  sourceDataMode,receiptUTC,asOfUTC,
  observationDate:latest.observationDate,
  realYieldPercent:latest.realYieldPercent,
  priorObservedDate:prior?.observationDate??null,
  priorRealYieldPercent:prior?.realYieldPercent??null,
  observedChangePercentagePoints:prior?Number((latest.realYieldPercent-prior.realYieldPercent).toFixed(6)):null,
  validatedRows:total,missingRows:missing,
  firstAvailabilityVerified:false,historicalRevisionHistoryVerified:false,
  pointInTimeBacktestEligible:false,
  intradayConfirmationEligible:false,
  quoteLive:false,licenseVerified:false,sourceRequestsMade:0,providerRequestsMade:0,
  ordersSent:0,researchEligible:false,paperOrdersAllowed:false,signal:'WAIT',executable:false,
  warning:'The receipt is NOT the first availability timestamp. DFII10 is a published DAILY real-yield reference, not an intraday Treasury confirmation or validated trading feed.'
 };
}
function compareNominal10Y(real,nominal){
 if(!real||real.status!=='DAILY_REFERENCE_ONLY'||real.mode!=='OFFLINE_DFII10_DAILY_REVIEW'||
    real.firstAvailabilityVerified!==false||real.executable!==false||
    !nominal||nominal.mode!=='OFFICIAL_RECORDED_DAILY_CONTEXT'||
    nominal.sourceStatus!=='OFFICIAL_FED_RSS_REFRESHED'||
    nominal.allowedRole!=='MACRO_DAILY_CONTEXT_ONLY'||
    real.observationDate!==nominal.observedDate||!Array.isArray(nominal.rates))
  return unavailable('MATCHED_FED_H15_NOMINAL_DATE_OR_PROVENANCE_MISSING');
 const dgs10=nominal.rates.filter(x=>x?.series==='DGS10');
 if(dgs10.length!==1||!Number.isFinite(dgs10[0].latestYieldPct)||
    dgs10[0].latestYieldPct<=0)
  return unavailable('MATCHED_H15_DGS10_MISSING');
 const nominal10y=dgs10[0].latestYieldPct;
 return {
  mode:'OFFLINE_DFII10_H15_DAILY_COMPARISON',
  status:'DAILY_ARITHMETIC_ONLY',
  observationDate:real.observationDate,
  realYieldPercent:real.realYieldPercent,
  nominalYieldPercent:nominal10y,
  nominalMinusRealPercentagePoints:Number((nominal10y-real.realYieldPercent).toFixed(6)),
  sourceDataMode:real.sourceDataMode,
  sourceRequestsMade:0,providerRequestsMade:0,
  firstAvailabilityVerified:false,pointInTimeBacktestEligible:false,
  researchEligible:false,intradayConfirmationEligible:false,
  paperOrdersAllowed:false,signal:'WAIT',executable:false,
  warning:'Approximate breakeven only; cross-series release time and historical revision timestamps are unverified.'
 };
}
module.exports={reviewDFII10,compareNominal10Y};
