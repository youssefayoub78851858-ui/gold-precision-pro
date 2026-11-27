'use strict';
// Transport lifecycle boundary. No socket, network, env, timers, storage, or
// orders are created here. A future approved private collector supplies a
// socket's send/close callbacks and a credential from isolated secret storage.
// This module is not data-rights or activation authority. No market data output.
const TOPIC='C.XAU-USD', LIMIT=65536, HANDSHAKE_MS=15000, QUOTE_IDLE_MS=30000;
function createHandshake({send, close, credential, clock=Date.now}={}){
 if(typeof send!=='function'||typeof close!=='function'||typeof clock!=='function'||
    typeof credential!=='string'||!credential||credential.length>4096)
  throw new Error('Invalid transport configuration');
 let secret=credential; credential=null;
 let state='WAIT_CONNECTED', reason='AWAITING_CONNECTED', last=clock(), quotes=0;
 if(!Number.isFinite(last))throw new Error('Invalid transport clock');
 function report(){return {state,reason,acceptedQuoteMessages:quotes,
  signal:'WAIT',executable:false,paperOrdersAllowed:false,liveOrdersAllowed:false};}
 function stop(code='TRANSPORT_CLOSED'){
  if(state==='CLOSED')return report();
  secret=null;state='CLOSED';reason=code;
  try{close();}catch{} // never expose provider or secret-containing errors
  return report();
 }
 function tick(){
  if(state==='CLOSED')return report();
  const now=clock(),limit=state==='STREAMING'?QUOTE_IDLE_MS:HANDSHAKE_MS;
  if(!Number.isFinite(now)||now<last||now-last>=limit)
   return stop(state==='STREAMING'?'QUOTE_IDLE_OR_CLOCK':'HANDSHAKE_TIMEOUT_OR_CLOCK');
  return report();
 }
 function transmit(action,params){
  try{send(JSON.stringify({action,params}));return true;}
  catch{stop('SEND_FAILED');return false;}
 }
 function frame(raw){
  if(tick().state==='CLOSED')return report();
  if(typeof raw!=='string'||raw.length>LIMIT)return stop('BAD_FRAME');
  let parsed;try{parsed=JSON.parse(raw);}catch{return stop('BAD_FRAME');}
  const batch=Array.isArray(parsed)?parsed:[parsed];
  if(!batch.length||batch.length>2000)return stop('BAD_FRAME');
  for(const e of batch){
   if(state==='CLOSED')break;
   if(!e||typeof e!=='object'||Array.isArray(e))return stop('BAD_FRAME');
   if(e.ev==='status'){
    if(['auth_failed','error','max_connections','not_authorized','unauthorized'].includes(e.status))
     return stop('AUTH_OR_ENTITLEMENT_REFUSED');
    if(e.status==='connected'){
     if(state!=='WAIT_CONNECTED')return stop('UNEXPECTED_CONNECTED');
     state='WAIT_AUTH';reason='AWAITING_AUTH';last=clock();
     const value=secret;secret=null;
     if(!transmit('auth',value))return report();
    }else if(e.status==='auth_success'){
     if(state!=='WAIT_AUTH')return stop('UNEXPECTED_AUTH');
     state='WAIT_SUBSCRIPTION';reason='AWAITING_SUBSCRIPTION';last=clock();
     if(!transmit('subscribe',TOPIC))return report();
    }else if(e.status==='success'&&e.message==='subscribed to: '+TOPIC){
     if(state!=='WAIT_SUBSCRIPTION')return stop('UNEXPECTED_SUBSCRIPTION');
     state='STREAMING';reason='AWAITING_FIRST_QUOTE';last=clock();
    }
   }else if(e.ev==='C'&&e.p==='XAU/USD'){
    if(state!=='STREAMING')return stop('QUOTE_BEFORE_SUBSCRIPTION');
    const now=clock();
    if(!Number.isSafeInteger(e.t)||e.t<=0||e.t>now||now-e.t>QUOTE_IDLE_MS||
       typeof e.b!=='number'||typeof e.a!=='number'||!Number.isFinite(e.b)||
       !Number.isFinite(e.a)||e.b<=0||e.a<e.b)
     return stop('INVALID_OR_STALE_QUOTE');
    quotes++;last=now;reason='TRANSPORT_QUOTE_RECEIVED_NOT_SOURCE_APPROVED';
   }
  }
  return report();
 }
 return Object.freeze({frame,tick,stop,report});
}
module.exports={createHandshake};
