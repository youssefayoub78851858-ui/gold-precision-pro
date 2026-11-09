'use strict';
const fs=require('fs');
const {ema,rsi,analyze}=require('./app/frozen/strategy');
const doc=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const sizes={'15min':900000,'1h':3600000,'4h':14400000};
const frames=doc.frames;
const result={source:doc.source,frames:{},alignedDecisionCounts:{BUY:0,SELL:0,WAIT:0},allFrameDirections:{},samples:0};
for(const [frame,bars] of Object.entries(frames)){
 const first=Date.parse(bars[0].datetime),last=Date.parse(bars.at(-1).datetime);
 const gaps=[];
 for(let i=1;i<bars.length;i++){const delta=Date.parse(bars[i].datetime)-Date.parse(bars[i-1].datetime);if(delta>sizes[frame])gaps.push({at:bars[i].datetime,missingSlots:delta/sizes[frame]-1});}
 result.frames[frame]={count:bars.length,first:bars[0].datetime,last:bars.at(-1).datetime,firstClose:bars[0].close,lastClose:bars.at(-1).close,priceChangePercent:+((bars.at(-1).close/bars[0].close-1)*100).toFixed(3),gapCount:gaps.length,missingSlots:gaps.reduce((a,g)=>a+g.missingSlots,0),largestGaps:gaps.sort((a,b)=>b.missingSlots-a.missingSlots).slice(0,3)};
 result.allFrameDirections[frame]={BUY:0,SELL:0,WAIT:0,emaBullRsiBull:0,emaBearRsiBear:0,emaBullRsiBear:0,emaBearRsiBull:0};
 for(let i=59;i<bars.length;i++){
  const c=bars.slice(0,i+1).map(x=>x.close);
  const fast=ema(c,20),slow=ema(c,50),momentum=rsi(c);
  const direction=fast>slow&&momentum>50&&momentum<70?'BUY':fast<slow&&momentum<50&&momentum>30?'SELL':'WAIT';
  const bucket=result.allFrameDirections[frame];bucket[direction]++;
  bucket[(fast>slow?'emaBull':'emaBear')+(momentum>50?'RsiBull':'RsiBear')]++;
 }
}
const pos={'15min':-1,'1h':-1,'4h':-1};
for(let i=0;i<frames['15min'].length-1;i++){
 const t=Date.parse(frames['15min'][i].datetime)+sizes['15min'];
 const snap={};
 for(const frame of ['15min','1h','4h']){
  while(pos[frame]+1<frames[frame].length&&Date.parse(frames[frame][pos[frame]+1].datetime)+sizes[frame]<=t)pos[frame]++;
  snap[frame]=frames[frame].slice(0,pos[frame]+1);
 }
 const a=analyze(snap,{historical:true});
 result.alignedDecisionCounts[a.signal]=(result.alignedDecisionCounts[a.signal]||0)+1;result.samples++;
}
console.log(JSON.stringify(result,null,2));
