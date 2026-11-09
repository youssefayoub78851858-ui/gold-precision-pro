'use strict';
// Review-only execution policy: UTC native bar grid, no fabricated session bars.
// decisionTime is the current M15 close, not the observation timestamp.
const duration={'15min':900000,'1h':3600000,'4h':14400000};
const stamp=c=>Date.parse(c.datetime.includes('T')?c.datetime:c.datetime.replace(' ','T')+'Z');
function admit(frames,observedAt,{marketOpen=true,maximumDelayMs=90000}={}){
 const decisionTime=Math.floor(observedAt/duration['15min'])*duration['15min'];
 const fail=(reason,details={})=>({accepted:false,reason,decisionTime,...details});
 if(!Number.isFinite(observedAt))return fail('INVALID_OBSERVATION_TIME');
 if(!marketOpen)return fail('MARKET_CLOSED');
 if(observedAt-decisionTime>maximumDelayMs)return fail('MISSED_OBSERVATION_WINDOW');
 const selected={};
 for(const [frame,ms] of Object.entries(duration)){
  const input=frames[frame];if(!Array.isArray(input))return fail('MISSING_FRAME',{frame});
  let previous=-Infinity;
  for(const c of input){const t=stamp(c);if(!Number.isFinite(t)||t<=previous)return fail('INVALID_OR_UNORDERED_TIME',{frame});previous=t;
   const v=['open','high','low','close'].map(k=>Number(c[k]));
   if(v.some(x=>!Number.isFinite(x)||x<=0)||v[2]>Math.min(v[0],v[3])||v[1]<Math.max(v[0],v[3]))return fail('INVALID_OHLC',{frame});
  }
  selected[frame]=input.filter(c=>stamp(c)+ms<=decisionTime);
  const last=selected[frame].at(-1),expectedOpen=Math.floor(decisionTime/ms)*ms-ms;
  if(!last)return fail('MISSING_CLOSED_BAR',{frame,expectedOpen});
  if(stamp(last)!==expectedOpen)return fail('MISSING_LATEST_EXPECTED_CLOSED_BAR_OR_UNVERIFIED_GRID',{frame,expectedOpen,actualOpen:stamp(last)});
 }
 return {accepted:true,reason:'LATEST_EXPECTED_CLOSED_BARS_PRESENT',decisionTime,frames:selected};
}
module.exports={admit,duration,stamp};
