'use strict';
// Independent closed BBO basis-quality review for XAU/USD. Does not fetch
// prices, infer licensed source provenance, or authorize any signal/order.
// Historical BID/ASK extrema are NOT contemporaneous spread observations;
// use synchronized opening/closing quote samples only.
const WIDTH=15*60000,LOOKBACK=20,LIMIT=3000;
const numeric=x=>typeof x==='number'&&Number.isFinite(x)&&x>0;
const stamp=x=>{
 if(typeof x!=='string'||! /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,3})?Z$/.test(x))return NaN;
 const t=Date.parse(x);
 return Number.isFinite(t)&&new Date(t).toISOString().slice(0,19)===x.slice(0,19)?t:NaN;
};
const block=reasonCode=>({mode:'OFFLINE_CLOSED_BBO_SPREAD_NOISE_GUARD',
 status:'BLOCKED',reasonCode,signal:'WAIT',executable:false,
 directionalVote:false,realPriceVerified:false,providerRequestsMade:0,
 paperOrdersAllowed:false,predictedWinRate:null});
const round=n=>Math.round(n*1e6)/1e6;
function evaluate(envelope,asOfUTC,technicalCandidate='NONE'){
 const now=stamp(asOfUTC);
 if(!Number.isFinite(now))return block('INDEPENDENT_ASOF_UTC_INVALID');
 if(envelope===undefined||envelope===null)return block('CLOSED_BID_ASK_HISTORY_NOT_CONNECTED');
 if(!envelope||envelope.sourceDataMode!=='SYNTHETIC_TEST_ONLY'||
    envelope.instrument!=='XAU/USD'||Object.keys(envelope).some(k=>!
     ['sourceDataMode','instrument','bid','ask','mid'].includes(k)))
  return block('SYNTHETIC_XAUUSD_BBO_ONLY');
 if(!['BUY','SELL','NONE'].includes(technicalCandidate))
  return block('TECHNICAL_CANDIDATE_INVALID');
 const names=['bid','ask','mid'];
 if(names.some(k=>!Array.isArray(envelope[k])||envelope[k].length<LOOKBACK+1||
    envelope[k].length>LIMIT)||names.some(k=>envelope[k].length!==envelope.bid.length))
  return block('M15_THREE_BASIS_CLOSED_HISTORY_REQUIRED');
 const slices=Object.fromEntries(names.map(k=>[k,envelope[k].slice(-LOOKBACK-1)]));
 let last=-Infinity;
 for(let i=0;i<LOOKBACK+1;i++){
  const bars=names.map(k=>slices[k][i]),times=bars.map(x=>stamp(x?.openTime));
  if(times.some(t=>!Number.isFinite(t))||times.some(t=>t!==times[0])||
     times[0]%WIDTH!==0||times[0]+WIDTH>now||
     (i>0&&times[0]!==last+WIDTH))
   return block('MISALIGNED_GAPPED_UNCLOSED_OR_FUTURE_M15');
  last=times[0];
  for(const bar of bars){
   if(!bar||!['open','high','low','close'].every(k=>numeric(bar[k]))||
      bar.high<Math.max(bar.open,bar.close,bar.low)||
      bar.low>Math.min(bar.open,bar.close,bar.high))
    return block('INVALID_CLOSED_BBO_OHLC');
  }
  const [bid,ask,mid]=bars;
  const epsilon=1e-6*Math.max(1,ask.close);
  if(bid.open>ask.open||bid.close>ask.close||
     bid.high>ask.high+epsilon||bid.low>ask.low+epsilon||
     Math.abs(mid.open-(bid.open+ask.open)/2)>epsilon||
     Math.abs(mid.close-(bid.close+ask.close)/2)>epsilon||
     mid.high>(bid.high+ask.high)/2+epsilon||
     mid.low<(bid.low+ask.low)/2-epsilon)
   return block('CROSSED_OR_NONPARITY_BID_ASK_MID');
 }
 if(now-(last+WIDTH)>WIDTH)return block('LAST_CLOSED_BBO_BAR_STALE');
 const b=slices.bid,a=slices.ask,m=slices.mid;
 const previous=Array.from({length:LOOKBACK},(_,i)=>a[i].close-b[i].close);
 const recent=a.at(-1).close-b.at(-1).close;
 const baseline=[...previous].sort((x,y)=>x-y);
 const median=(baseline[9]+baseline[10])/2;
 if(!Number.isFinite(median)||median<=0)return block('POSITIVE_HISTORICAL_SPREAD_BASELINE_REQUIRED');
 const ratio=recent/median;
 const tr=Array.from({length:LOOKBACK},(_,i)=>Math.max(
  m[i+1].high-m[i+1].low,
  Math.abs(m[i+1].high-m[i].close),
  Math.abs(m[i+1].low-m[i].close)));
 const avgRange=tr.reduce((p,v)=>p+v,0)/LOOKBACK;
 const upper=Math.max(...m.slice(0,-1).map(x=>x.high));
 const lower=Math.min(...m.slice(0,-1).map(x=>x.low));
 const side=technicalCandidate;
 const midBreaks=side==='BUY'?m.at(-1).close>upper:
                 side==='SELL'?m.at(-1).close<lower:false;
 const bidConfirms=side==='BUY'?b.at(-1).close>Math.max(...b.slice(0,-1).map(x=>x.high)):
                   side==='SELL'?b.at(-1).close<Math.min(...b.slice(0,-1).map(x=>x.low)):false;
 const askConfirms=side==='BUY'?a.at(-1).close>Math.max(...a.slice(0,-1).map(x=>x.high)):
                   side==='SELL'?a.at(-1).close<Math.min(...a.slice(0,-1).map(x=>x.low)):false;
 const spreadShock=ratio>3;
 const midOnly=midBreaks&&(!bidConfirms||!askConfirms);
 const warnings=[
  ...(spreadShock?['SYNCHRONIZED_CLOSE_SPREAD_OVER_3X_PRIOR_MEDIAN']:[]),
  ...(midOnly?['MID_CLOSE_BREAKOUT_NOT_CONFIRMED_BY_BOTH_BID_AND_ASK']:[])
 ];
 const status=spreadShock?'SPREAD_WIDENING_RISK':midOnly?
  'MID_ONLY_BREAKOUT_UNCONFIRMED':midBreaks?'SYNTHETIC_DUAL_BASIS_BREAKOUT_ONLY':
  'NO_20_BAR_CLOSE_BREAKOUT';
 return {mode:'OFFLINE_CLOSED_BBO_SPREAD_NOISE_GUARD',
  status,signal:'WAIT',executable:false,directionalVote:false,
  researchEligible:false,paperOrdersAllowed:false,realPriceVerified:false,
  historicalLiveBboParityVerified:false,independentBrokerSessionVerified:false,
  predictedWinRate:null,providerRequestsMade:0,ordersSent:0,
  sourceDataMode:'SYNTHETIC_TEST_ONLY',
  asOfUTC,lastClosedUTC:new Date(last+WIDTH).toISOString(),
  technicalCandidate:side,closedBarsExamined:LOOKBACK+1,
  medianHistoricalCloseSpread:round(median),lastCloseSpread:round(recent),
  spreadVsHistoricalMedian:round(ratio),
  averageMidTrueRange:round(avgRange),
  spreadAsFractionOfAverageTrueRange:avgRange>0?round(recent/avgRange):null,
  mid20BarCloseBreakout:midBreaks,bidHighLowCloseConfirmed:bidConfirms,
  askHighLowCloseConfirmed:askConfirms,warnings,
  note:'BBO closes are synchronized; max/min highs and lows are NOT same-timestamp quote spreads. This is an exploratory synthetic-only heuristic, not a licensed market signal or proof of false-breakout reduction.'};
}
module.exports={evaluate};
