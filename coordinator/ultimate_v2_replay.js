'use strict';
// Same development archives, two explicit engine versions; not a fresh holdout.
const fs=require('node:fs');
const {evaluate}=require('./ultimate_v2');
const {selectKnown,ROLES}=require('./ultimate_v2_contracts');
const {checkFrame}=require('./v3_multitimeframe');
const input=JSON.parse(fs.readFileSync(0,'utf8'));
const duration={'15min':900000,'1h':3600000,'4h':14400000};
const position={'15min':0,'1h':0,'4h':0},prefix={'15min':[],'1h':[],'4h':[]};
const layers=['XAUUSD',...Object.keys(ROLES)];
const ready=Object.fromEntries(layers.map(n=>[n,0]));
const fail=Object.fromEntries(layers.map(n=>[n,{}]));
const counts={v1:{},v2:{}},cases=[];
let total=0,priceReady=0,allReady=0,candidateV1=0,candidateV2=0;
// Validate and order once; selectKnown rechecks rows when provided, never supplies absent data.
if(input.records)selectKnown(input.records,'1970-01-01T00:00:00Z');
for(const bar of input.frames['15min']){
 const now=Date.parse(bar.datetime)+900000,asOfUTC=new Date(now).toISOString();
 for(const [name,ms] of Object.entries(duration)){
  const source=input.frames[name];
  while(position[name]<source.length&&Date.parse(source[position[name]].datetime)+ms<=now)prefix[name].push(source[position[name]++]);
 }
 const frames={M15:prefix['15min'],H1:prefix['1h'],H4:prefix['4h']};
 const out=evaluate({frames,asOfUTC,feeds:input.records?selectKnown(input.records,asOfUTC):{},spread:input.spread,risk:input.risk});
 if(out.signal!=='WAIT'||out.executable!==false)throw Error('Execution invariant violated');
 const price=Object.entries(duration).map(([n,ms])=>[n,checkFrame(prefix[n],ms/60000,now)]);
 const priceOK=price.every(([,status])=>status.ok);if(priceOK)priceReady++;
 const valid={XAUUSD:priceOK};
 for(const [n,status] of price)if(!status.ok){const k=n+': '+status.reason;fail.XAUUSD[k]=(fail.XAUUSD[k]||0)+1;}
 for(const name of Object.keys(ROLES)){
  valid[name]=out.layers[name].status==='READY';
  if(!valid[name]){const reason=out.layers[name].reason;fail[name][reason]=(fail[name][reason]||0)+1;}
 }
 for(const n of layers)if(valid[n])ready[n]++;
 if(Object.values(valid).every(Boolean))allReady++;
 for(const [version,blocks] of [['v1',out.legacyComparison.blockers],['v2',out.monitoring.blocked]])for(const gate of blocks)counts[version][gate]=(counts[version][gate]||0)+1;
 if(out.legacyComparison.researchCandidate!=='NONE')candidateV1++;
 if(out.researchCandidate!=='NONE')candidateV2++;
 if(['BUY','SELL'].includes(out.technical.candidate))cases.push({asOfUTC,technicalLabel:out.technical.candidate,executable:false,v1Blockers:out.legacyComparison.blockers,v2Blockers:out.monitoring.blocked});
 total++;
}
const pct=n=>total?Math.round(n*1000000/total)/10000:null;
process.stdout.write(JSON.stringify({kind:'ULTIMATE_VERSIONED_ARCHIVE_REPLAY',contractVersion:2,executable:false,networkEnabled:false,isIndependentHoldout:false,
 assessment:'Reinterpretation of the same September/October development archives; no new independent performance evidence',observedM15Decisions:total,
 dataCoverage:Object.fromEntries(layers.map(n=>[n,{role:n==='XAUUSD'?'CLOSED_PRICE_FRAMES':ROLES[n],readyObservations:ready[n],coveragePct:pct(ready[n]),failureReasons:fail[n]}])),
 jointCoveragePct:pct(allReady),meanLayerCoveragePct:total?pct(Object.values(ready).reduce((a,b)=>a+b,0)/layers.length):null,
 roleCoverage:{dailyContext:{US02Y:pct(ready.US02Y),US10Y:pct(ready.US10Y)},intraday:{DXY:pct(ready.DXY),GC:pct(ready.GC),orderFlow:pct(ready.orderFlow)},events:{knownSchedule:pct(ready.calendar),observedNews:pct(ready.headlines)}},
 researchCandidates:{v1:candidateV1,v2:candidateV2},gateBlockCounts:counts,directionalResearchCases:cases,
 noPerformanceInference:true,note:'No sources filled, no synthetic rows, no trial or subscription activated; missing inputs remain mandatory blockers'}));
