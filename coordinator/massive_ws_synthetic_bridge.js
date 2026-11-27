'use strict';
// Offline bridge only. No socket factory, real credentials, provider calls,
// persistent storage, or order admission. All input/output is synthetic.
const {createHandshake}=require('./massive_ws_handshake');
const {MassiveQuoteStandby}=require('./massive_ws_standby');
function createSyntheticBridge(clock){
 if(typeof clock!=='function')throw Error('Explicit test clock required');
 const bars=new MassiveQuoteStandby(clock);
 const handshake=createHandshake({clock,credential:'SYNTHETIC_NOT_A_KEY',
  send:()=>{},close:()=>bars.disconnect('TRANSPORT_CLOSED')});
 function frame(raw){
  if(handshake.tick().state==='CLOSED')return handshake.report();
  if(typeof raw!=='string'||raw.length>65536)return handshake.stop('BAD_FRAME');
  let batch;
  try{const p=JSON.parse(raw);batch=Array.isArray(p)?p:[p];}
  catch{return handshake.stop('BAD_FRAME');}
  if(!batch.length||batch.length>2000||batch.some(e=>!e||typeof e!=='object'||Array.isArray(e)))
   return handshake.stop('BAD_FRAME');
  for(const e of batch){
   const status=handshake.frame(JSON.stringify(e));
   if(status.state==='CLOSED')return status;
   const result=bars.handle(e);
   if(result.kind==='blocked')return handshake.stop('CANDLE_VALIDATION_FAILED');
  }
  return handshake.report();
 }
 function packet(){
  const state=handshake.tick(),s=bars.snapshot();
  if(state.state!=='STREAMING'||!s.lastSyntheticQuote||
     !s.bidFrames.M15.length||!s.bidFrames.H1.length||!s.bidFrames.H4.length)
   return null;
  const frames={};
  for(const [tf,interval] of [['M15','15min'],['H1','1h'],['H4','4h']]){
   const candles=s.bidFrames[tf];
   frames[interval]={candles,expectedOpenTimes:candles.map(c=>c.openTime)};
  }
  return {provider:'MASSIVE_SYNTHETIC_STREAM_ONLY',instrument:'XAU/USD',
   mode:'synthetic',priceBasis:'BID',receivedUTC:new Date(clock()).toISOString(),frames};
 }
 return Object.freeze({frame,packet,tick:()=>handshake.tick(),stop:()=>handshake.stop()});
}
module.exports={createSyntheticBridge};
