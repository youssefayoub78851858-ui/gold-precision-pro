'use strict';
// One offline process: only closed prefixes are passed to either strategy.
const fs=require('node:fs');
const {evaluate}=require('./v3_ultimate');
const {analyze}=require('./app/frozen/strategy');
const input=JSON.parse(fs.readFileSync(0,'utf8'));
const durations={'15min':900000,'1h':3600000,'4h':14400000};
const positions={'15min':0,'1h':0,'4h':0},prefix={'15min':[],'1h':[],'4h':[]};
const decisions=[];
for(const bar of input.frames['15min']){
 const time=Date.parse(bar.datetime)+900000;
 for(const [name,ms] of Object.entries(durations)){
  const source=input.frames[name];
  while(positions[name]<source.length&&Date.parse(source[positions[name]].datetime)+ms<=time)prefix[name].push(source[positions[name]++]);
 }
 const asOfUTC=new Date(time).toISOString();
 const v2=analyze(prefix,{historical:true});
 const snapshot={asOfUTC,frames:{M15:prefix['15min'],H1:prefix['1h'],H4:prefix['4h']},feeds:input.evidence?.[asOfUTC]||{},spread:input.spread,risk:input.risk};
 const ultimate=evaluate(snapshot);
 decisions.push({asOfUTC,v2:{signal:v2.signal,executable:false,stop:v2.stopReference,target:v2.target2Reference},ultimate:{signal:ultimate.signal,executable:ultimate.executable,researchCandidate:ultimate.researchCandidate,risk:ultimate.risk,tradePlan:ultimate.tradePlan,monitoring:ultimate.monitoring}});
}
process.stdout.write(JSON.stringify(decisions));
