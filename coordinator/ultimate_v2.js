'use strict';
// Independent Ultimate revision. Previous engine remains unchanged and is a comparison input.
const legacy=require('./v3_ultimate');
const {ROLES,assessLayer,time,issues}=require('./ultimate_v2_contracts');
function evaluate(input){
 if(!input||!Number.isFinite(time(input.asOfUTC)))throw Error('Explicit UTC asOfUTC required');
 const excluded=Object.keys(input.feeds||{}).filter(n=>issues(n,input.feeds[n]).length);
 const accepted=Object.fromEntries(Object.entries(input.feeds||{}).filter(([n])=>!excluded.includes(n)));
 const previous=legacy.evaluate({...input,feeds:accepted}),layers={},blocked=[];
 for(const name of Object.keys(ROLES)){
  layers[name]=assessLayer(name,input.feeds?.[name],input.asOfUTC);
  if(layers[name].status!=='READY'||layers[name].blocked)blocked.push(name);
 }
 const {technical,tradePlan,risk,atr}=previous;
 if(!['BUY','SELL'].includes(technical.candidate)||!Number.isFinite(tradePlan.target))blocked.push('technical');
 if(!risk.ok)blocked.push('risk');
 if(!Number.isFinite(atr)||atr<=0||!Number.isFinite(input.spread)||input.spread<0||input.spread>atr*.2)blocked.push('volatility/spread');
 const daily=['US02Y','US10Y'];
 if(daily.every(n=>layers[n].status==='READY')&&layers.US02Y.observationDate!==layers.US10Y.observationDate)blocked.push('dailyContext: different observation dates');
 const intraday=['DXY','GC','orderFlow'];
 if(intraday.every(n=>layers[n].status==='READY')){
  const times=intraday.map(n=>time(layers[n].observedUTC));
  if(Math.max(...times)-Math.min(...times)>60000)blocked.push('intraday: observation skew');
  if(layers.GC.contract!==layers.orderFlow.contract)blocked.push('intraday: GC contract mismatch');
  if(input.feeds.GC.contractExpiryUTC!==input.feeds.orderFlow.contractExpiryUTC)blocked.push('intraday: GC expiry mismatch');
 }
 if(['BUY','SELL'].includes(technical.candidate)){
  const sign=technical.candidate==='BUY'?1:-1;
  for(const name of intraday)if(layers[name].status==='READY'&&layers[name].score*sign<=0)blocked.push(name+': disagreement');
 }
 return {engine:'V3 Ultimate',version:2,contractVersion:'ultimate-context-events-v2',mode:'offline-research',asOfUTC:input.asOfUTC,
  signal:'WAIT',executable:false,networkEnabled:false,dataModes:[...new Set(Object.values(layers).map(x=>x.mode).filter(Boolean))],technical,tradePlan,risk,atr,layers,
  researchCandidate:blocked.length?'NONE':technical.candidate,
  dailyContext:{directionalVote:false,requiredForAdmission:true,US02Y:layers.US02Y,US10Y:layers.US10Y},
  monitoring:{blocked:[...new Set(blocked)],readyFeeds:Object.values(layers).filter(x=>x.status==='READY').length,totalFeeds:7},
  legacyComparison:{version:1,invalidV2RowsExcluded:excluded,researchCandidate:previous.researchCandidate,blockers:previous.monitoring.blocked,layers:previous.layers},
  reason:blocked.length?'Mandatory v2 data, event, technical or risk gates blocked':'Research candidate only; never an execution instruction'};
}
module.exports={evaluate};
if(require.main===module){try{const fs=require('node:fs');const text=fs.readFileSync(process.argv[2]||0,'utf8');process.stdout.write(JSON.stringify(evaluate(JSON.parse(text)),null,2)+'\n');}catch(e){console.error(e.message);process.exitCode=1;}}
