'use strict';
// Offline research-only FX basket proxy. The weights are from the public ICE
// Dollar Index FAQ: https://www.ice.com/publicdocs/futures_us/ICE_Dollar_Index_FAQ.pdf
// Not an ICE index quote, not a licensed official DXY substitute or a trade vote.
// Does not contact providers, handle credentials, or admit live data.
const weights=Object.freeze({EURUSD:-.576,USDJPY:.136,GBPUSD:-.119,USDCAD:.091,USDSEK:.042,USDCHF:.036});
const keys=Object.keys(weights);
const iso=/^20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,3})?Z$/;
function utc(s){
 if(typeof s!=='string'||!iso.test(s))return NaN;
 const t=Date.parse(s);
 return Number.isFinite(t)&&new Date(t).toISOString().slice(0,19)===s.slice(0,19)?t:NaN;
}
function result(reason,value=null){
 return {mode:'OFFLINE_SYNTHETIC_FX_BASKET_PROXY',reason,proxyValue:value,
 officialDxy:false,sourceRightsVerified:false,marketDataVerified:false,
 researchEligible:false,directionalVote:false,signal:'WAIT',executable:false,
 paperOrdersAllowed:false,providerRequestsMade:0};
}
function calculate(input){
 if(input?.origin!=='SYNTHETIC_TEST_ONLY')return result('SYNTHETIC_ONLY');
 const decision=utc(input.decisionUTC),rows=input.quotes;
 if(!Number.isFinite(decision)||!rows||typeof rows!=='object'||Array.isArray(rows)||
    Object.keys(rows).sort().join(',')!==keys.slice().sort().join(','))
  return result('SIX_PAIRS_AND_VALID_CLOCK_REQUIRED');
 let log= Math.log(50.14348112),oldest=Infinity,newest=-Infinity;
 for(const pair of keys){
  const q=rows[pair];
  if(!q||typeof q!=='object'||Array.isArray(q)||
     Object.keys(q).sort().join(',')!=='ask,bid,observedUTC,receivedUTC')
   return result('INVALID_QUOTE_SHAPE');
  const t=utc(q.observedUTC),r=utc(q.receivedUTC);
  if(!Number.isFinite(t)||!Number.isFinite(r)||t>r||r>decision||decision-t>30000)
   return result('STALE_OR_FUTURE_QUOTE');
  if(typeof q.bid!=='number'||typeof q.ask!=='number'||!Number.isFinite(q.bid)||
     !Number.isFinite(q.ask)||q.bid<=0||q.ask<q.bid)
   return result('INVALID_OR_CROSSED_QUOTE');
  const mid=q.bid/2+q.ask/2;
  if((q.ask-q.bid)/mid>.01)return result('EXCESSIVE_RELATIVE_SPREAD');
  log+=weights[pair]*Math.log(mid);
  oldest=Math.min(oldest,t);newest=Math.max(newest,t);
 }
 if(newest-oldest>5000)return result('PAIR_CLOCK_SKEW');
 const value=Math.exp(log);
 return Number.isFinite(value)&&value>0?result('SYNTHETIC_PROXY_CALCULATED',value):
  result('INVALID_BASKET_RESULT');
}
module.exports={calculate};
