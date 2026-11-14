'use strict';
// Pure offline FXCM native data-intake contract. Never imports or runs a vendor SDK.
const W={M15:900000,H1:3600000,H4:14400000},SIDE=['bid','ask'],OHLC=['open','high','low','close'];
const blockers=['FXCM_CLOUD_EULA_UNVERIFIED','FXCM_DEMO_READ_ONLY_ACCESS_UNVERIFIED','FXCM_NATIVE_SDK_AND_UTC_CLOCK_UNVERIFIED','FXCM_LIVE_VS_HISTORICAL_BID_ASK_UNVERIFIED','PAPER_AND_REAL_TRADING_DISABLED'];
function utc(x){
 if(typeof x!=='string'||!/^20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,3})?Z$/.test(x))throw Error('UTC_Z_REQUIRED');
 const t=Date.parse(x);
 if(!Number.isFinite(t)||new Date(t).toISOString().slice(0,19)!==x.slice(0,19))throw Error('INVALID_UTC_TIMESTAMP');
 return t;
}
function frame(rows,tf,now){
 if(!Array.isArray(rows)||!rows.length||rows.length>2048)throw Error('FRAME_MISSING_OR_TOO_LONG');
 const indexed=new Map();let prev=-Infinity,gaps=0;
 for(const r of rows){
  const t=utc(r?.openTime);
  if(t%W[tf]||t+W[tf]>now)throw Error('UNALIGNED_OR_UNCLOSED_CANDLE');
  if(t<=prev)throw Error('DUPLICATE_OR_UNSORTED_TIME');
  if(prev!==-Infinity)gaps+=Math.max(0,(t-prev)/W[tf]-1);
  const sides={};
  for(const side of SIDE){
   const p=r?.[side];if(!p||typeof p!=='object'||Array.isArray(p))throw Error('SEPARATE_BID_ASK_REQUIRED');
   const out={};
   for(const k of OHLC){
    if(typeof p[k]!=='number'||!Number.isFinite(p[k])||p[k]<=0)throw Error('INVALID_PRICE');
    out[k]=p[k];
   }
   if(out.high<Math.max(out.open,out.low,out.close)||out.low>Math.min(out.open,out.high,out.close))throw Error('INVALID_OHLC');
   sides[side]=out;
  }
  for(const k of OHLC)if(sides.ask[k]<sides.bid[k])throw Error('CROSSED_BID_ASK');
  indexed.set(t,sides);prev=t;
 }
 return {indexed,count:rows.length,gaps};
}
function overlap(m15,higher,tf){
 let compared=0;
 const count=W[tf]/W.M15;
 for(const [t,v] of higher.indexed){
  const bars=Array.from({length:count},(_,i)=>m15.indexed.get(t+i*W.M15));
  const present=bars.filter(Boolean).length;
  if(present&&present<count)throw Error('PARTIAL_M15_COVERAGE');
  if(!present)continue;
  for(const side of SIDE){
   const aggregate={open:bars[0][side].open,high:Math.max(...bars.map(b=>b[side].high)),low:Math.min(...bars.map(b=>b[side].low)),close:bars.at(-1)[side].close};
   for(const k of OHLC)if(Math.abs(aggregate[k]-v[side][k])>0.00001)throw Error('BID_ASK_TIMEFRAME_MISMATCH');
  }
  compared++;
 }
 return compared;
}
function assess(packet,asOfUTC){
 const errors=[],counts={M15:0,H1:0,H4:0},gaps={M15:0,H1:0,H4:0},overlaps={H1:0,H4:0};
 try{
  const now=utc(asOfUTC);
  if(!packet||typeof packet!=='object'||Array.isArray(packet))throw Error('INVALID_PACKET');
  if(packet.provider!=='FXCM'||packet.source!=='FOREXCONNECT_NATIVE_CPP'||packet.instrument!=='XAU/USD')throw Error('WRONG_PROVIDER_SOURCE_OR_INSTRUMENT');
  const arrived=utc(packet.receivedUTC);
  if(arrived>now+60000||now-arrived>120000)throw Error('STALE_PACKET');
  if(!packet.frames||typeof packet.frames!=='object'||Object.keys(packet.frames).sort().join(',')!=='H1,H4,M15')throw Error('ALL_THREE_FRAMES_REQUIRED');
  const f={};
  for(const tf of Object.keys(W)){f[tf]=frame(packet.frames[tf],tf,now);counts[tf]=f[tf].count;gaps[tf]=f[tf].gaps;}
  overlaps.H1=overlap(f.M15,f.H1,'H1');
  overlaps.H4=overlap(f.M15,f.H4,'H4');
  if(!overlaps.H1||!overlaps.H4)throw Error('NO_COMPLETE_TIMEFRAME_OVERLAP');
 }catch(e){errors.push(e.message||'INVALID_FXCM_RECORD');}
 return {provider:'FXCM',adapter:'NATIVE_CPP_JSON_OFFLINE_ONLY',
  status:errors.length?'BLOCKED_INVALID_RECORD':'WAIT_UNVERIFIED_LIVE_SOURCE',
  structureValid:!errors.length,frameCounts:counts,unverifiedGapCounts:gaps,verifiedGeometricOverlaps:overlaps,
  signal:'WAIT',executable:false,researchEligible:false,paperOrdersAllowed:false,
  sourceRequestsMade:0,orderRequestsMade:0,credentialReads:0,sdkLoaded:false,engineCalled:false,
  rawCandlesReleased:false,sourceRightsVerified:false,clockBasisVerified:false,
  blockingReasons:[...errors,...blockers,...(Object.values(gaps).some(n=>n)?['SESSION_SCHEDULE_GAPS_UNVERIFIED']:[])]};
}
module.exports={assess};
if(require.main===module)console.log(JSON.stringify(assess(null,'2026-11-13T16:00:00Z')));
