'use strict';
// Bounded private read-only transport probe, disabled by default. No auto-start,
// environment reads, prices in reports, storage, order endpoints or analysis.
// The operator must independently verify rights and entitlement before use.
const {createHandshake}=require('./massive_ws_handshake');
const ENDPOINT='wss://socket.massive.com/forex';
async function probe({authorized=false,credential,WebSocketImpl=globalThis.WebSocket,
 durationMs=60000,clock=Date.now,onQuote=()=>{}}={}){
 const blocked={status:'NOT_AUTHORIZED',signal:'WAIT',executable:false,
   paperOrdersAllowed:false,liveOrdersAllowed:false,socketAttempted:false,
   acceptedQuoteMessages:0,realDataQualificationProven:false};
 if(authorized!==true)return blocked;
 if(typeof credential!=='string'||!credential||credential.length>4096||
    typeof WebSocketImpl!=='function'||typeof clock!=='function'||typeof onQuote!=='function'||
    !Number.isInteger(durationMs)||durationMs<1000||durationMs>300000)
  return {...blocked,status:'INVALID_PROBE_CONFIGURATION'};
 return new Promise(resolve=>{
  let socket,handshake,timer,deadline,done=false;
  function finish(status){
   if(done)return;done=true;
   clearInterval(timer);clearTimeout(deadline);
   const counts=handshake?.report().acceptedQuoteMessages||0;
   if(handshake)handshake.stop();else{try{socket?.close();}catch{}}
   resolve({...blocked,status,socketAttempted:true,acceptedQuoteMessages:counts});
  }
  try{
   socket=new WebSocketImpl(ENDPOINT);
   handshake=createHandshake({credential,clock,onQuote,send:x=>socket.send(x),
    close:()=>{try{socket.close();}catch{}}});
   credential=null;
   socket.addEventListener('message',e=>{
    if(done)return;
    try{
     const r=handshake.frame(e.data);
     if(r.state==='CLOSED')finish(r.reason);
    }catch{finish('PROBE_FRAME_ERROR');}
   });
   socket.addEventListener('error',()=>finish('SOCKET_ERROR'));
   socket.addEventListener('close',()=>finish('SOCKET_CLOSED'));
   timer=setInterval(()=>{
    try{const r=handshake.tick();if(r.state==='CLOSED')finish(r.reason);}
    catch{finish('PROBE_CLOCK_ERROR');}
   },250);
   deadline=setTimeout(()=>finish(handshake.report().acceptedQuoteMessages>0?
    'BOUNDED_OBSERVATION_ENDED_NOT_QUALIFIED':'NO_QUOTES_OBSERVED'),durationMs);
  }catch{credential=null;finish('SOCKET_SETUP_FAILED');}
 });
}
module.exports={probe};
