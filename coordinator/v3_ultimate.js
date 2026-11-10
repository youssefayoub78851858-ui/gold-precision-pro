'use strict';
// Deterministic offline research. Input evidence is supplied, never fetched.
const {assess}=require('./v3_multitimeframe');
const {plan}=require('./v3_trade_plan');
const FEEDS=['DXY','US02Y','US10Y','GC','calendar','headlines','orderFlow'];
const finite=Number.isFinite;
function evidence(name,feed,now){
 const bad=reason=>({status:'UNAVAILABLE',reason});
 if(!feed||!['synthetic','recorded'].includes(feed.mode)||typeof feed.source!=='string'||!feed.source.trim())return bad('Provenance missing');
 const time=Date.parse(feed.observedUTC);
 if(!finite(time)||time>now||now-time>300000)return bad('Stale or future evidence');
 if(feed.mode==='recorded'){
  const available=Date.parse(feed.availableUTC);
  const instruments={DXY:'DXY',US02Y:'DGS2',US10Y:'DGS10',GC:'GC',calendar:'USD_EVENTS',headlines:'GOLD_USD_NEWS',orderFlow:'GC_TRADES'};
  if(!finite(available)||available<time||available>now)return bad('Evidence not available at decision time');
  if(feed.instrument!==instruments[name]||(!['US02Y','US10Y'].includes(name)&&feed.entitlementVerified!==true))return bad('Recorded instrument or entitlement unverified');
 }
 if(['calendar','headlines'].includes(name)){
  if(!Array.isArray(feed.events))return bad('Event coverage unavailable');
  if(feed.mode==='recorded'&&feed.events.some(e=>!finite(Date.parse(e.publishedUTC))||Date.parse(e.publishedUTC)>Date.parse(feed.availableUTC)||(name==='headlines'&&Date.parse(e.timeUTC)>now)))return bad('Unknown or future news publication');
  const start=Date.parse(feed.coverageStartUTC),end=Date.parse(feed.coverageEndUTC);
  if(!(start<=now-1800000&&end>=now+1800000))return bad('Event window not covered');
  if(feed.events.some(e=>!finite(Date.parse(e.timeUTC))||!['low','medium','high'].includes(e.impact)))return bad('Invalid event');
  return {status:'READY',mode:feed.mode,source:feed.source,blocked:feed.events.some(e=>e.impact==='high'&&Math.abs(Date.parse(e.timeUTC)-now)<=1800000)};
 }
 if(name==='orderFlow'){
  if(feed.kind!=='trades'||feed.licensed!==true||!finite(feed.buyVolume)||!finite(feed.sellVolume)||feed.buyVolume<0||feed.sellVolume<0||feed.buyVolume+feed.sellVolume<=0)return bad('Requires licensed trade-side evidence; OHLC volume is insufficient');
  return {status:'READY',mode:feed.mode,source:feed.source,score:(feed.buyVolume-feed.sellVolume)/(feed.buyVolume+feed.sellVolume)};
 }
 if(!finite(feed.previous)||feed.previous<=0||!finite(feed.value)||feed.value<=0)return bad('Invalid reference values');
 return {status:'READY',mode:feed.mode,source:feed.source,score:Math.sign(feed.value-feed.previous)*(name==='GC'?1:-1)};
}
function riskSize(p,r={}){
 const fail=reason=>({ok:false,reason});
 if(r.killSwitch!==false||r.activeTrades!==0)return fail('Kill switch or active trade');
 for(const k of ['equity','dailyLoss','riskFraction','dailyLossFraction','valuePerPoint','lotStep','minLot','maxLot','commissionPerLot','slippage'])if(!finite(r[k]))return fail('Risk inputs unavailable');
 if(r.equity<=0||r.dailyLoss<0||r.riskFraction<=0||r.riskFraction>0.005||r.dailyLossFraction<=0||r.dailyLossFraction>0.02||r.dailyLoss>=r.equity*r.dailyLossFraction)return fail('Risk or daily loss ceiling');
 if(r.valuePerPoint<=0||r.lotStep<=0||r.minLot<=0||r.maxLot<r.minLot||r.commissionPerLot<0||r.slippage<0||!finite(p.stopDistance)||p.stopDistance<=0)return fail('Invalid execution geometry');
 const budget=Math.min(r.equity*r.riskFraction,r.equity*r.dailyLossFraction-r.dailyLoss);
 const perLot=(p.stopDistance+p.spread+r.slippage)*r.valuePerPoint+r.commissionPerLot;
 const lots=Math.floor(Math.min(r.maxLot,budget/perLot)/r.lotStep)*r.lotStep;
 if(lots<r.minLot||lots*perLot>budget)return fail('Minimum lot exceeds remaining risk budget');
 return {ok:true,lots,riskAmount:lots*perLot,budget};
}
function context(rows,asOfUTC){
 if(!Array.isArray(rows)||rows.length<14)return {available:false};
 const {structure}=require('./v3_market_structure');
 const previous=structure(rows.slice(0,-1)),current=structure(rows);
 const hh=previous.high,ll=previous.low;
 const history=rows.slice(0,-1);
 const trend=hh&&ll?(history.at(-1).close>(hh.price+ll.price)/2?'UP':'DOWN'):'UNKNOWN';
 const hour=new Date(asOfUTC).getUTCHours();
 return {available:true,structure:current,priorRangeBias:trend,
 chochUp:trend==='DOWN'&&current.bosUp,chochDown:trend==='UP'&&current.bosDown,
 sessionUTC:hour>=13&&hour<16?'LONDON_NEW_YORK_OVERLAP':hour>=8&&hour<17?'LONDON':hour>=13&&hour<22?'NEW_YORK':'ASIA_OR_OFF_HOURS',
 sessionConvention:'Fixed UTC research windows; not exchange holidays or DST-adjusted sessions'};
}
function evaluate(input){
 if(!input||!finite(Date.parse(input.asOfUTC)))throw Error('Explicit asOfUTC required');
 const now=Date.parse(input.asOfUTC),layers={},blocked=[];
 const technical=assess(input.frames,input.asOfUTC);
 for(const name of FEEDS){layers[name]=evidence(name,input.feeds?.[name],now);if(layers[name].status!=='READY'||layers[name].blocked)blocked.push(name);}
 const tradePlan=plan(input.frames,input.asOfUTC,{spread:input.spread});
 const risk=riskSize(tradePlan,input.risk);
 if(!risk.ok)blocked.push('risk');
 if(!['BUY','SELL'].includes(technical.candidate)||!finite(tradePlan.target))blocked.push('technical');
 const direction=technical.candidate==='BUY'?1:-1;
 for(const name of ['DXY','US02Y','US10Y','GC','orderFlow'])if(layers[name].status==='READY'&&layers[name].score*direction<=0)blocked.push(name+': disagreement');
 const rows=input.frames?.M15||[];
 const ranges=rows.slice(-14).map((b,i,a)=>Math.max(b.high-b.low,i?Math.abs(b.high-a[i-1].close):0,i?Math.abs(b.low-a[i-1].close):0));
 const atr=ranges.length===14?ranges.reduce((a,b)=>a+b,0)/14:null;
 if(!finite(atr)||atr<=0||!finite(input.spread)||input.spread<0||input.spread>atr*0.2)blocked.push('volatility/spread');
 return {engine:'V3 Ultimate',version:1,mode:'offline-research',asOfUTC:input.asOfUTC,signal:'WAIT',executable:false,
 marketContext:context(input.frames?.M15,input.asOfUTC),researchCandidate:blocked.length?'NONE':technical.candidate,technical,atr,layers,tradePlan,risk,
 monitoring:{blocked:[...new Set(blocked)],readyFeeds:FEEDS.filter(n=>layers[n].status==='READY').length,totalFeeds:FEEDS.length},
 reason:blocked.length?'Mandatory evidence or risk gates blocked':'Research candidate only; strategy validation and operator review pending'};
}
module.exports={evaluate,evidence,riskSize,context};
if(require.main===module){try{process.stdout.write(JSON.stringify(evaluate(JSON.parse(require('node:fs').readFileSync(process.argv[2],'utf8'))),null,2)+'\n');}catch(e){console.error(e.message);process.exitCode=1;}}
