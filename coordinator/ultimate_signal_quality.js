'use strict';
// Offline, as-of-only signal-quality diagnostics for Gold Precision Pro Ultimate.
// This is NOT a predictive AI model or an empirically validated win probability.
// Does not contact providers, place trades, authorize paper orders, or change a signal.
const {checkFrame}=require('./v3_multitimeframe');

const PERIODS=Object.freeze({M15:15,H1:60,H4:240});
const THRESHOLDS=Object.freeze({
  efficiencyLookback:20,atrPeriod:14,atrShockRatio:2.5,
  choppyEfficiency:0.25,trendingEfficiency:0.60,minimumNetRewardRisk:1.5
});
const finite=Number.isFinite;
function round(n){return finite(n)?Math.round(n*1e6)/1e6:null;}
// Offline-only BID/MID-frame geometry check; never invent missing candles.
// A fully covered H1/H4 candle must match exact M15 constituents before a
// technical regime is used even as descriptive context. This does NOT prove
// independent vendor identity or broker-session completeness.
function auditCrossFrameM15(frames){
  const lower=new Map(frames.M15.map(r=>[Date.parse(r.datetime),r]));
  const findings={};
  for(const [tf,segments] of [['H1',4],['H4',16]]){
    let matched=0,disagreed=0,uncovered=0;
    for(const whole of frames[tf]){
      const start=Date.parse(whole.datetime);
      const parts=Array.from({length:segments},(_,i)=>lower.get(start+i*900000));
      if(parts.some(x=>!x)){uncovered++;continue;}
      const expected={open:parts[0].open,high:Math.max(...parts.map(x=>x.high)),
        low:Math.min(...parts.map(x=>x.low)),close:parts.at(-1).close};
      const same=['open','high','low','close'].every(k=>
        Math.abs(whole[k]-expected[k])<=Math.max(0.00001,Math.abs(expected[k])*1e-8));
      if(same)matched++;else disagreed++;
    }
    findings[tf]={matched,disagreed,uncovered,
      fullHistoryCrossFrameVerified:false};
  }
  return findings;
}
function diagnostic(frames,asOfUTC,tradePlan={},risk={},layers={}){
  const result={
    mode:'OFFLINE_PROSPECTIVE_QUALITY_DIAGNOSTIC',
    effectOnCandidate:'NONE',signal:'WAIT',executable:false,
    paperOrdersAllowed:false,providerRequestsMade:0,
    status:'INSUFFICIENT_EVIDENCE',regime:'UNAVAILABLE',
    empiricalWinProbability:null,qualityScore:null,
    thresholds:'FIXED_EXPLORATORY_NOT_OPTIMIZED',
    warnings:[],checks:{},metrics:{},
    };
  const now=Date.parse(asOfUTC);
  if(typeof asOfUTC!=='string'||!/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z$/.test(asOfUTC)
    ||!finite(now)||new Date(now).toISOString().slice(0,19)!==asOfUTC.slice(0,19)){
    result.warnings.push('EXPLICIT_UTC_DECISION_TIME_REQUIRED');
    return result;
  }
  for(const [frame,minutes] of Object.entries(PERIODS)){
    const test=checkFrame(frames?.[frame],minutes,now);
    result.checks[frame]={closedAndFresh:test.ok,reason:test.ok?null:test.reason};
    if(!test.ok)result.warnings.push(frame+'_CLOSED_DATA_UNAVAILABLE');
  }
  if(result.warnings.length)return result;
  // A missing aligned bar could be a legitimate weekend/session closure.
  // Without an independently verified calendar, flag gaps for human review
  // instead of pretending continuity or inventing synthetic missing candles.
  for(const [frame,minutes] of Object.entries(PERIODS)){
    const rowsForFrame=frames[frame],width=minutes*60_000;
    for(let i=1;i<rowsForFrame.length;i++){
      if(Date.parse(rowsForFrame[i].datetime)-Date.parse(rowsForFrame[i-1].datetime)>width){
        result.warnings.push(frame+'_GAP_REQUIRES_BROKER_SESSION_CALENDAR');
        break;
      }
    }
  }
  const cross=auditCrossFrameM15(frames);
  result.metrics.crossFrameM15=cross;
  for(const tf of ['H1','H4']){
    if(cross[tf].disagreed>0)
      result.warnings.push(tf+'_M15_CLOSED_OHLC_PARITY_MISMATCH');
    if(cross[tf].uncovered>0)
      result.warnings.push(tf+'_M15_PARITY_NOT_FULLY_COVERED');
  }
  const rows=frames.M15;
  if(rows.length<Math.max(THRESHOLDS.efficiencyLookback+1,2*THRESHOLDS.atrPeriod+1)){
    result.warnings.push('M15_HISTORY_INSUFFICIENT_FOR_QUALITY_AUDIT');
    return result;
  }
  // Uses only CLOSED historical M15 bars available at asOfUTC; prev close is closed.
  const tr=rows.map((r,i)=>{
    const prev=i?rows[i-1].close:r.close;
    return Math.max(r.high-r.low,Math.abs(r.high-prev),Math.abs(r.low-prev));
  });
  const prior=tr.slice(-THRESHOLDS.atrPeriod-1,-1);
  const atr=prior.reduce((a,b)=>a+b,0)/THRESHOLDS.atrPeriod;
  if(!finite(atr)||atr<=0){
    result.warnings.push('ATR_UNAVAILABLE_OR_ZERO');
    return result;
  }
  const closes=rows.slice(-THRESHOLDS.efficiencyLookback-1).map(r=>r.close);
  let path=0;
  for(let i=1;i<closes.length;i++)path+=Math.abs(closes[i]-closes[i-1]);
  const movement=Math.abs(closes.at(-1)-closes[0]);
  // Kaufman-style efficiency ratio: measures straightness of path, NOT profit.
  const efficiency=path>0?movement/path:0;
  const lastTrueRange=tr.at(-1);
  const shockRatio=lastTrueRange/atr;
  const regime=efficiency<=THRESHOLDS.choppyEfficiency?'CHOPPY':
    efficiency>=THRESHOLDS.trendingEfficiency?'DIRECTIONAL':'MIXED';
  result.regime=regime;
  result.metrics={efficiencyRatio:round(efficiency),atr14PriorClosed:round(atr),
    lastTrueRangeToPriorATR:round(shockRatio),directionOver20Bars:
      closes.at(-1)>closes[0]?'UP':closes.at(-1)<closes[0]?'DOWN':'FLAT'};
  if(regime==='CHOPPY')result.warnings.push('CHOPPY_PRICE_PATH');
  if(shockRatio>=THRESHOLDS.atrShockRatio)result.warnings.push('SINGLE_CANDLE_VOLATILITY_SHOCK');
  // Conservative, auditable net R:R estimate in price units.
  const entry=tradePlan?.entry,stop=tradePlan?.stop,target=tradePlan?.target;
  const spread=tradePlan?.spread,slippage=risk?.slippage,
        valuePerPoint=risk?.valuePerPoint,commissionPerLot=risk?.commissionPerLot;
  if([entry,stop,target,spread,slippage,valuePerPoint,commissionPerLot].every(finite)
    &&entry>0&&stop>0&&target>0&&spread>=0&&slippage>=0
    &&valuePerPoint>0&&commissionPerLot>=0
    &&((entry>stop&&target>entry)||(entry<stop&&target<entry))){
    // Round-trip conservative estimate; actual broker fills can differ.
    const priceCost=spread+slippage+commissionPerLot/valuePerPoint;
    const netReward=Math.abs(target-entry)-priceCost;
    const netRisk=Math.abs(entry-stop)+priceCost;
    const adjustedRR=netReward/netRisk;
    result.metrics.netRewardRiskEstimate=round(adjustedRR);
    result.metrics.roundTripCostPriceEstimate=round(priceCost);
    if(adjustedRR<THRESHOLDS.minimumNetRewardRisk)
      result.warnings.push('COST_ADJUSTED_REWARD_RISK_LOW');
  }else{
    result.metrics.netRewardRiskEstimate=null;
    result.warnings.push('BROKER_COST_OR_TRADE_GEOMETRY_NOT_VERIFIED');
  }
  if(layers?.calendar?.status!=='READY')
    result.warnings.push('CALENDAR_COVERAGE_UNVERIFIED');
  else if(layers.calendar.blocked)
    result.warnings.push('HIGH_IMPACT_EVENT_WINDOW');
  if(layers?.headlines?.status!=='READY')
    result.warnings.push('NEWS_COVERAGE_UNVERIFIED');
  else if(layers.headlines.blocked)
    result.warnings.push('HIGH_IMPACT_NEWS_WINDOW');
  result.status='RESEARCH_DIAGNOSTIC_ONLY';
  return result;
}
module.exports={diagnostic,THRESHOLDS};
