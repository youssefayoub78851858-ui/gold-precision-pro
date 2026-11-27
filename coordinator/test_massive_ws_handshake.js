'use strict';
const a=require('node:assert/strict');
const {createHandshake}=require('./massive_ws_handshake');
function fixture(sendFail=false){
 let now=Date.parse('2026-11-10T12:00:00Z'),closes=0;const sent=[];
 const c=createHandshake({credential:'SYNTHETIC_NOT_A_KEY',clock:()=>now,
   send:x=>{if(sendFail)throw Error('SYNTHETIC_NOT_A_KEY');sent.push(JSON.parse(x));},
   close:()=>{closes++;}});
 return {c,sent,closeCount:()=>closes,advance:n=>{now+=n;},
  status:(status,message)=>c.frame(JSON.stringify([{ev:'status',status,message}])),
  quote:(over={})=>c.frame(JSON.stringify([{ev:'C',p:'XAU/USD',t:now,b:100,a:100.4,...over}]))};
}
function start(f){f.status('connected');f.status('auth_success');f.status('success','subscribed to: C.XAU-USD');}
let f=fixture();
a.equal(f.c.report().state,'WAIT_CONNECTED');a.deepEqual(f.sent,[]);
a.equal(f.status('connected').state,'WAIT_AUTH');
a.deepEqual(f.sent,[{action:'auth',params:'SYNTHETIC_NOT_A_KEY'}]);
a.equal(f.status('auth_success').state,'WAIT_SUBSCRIPTION');
a.deepEqual(f.sent[1],{action:'subscribe',params:'C.XAU-USD'});
a.equal(f.status('success','subscribed to: C.XAU-USD').state,'STREAMING');
a.equal(f.quote().acceptedQuoteMessages,1);
a.equal(f.c.report().signal,'WAIT');a.equal(f.c.report().executable,false);
a.equal(f.c.report().paperOrdersAllowed,false);
a(!JSON.stringify(f.c.report()).includes('SYNTHETIC_NOT_A_KEY'));
f.advance(30000);a.equal(f.c.tick().reason,'QUOTE_IDLE_OR_CLOCK');
a.equal(f.closeCount(),1);f.c.stop();f.quote();a.equal(f.closeCount(),1);
f=fixture();f.advance(15000);a.equal(f.c.tick().reason,'HANDSHAKE_TIMEOUT_OR_CLOCK');a.equal(f.sent.length,0);
f=fixture();a.equal(f.quote().reason,'QUOTE_BEFORE_SUBSCRIPTION');
f=fixture();a.equal(f.status('auth_success').reason,'UNEXPECTED_AUTH');
f=fixture();f.status('connected');a.equal(f.status('auth_failed').reason,'AUTH_OR_ENTITLEMENT_REFUSED');
a.equal(f.sent.length,1);
f=fixture();start(f);a.equal(f.quote({a:99}).reason,'INVALID_OR_STALE_QUOTE');
f=fixture();start(f);a.equal(f.status('success','subscribed to: C.XAU-USD').reason,'UNEXPECTED_SUBSCRIPTION');
f=fixture(true);a.equal(f.status('connected').reason,'SEND_FAILED');a.equal(f.closeCount(),1);
a(!JSON.stringify(f.c.report()).includes('SYNTHETIC_NOT_A_KEY'));
f=fixture();a.equal(f.c.frame('{').reason,'BAD_FRAME');
f=fixture();start(f);f.advance(-1);a.equal(f.c.tick().reason,'QUOTE_IDLE_OR_CLOCK');
console.log('PASS offline transport handshake, auth/subscribe ordering, timeout, rejection, secret-safe status; no socket opened');
