'use strict';
// Supplemental offline evidence diagnostics. Not a model, not a signal source,
// not an account feed, and not proof of actual source rights or predictive accuracy.
const {time}=require('./ultimate_v2_contracts');
const {checkFrame}=require('./v3_multitimeframe');
const {evaluate:spreadGuard}=require('./xauusd_spread_noise_guard');
const EPS=1e-9,MAX_EVENTS=64,MAX_OUTCOMES=5000;
const TF={M15:15,H1:60,H4:240};
const safe=(n)=>typeof n==='number'&&Number.isFinite(n);
const rounded=(n)=>Math.round(n*1e5)/1e5;
const blocked=(reason)=>({status:'BLOCKED',reason,signal:'WAIT',executable:false,directionalVote:false});
function regime(frames,asOfUTC){
 const now=time(asOfUTC),states={};
 if(!Number.isFinite(now))return blocked('INVALID_DECISION_CLOCK');
 for(const [tf,minutes] of Object.entries(TF)){
  const candles=frames?.[tf],valid=checkFrame(candles,minutes,now);
  if(!valid.ok||candles.length<21)return {...blocked(tf+'_INSUFFICIENT_CLOSED_FRAMES'),timeframe:tf};
  const rows=candles.slice(-21),width=minutes*60000;
  if(rows.some((r,i)=>i>0&&time(r.datetime??r.timestamp)!==time(rows[i-1].datetime??rows[i-1].timestamp)+width))
   return {...blocked(tf+'_NONCONSECUTIVE_OBSERVATIONS'),timeframe:tf};
  const closes=rows.map(r=>r.close),moves=closes.slice(1).map((v,i)=>Math.abs(v-closes[i]));
  const gross=moves.reduce((a,b)=>a+b,0);
  const net=closes.at(-1)-closes[0];
  const efficiency=gross>EPS?Math.abs(net)/gross:0;
  const tr=rows.slice(1).map((r,i)=>Math.max(r.high-r.low,
   Math.abs(r.high-closes[i]),Math.abs(r.low-closes[i])));
  const atr=tr.reduce((a,b)=>a+b,0)/tr.length;
  const ordered=[...tr.slice(0,-1)].sort((a,b)=>a-b),median=ordered[Math.floor(ordered.length/2)];
  const shock=median>EPS&&tr.at(-1)>2.5*median;
  states[tf]={efficiency:rounded(efficiency),direction:net>EPS?'UP':net<-EPS?'DOWN':'FLAT',
   normalizedNetAtr:atr>EPS?rounded(net/atr):null,volatilityShock:shock,
   lastClosedUTC:new Date(time(rows.at(-1).datetime??rows.at(-1).timestamp)+width).toISOString()};
 }
 const dirs=Object.values(states).map(v=>v.direction);
 const efficient=Object.values(states).every(v=>v.efficiency>=.44);
 const ranging=Object.values(states).every(v=>v.efficiency<=.22);
 const spike=Object.values(states).some(v=>v.volatilityShock);
 const type=spike?'VOLATILITY_SHOCK':dirs.every(v=>v===dirs[0]&&v!=='FLAT')&&efficient?
  'ALIGNED_TREND':ranging?'RANGE_LIKE':'MIXED_OR_TRANSITION';
 return {status:'DIAGNOSTIC_ONLY',marketRegime:type,frames:states,
  signal:'WAIT',executable:false,directionalVote:false,
  researchEligible:false,confidence:'UNCALIBRATED_HEURISTIC',
  note:'Closed-bar efficiency heuristic: not a market-data provenance check or validated prediction'};
}
function surprises(envelope,asOfUTC){
 const now=time(asOfUTC);
 if(!Number.isFinite(now))return blocked('INVALID_DECISION_CLOCK');
 if(envelope===undefined)return {...blocked('CONSENSUS_ACTUAL_SOURCE_NOT_CONNECTED'),events:[]};
 if(!envelope||envelope.sourceDataMode!=='SYNTHETIC_TEST_ONLY'||
    !Array.isArray(envelope.events)||envelope.events.length>MAX_EVENTS)
  return {...blocked('UNVERIFIED_RELEASE_OR_CONSENSUS_SOURCE'),events:[]};
 const seen=new Set(),items=[];
 for(const event of envelope.events){
  if(!event||typeof event.id!=='string'||event.id.length<1||seen.has(event.id)||
     !['CPI','PPI','NFP','PCE','FOMC','GDP','ISM'].includes(event.kind)||
     typeof event.units!=='string'||!/^[A-Z_%][A-Z0-9_%]{0,19}$/.test(event.units)||
     ![event.actual,event.consensus,event.previous].every(safe)||
     ![event.scheduledUTC,event.releasedUTC,event.availableUTC].every(x=>Number.isFinite(time(x)))||
     time(event.releasedUTC)<time(event.scheduledUTC)||
     time(event.availableUTC)<time(event.releasedUTC)||
     time(event.availableUTC)>now)
   return {...blocked('RELEASE_AVAILABILITY_OR_VALUE_INVALID'),events:[]};
  seen.add(event.id);
  const delta=event.actual-event.consensus;
  if(!Number.isFinite(delta))return {...blocked('RELEASE_SURPRISE_ARITHMETIC_OVERFLOW'),events:[]};
  const relative= Math.abs(event.consensus)<1e-9?null:rounded(delta/Math.abs(event.consensus));
  items.push({id:event.id,kind:event.kind,units:event.units,
   scheduledUTC:event.scheduledUTC,availableUTC:event.availableUTC,
   actual: event.actual,consensus:event.consensus,previous:event.previous,
   surprise:rounded(delta),surpriseRelativeToConsensus:relative,
   result:delta>1e-9?'ABOVE_CONSENSUS':delta< -1e-9?'BELOW_CONSENSUS':'MATCHED_CONSENSUS',
   goldReaction:'NOT_OBSERVED',directionalVote:false});
 }
 return {status:'SYNTHETIC_RELEASE_ARITHMETIC_ONLY',events:items,
  eventCount:items.length,signal:'WAIT',executable:false,directionalVote:false,
  researchEligible:false,verifiedConsensusFeed:false,
  goldReactionValidated:false,note:'Economic surprises have no universal gold direction; independent price response and source timestamp are missing'};
}
function crossAssets(result,asOfUTC){
 const now=time(asOfUTC);
 if(!Number.isFinite(now)||!result||result.signal!=='WAIT'||result.executable!==false)
  return blocked('INDEPENDENT_BASE_DECISION_REQUIRED');
 const keys=['DXY','GC','orderFlow'],rows=keys.map(k=>[k,result.layers?.[k]]);
 if(rows.some(([,v])=>v?.status!=='READY'||!Number.isFinite(time(v.observedUTC))||
      !safe(v.score)||time(v.observedUTC)>now))
  return {...blocked('INTRADAY_SOURCE_EVIDENCE_INCOMPLETE'),evidence:[]};
 const times=rows.map(([,v])=>time(v.observedUTC));
 if(Math.max(...times)-Math.min(...times)>60000)
  return {...blocked('MARKET_OBSERVATION_SKEW_OVER_60_SECONDS'),evidence:[]};
 if(result.layers.GC.contract!==result.layers.orderFlow.contract)
  return {...blocked('GC_CONTRACT_MISMATCH'),evidence:[]};
 const candidate=result.technical?.candidate,sign=candidate==='BUY'?1:candidate==='SELL'?-1:0;
 const opposing=rows.filter(([,v])=>sign!==0&&v.score*sign<=0).map(([k])=>k);
 const zeroVotes=rows.filter(([,v])=>v.score===0).map(([k])=>k);
 const evidence=rows.map(([source,v])=>({source,
  goldBias:v.score>0?'UP':v.score<0?'DOWN':'NEUTRAL',
  observedUTC:v.observedUTC}));
 const status=sign===0?'NO_TECHNICAL_CANDIDATE':
   opposing.length?'DIVERGENCE_DETECTED':'SYNTHETIC_ALIGNMENT_ONLY';
 return {status,evidence,opposing,zeroVotes,marketSkewSeconds:(Math.max(...times)-Math.min(...times))/1000,
  conservativeReviewCandidate:opposing.length?'NONE':sign===0?'NONE':candidate,
  signal:'WAIT',executable:false,directionalVote:false,independentMarketEvidenceVerified:false,
  note:'Same-timestamp synthetic contracts are not proof of licensed live alignment or higher forecast quality'};
}
function realYield(tips,nominal,layer,asOfUTC){
 const now=time(asOfUTC);
 if(!Number.isFinite(now))return blocked('INVALID_DECISION_CLOCK');
 if(tips===undefined)return blocked('DFII10_TIPS_DAILY_REFERENCE_NOT_CONNECTED');
 if(!tips||tips.sourceDataMode!=='SYNTHETIC_TEST_ONLY'||
    tips.series!=='DFII10'||tips.frequency!=='DAILY'||
    typeof tips.observationDate!=='string'||!(/^\d{4}-\d{2}-\d{2}$/.test(tips.observationDate))||
    !safe(tips.percent)||tips.percent < -20||tips.percent>30||
    !Number.isFinite(time(tips.observedUTC))||!Number.isFinite(time(tips.availableUTC))||
    time(tips.observedUTC)>time(tips.availableUTC)||
    time(tips.availableUTC)>now||now-time(tips.availableUTC)>7*86400000||
    tips.observationDate!==tips.observedUTC.slice(0,10))
  return blocked('TIPS_DAILY_VINTAGE_INVALID_OR_NOT_AVAILABLE');
 if(layer?.status!=='READY'||!nominal||nominal.instrument!=='DGS10'||
    nominal.observationDate!==tips.observationDate||
    !safe(nominal.value)||!Number.isFinite(time(nominal.availableUTC))||
    time(nominal.availableUTC)>now)
  return blocked('NOMINAL_10Y_MATCHED_DAILY_VINTAGE_UNAVAILABLE');
 return {status:'SYNTHETIC_DAILY_REAL_YIELD_ARITHMETIC_ONLY',
  series:'DFII10',observationDate:tips.observationDate,realYieldPercent:tips.percent,
  nominalYieldPercent:nominal.value,
  nominalMinusRealPercent:rounded(nominal.value-tips.percent),
  signal:'WAIT',executable:false,directionalVote:false,
  verifiedRealYieldFeed:false,intradayEvidence:false,
  note:'DFII10 is a daily TIPS real-yield proxy; nominal minus real is a rough breakeven measure, not a gold signal'};
}
function quality(sample,asOfUTC){
 const now=time(asOfUTC);
 if(!Number.isFinite(now))return blocked('INVALID_DECISION_CLOCK');
 if(sample===undefined)return blocked('INDEPENDENT_OUT_OF_SAMPLE_TRADES_NOT_CONNECTED');
 if(!sample||sample.sourceDataMode!=='SYNTHETIC_TEST_ONLY'||
    !Array.isArray(sample.trades)||sample.trades.length>MAX_OUTCOMES||
    !Number.isFinite(time(sample.frozenUTC))||time(sample.frozenUTC)>now)
  return blocked('FROZEN_HOLDOUT_OR_SOURCE_MISSING');
 let wins=0,losses=0,grossWins=0,grossLoss=0,net=0,peak=0,dd=0;
 const ids=new Set();let prev=-Infinity;
 for(const trade of sample.trades){
  if(!trade||typeof trade.id!=='string'||!trade.id||ids.has(trade.id)||
     !safe(trade.netR)||Math.abs(trade.netR)>100||
     !Number.isFinite(time(trade.openedUTC))||!Number.isFinite(time(trade.closedUTC))||
     time(trade.openedUTC)<time(sample.frozenUTC)||
     time(trade.openedUTC)>=time(trade.closedUTC)||
     time(trade.closedUTC)>now||time(trade.closedUTC)<prev)
   return blocked('OUTCOMES_LOOKAHEAD_OR_NONCHRONOLOGICAL');
  ids.add(trade.id);prev=time(trade.closedUTC);
  net+=trade.netR;peak=Math.max(peak,net);dd=Math.max(dd,peak-net);
  if(trade.netR>0){wins++;grossWins+=trade.netR;}
  else if(trade.netR<0){losses++;grossLoss+=-trade.netR;}
 }
 const n=sample.trades.length;
 return {status:'SYNTHETIC_HOLDOUT_ARITHMETIC_ONLY',closedCount:n,
  netR:rounded(net),maxDrawdownR:rounded(dd),
  winRatePercent:n?rounded(100*wins/n):null,
  profitFactor:grossLoss>0?rounded(grossWins/grossLoss):null,
  wins,losses,readyForStatisticalClaims:false,
  minimum100ClosedSamplesMetByGeometry:n>=100,
  independentForwardHoldoutVerified:false,brokerCostsVerified:false,
  signal:'WAIT',executable:false,directionalVote:false,
  note:'Synthetic R outcomes demonstrate math only; not live accuracy, selection independence or expected profits'};
}
function inspect(input,core){
 if(!input||!core||core.version!==2||core.contractVersion!=='ultimate-context-events-v2'||
   core.signal!=='WAIT'||core.executable!==false||core.networkEnabled!==false)
  throw Error('UNSAFE_ULTIMATE_RESEARCH_REVIEW');
 const asOfUTC=input.asOfUTC,r=input.researchReview||{};
 return {
  mode:'OFFLINE_ULTIMATE_RESEARCH_EXTENSIONS',
  signal:'WAIT',executable:false,researchEligible:false,paperOrdersAllowed:false,
  automatedOrdersAllowed:false,predictedWinRate:null,
  realDataSourcesActivated:0,providerRequestsMade:0,
  sourceProvenanceVerified:false,
  regime:regime(input.frames,asOfUTC),
  economicSurprises:surprises(r.releases,asOfUTC),
  crossMarket:crossAssets(core,asOfUTC),
  tips10Y:realYield(r.tips10Y,input.feeds?.US10Y,core.layers?.US10Y,asOfUTC),
  performance:quality(r.holdout,asOfUTC),
  spreadNoise:spreadGuard(r.bboClosed,asOfUTC,core.technical?.candidate||'NONE'),
  note:'Supplemental research only; missing sources never become synthetic positive signals'
 };
}
module.exports={regime,surprises,crossAssets,realYield,quality,inspect};
