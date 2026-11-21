'use strict';
// Frozen V3 shadow veto: observes candidate conditions without voting on
// trades, changing V3, enabling paper orders or promoting synthetic inputs.
// This is an independent hypothesis for future prospective validation.
const {checkFrame}=require('./v3_multitimeframe');
const {diagnostic}=require('./ultimate_signal_quality');
const TF=Object.freeze({M15:15,H1:60,H4:240}),MIN_HISTORY=21,MAX_BREAKOUT_ATR=1.5;
const checks=['DXY','GC','orderFlow','calendar','headlines','US02Y','US10Y'];
const time=(s)=>typeof s==='string'&&/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,3})?Z$/.test(s)
 &&Number.isFinite(Date.parse(s))?Date.parse(s):NaN;
const safe=(x)=>typeof x==='number'&&Number.isFinite(x);
function nyOrLondon(ms,tz){
 const f=new Intl.DateTimeFormat('en-US',{timeZone:tz,weekday:'short',
 hour:'2-digit',minute:'2-digit',hourCycle:'h23'});
 const x=Object.fromEntries(f.formatToParts(ms).filter(y=>y.type!=='literal').map(y=>[y.type,y.value]));
 return {day:x.weekday,minute:Number(x.hour)*60+Number(x.minute)};
}
function sessions(asOfUTC){
 const t=time(asOfUTC);
 if(!safe(t))return {status:'UNAVAILABLE',reason:'INVALID_INDEPENDENT_UTC_CLOCK'};
 const l=nyOrLondon(t,'Europe/London'),n=nyOrLondon(t,'America/New_York');
 const weekdays=['Mon','Tue','Wed','Thu','Fri'];
 const london=weekdays.includes(l.day)&&l.minute>=8*60&&l.minute<16*60;
 const ny=weekdays.includes(n.day)&&n.minute>=8*60&&n.minute<17*60;
 return {status:'UTC_DST_RESEARCH_WINDOWS_ONLY',
  london,us:ny,overlap:london&&ny,referenceOnly:true,
  brokerHolidaysAndMaintenanceVerified:false,sessionAdmissibleForOrders:false};
}
function audit(snapshot,base,qualityReport){
 const veto=new Set(),observations=[];
 const add=c=>veto.add(c);
 const now=time(snapshot?.asOfUTC);
 if(!safe(now)||base?.engine!=='V3 Ultimate'||base?.version!==1||
    base?.signal!=='WAIT'||base?.executable!==false||
    !qualityReport||qualityReport.signal!=='WAIT'||
    qualityReport.executable!==false||qualityReport.effectOnCandidate!=='NONE')
  throw Error('UNSAFE_OR_UNFROZEN_V3_SHADOW_REVIEW');
 const shadowSide=base.researchCandidate;
 if(!['BUY','SELL'].includes(shadowSide))add('NO_ADMISSIBLE_FROZEN_V3_CANDIDATE');
 const perTimeframe={};
 for(const [tf,min] of Object.entries(TF)){
  const candles=snapshot?.frames?.[tf];
  const status=checkFrame(candles,min,now);
  if(!status.ok||candles.length<MIN_HISTORY){
   perTimeframe[tf]={status:'BLOCKED',reason:status.reason||'MIN_HISTORY_NOT_MET'};
   add(tf+'_CLOSED_FRAME_INVALID');continue;
  }
  const tail=candles.slice(-MIN_HISTORY),interval=min*60000;
  const hasGap=tail.some((bar,i)=>i>0&&Date.parse(bar.datetime??bar.timestamp)!==
   Date.parse(tail[i-1].datetime??tail[i-1].timestamp)+interval);
  if(hasGap)add(tf+'_SESSION_GAP_UNVERIFIED');
  const old=tail[0].close,last=tail.at(-1).close;
  const direction=last>old?'UP':last<old?'DOWN':'FLAT';
  perTimeframe[tf]={status:hasGap?'UNVERIFIED_SESSION_GAP':'CLOSED_RESEARCH_ONLY',
    direction,lastClosedUTC:new Date(Date.parse(tail.at(-1).datetime??tail.at(-1).timestamp)+interval).toISOString()};
  if(shadowSide==='BUY'&&direction!=='UP'||shadowSide==='SELL'&&direction!=='DOWN')
   add(tf+'_DIRECTION_NOT_CONFIRMED');
 }
 const quality=qualityReport;
 if(quality.status!=='RESEARCH_DIAGNOSTIC_ONLY'||quality.empiricalWinProbability!==null){
  add('QUALITY_DIAGNOSTIC_UNAVAILABLE_OR_PROMOTED');
 }else{
  const warnings=new Set(quality.warnings||[]);
  for(const key of ['M15_GAP_REQUIRES_BROKER_SESSION_CALENDAR',
   'H1_GAP_REQUIRES_BROKER_SESSION_CALENDAR',
   'H4_GAP_REQUIRES_BROKER_SESSION_CALENDAR',
   'CHOPPY_PRICE_PATH','SINGLE_CANDLE_VOLATILITY_SHOCK',
   'COST_ADJUSTED_REWARD_RISK_LOW',
   'H1_M15_CLOSED_OHLC_PARITY_MISMATCH',
   'H4_M15_CLOSED_OHLC_PARITY_MISMATCH',
   'H1_M15_PARITY_NOT_FULLY_COVERED',
   'H4_M15_PARITY_NOT_FULLY_COVERED',
   'BROKER_COST_OR_TRADE_GEOMETRY_NOT_VERIFIED',
   'HIGH_IMPACT_EVENT_WINDOW','HIGH_IMPACT_NEWS_WINDOW',
   'CALENDAR_COVERAGE_UNVERIFIED','NEWS_COVERAGE_UNVERIFIED'])
   if(warnings.has(key))add(key);
  if(!safe(quality.metrics?.netRewardRiskEstimate))add('AFTER_COST_REWARD_RISK_UNAVAILABLE');
 }
 // Independent breakout extension check: only a confirmed pivot that existed
 // prior to the latest CLOSED M15 may be used. No future-right-side pivot.
 const m15=snapshot.frames?.M15||[],last=m15.at(-1),idx=m15.length-1;
 const st=base.technical?.observations?.M15;
 const pivot=shadowSide==='BUY'?st?.high:shadowSide==='SELL'?st?.low:null;
 const bos=shadowSide==='BUY'?st?.bosUp:shadowSide==='SELL'?st?.bosDown:false;
 let extensionAtr=null;
 if(!pivot||!Number.isInteger(pivot.confirmedAt)||pivot.confirmedAt>=idx||
    !safe(pivot.price)||!bos||!last||!safe(last.close)||
    !safe(quality?.metrics?.atr14PriorClosed)||quality.metrics.atr14PriorClosed<=0){
  add('M15_CONFIRMED_LIQUIDITY_BREAK_NOT_VERIFIED');
 }else{
  const ext=shadowSide==='BUY'?last.close-pivot.price:pivot.price-last.close;
  extensionAtr=ext/quality.metrics.atr14PriorClosed;
  if(!safe(extensionAtr)||extensionAtr<=0)add('M15_BREAKOUT_PRICE_NOT_CONFIRMED');
  else if(extensionAtr>MAX_BREAKOUT_ATR)add('M15_BREAKOUT_TOO_EXTENDED_VS_PRIOR_ATR');
 }
 // V3 sees some daily yields as instantly fresh in synthetic fixtures; it
 // cannot prove licensed intraday 2Y / 10Y. Never silently promote them.
 const layerStatus={};
 for(const name of checks){
  const l=base.layers?.[name],f=snapshot.feeds?.[name];
  const ready=l?.status==='READY'&&!l?.blocked;
  layerStatus[name]={coreStatus:l?.status||'MISSING',inputMode:f?.mode||'MISSING',
    realMarketRightsIndependentlyVerified:false,
    intradayEvidenceValidated:false};
  if(!ready)add(name+'_EVIDENCE_UNAVAILABLE_OR_HIGH_IMPACT');
  // A crypto-perpetual trade stream must never masquerade as spot XAUUSD,
  // exchange GC, an index, or broker yields through a generic feed name.
  if((typeof f?.source==='string'&&/BINANCE|XAUUSDT/i.test(f.source))||
     (typeof f?.instrument==='string'&&/XAUUSDT/i.test(f.instrument))||
     (typeof f?.symbol==='string'&&/XAUUSDT/i.test(f.symbol)))
   add(name+'_BINANCE_XAUUSDT_SUBSTITUTION_FORBIDDEN');
  if(f?.mode!=='recorded')add(name+'_RECORDED_PROVENANCE_UNVERIFIED');
  if(!Number.isFinite(time(f?.availableUTC))||time(f.availableUTC)>now)
   add(name+'_FIRST_AVAILABLE_AT_DECISION_UNVERIFIED');
 }
 const candidate=shadowSide==='BUY'?1:shadowSide==='SELL'?-1:0;
 const multi=['DXY','GC','orderFlow'];
 const observationsMs=[];
 for(const key of multi){
  const f=snapshot.feeds?.[key],l=base.layers?.[key];
  if(!safe(l?.score)||!candidate||l.score*candidate<=0)add(key+'_CONTRADICTS_OR_CANNOT_CONFIRM');
  const t=time(f?.observedUTC);
  if(!safe(t)||t>now||now-t>300000)add(key+'_OBSERVATION_STALE_OR_FUTURE');
  else observationsMs.push(t);
 }
 if(observationsMs.length===multi.length&&Math.max(...observationsMs)-Math.min(...observationsMs)>60000)
  add('GC_DXY_FLOW_OBSERVATIONS_NOT_SYNCHRONIZED');
 if(!snapshot.feeds?.GC?.contract||!snapshot.feeds?.orderFlow?.contract||
    snapshot.feeds.GC.contract!==snapshot.feeds.orderFlow.contract)
  add('GC_TAPE_VS_FUTURES_CONTRACT_NOT_MATCHED');
 if(base.layers?.calendar?.blocked||base.layers?.headlines?.blocked)
  add('HIGH_IMPACT_NEWS_BLACKOUT');
 add('INDEPENDENT_LICENSE_AND_SOURCE_AVAILABILITY_ATTESTATION_REQUIRED');
 // Binance XAUUSDT is quarantined unconditionally, even if caller forges
 // price, volume, timing, license or an extreme bullish/bearish delta.
 const out={
  mode:'OFFLINE_FROZEN_V3_SHADOW_VETO_V1',
  frozenCandidate:shadowSide,signal:'WAIT',executable:false,
  paperOrdersAllowed:false,researchEligible:false,liveAdmissible:false,
  hypotheticalFilterPass:veto.size===0, // always false absent independent attestation
  blockers:[...veto].sort(),
  multiTimeframe:perTimeframe,liquidityBreakoutExtensionATR:
   safe(extensionAtr)?Math.round(extensionAtr*10000)/10000:null,
  session:sessions(snapshot.asOfUTC),
  evidence:layerStatus,
  binanceXauusdt:{status:'INDEPENDENT_AUXILIARY_QUARANTINED',
   substitutableForXauusd:false,substitutableForComex:false,
   participatesInV3:false,participatesInShadowVeto:false},
  sourceRequestsMade:0,providerRequestsMade:0,
  predictedWinRate:null,forwardPerformanceEstablished:false,
  rules:'FIXED_OFFLINE_ADVISORY_V1',
  warning:'Never trades. Even an apparently aligned synthetic candidate does not establish real licensed evidence or a successful filter.'};
 return out;
}
module.exports={audit,sessions};
