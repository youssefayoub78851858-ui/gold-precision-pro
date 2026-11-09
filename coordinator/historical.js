'use strict';
const {admit,duration,stamp}=require('./timing');
const {analyze}=require('./app/frozen/strategy');
const {marketOpen}=require('./app/paper-core');
// The same observation lag and market policy are applied on BOTH paths.
function evaluate(frames,lagMs=5000){
 const ordered=Object.fromEntries(Object.entries(frames).map(([f,a])=>[f,[...a].sort((a,b)=>stamp(a)-stamp(b))]));
 const rows=[],signals=[],oldSignals=[],unrestrictedSignals=[];
 for(let index=0;index<ordered['15min'].length-1;index++){
  const close=stamp(ordered['15min'][index])+900000,now=close+lagMs;
  const snapshot=Object.fromEntries(Object.entries(ordered).map(([f,a])=>[f,a.filter(c=>stamp(c)+duration[f]<=close)]));
  const old=marketOpen(now)&&Object.entries(duration).every(([f,ms])=>{const c=snapshot[f].at(-1);return c&&(now-stamp(c))<=({'15min':30,'1h':90,'4h':300}[f]*60000)});
  const g=admit(snapshot,now,{marketOpen:marketOpen(now)});
  const d=analyze(snapshot,{historical:true});
  const directional=['BUY','SELL'].includes(d.signal);
  const sig={index,side:d.signal,stop:d.stopReference,target:d.target2Reference};
  if(directional){unrestrictedSignals.push(sig);if(old)oldSignals.push(sig);if(g.accepted)signals.push(sig);}
  rows.push({index,closeUTC:new Date(close).toISOString(),oldAccepted:old,newAccepted:g.accepted,rejection:g.accepted?null:g.reason,signal:d.signal,directional,decision:g.accepted?analyze(g.frames,{dataFresh:true}):null});
 }
 return {rows,signals,oldSignals,unrestrictedSignals};
}
module.exports={evaluate};
