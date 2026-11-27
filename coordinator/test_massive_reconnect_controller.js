'use strict';
const a=require('node:assert/strict');
const {reconnect}=require('./massive_reconnect_controller');
(async()=>{
 let calls=0;
 const runProbe=async()=>{calls++;return {status:'SOCKET_ERROR'};};
 const sleep=async()=>{};
 let r=await reconnect({credential:'MOCK_ONLY',runProbe,sleep});
 a.equal(r.status,'NOT_AUTHORIZED');a.equal(calls,0);
 r=await reconnect({authorized:true,credential:'MOCK_ONLY',runProbe,sleep,maxAttempts:3});
 a.equal(r.status,'RETRY_LIMIT_REACHED');a.equal(calls,3);a.deepEqual(r.delaysMs,[1000,2000]);
 a.equal(r.signal,'WAIT');a.equal(r.historyContinuityVerified,false);
 calls=0;
 r=await reconnect({authorized:true,credential:'MOCK_ONLY',sleep,runProbe:async()=>({status:++calls===1?'SOCKET_CLOSED':'BOUNDED_OBSERVATION_ENDED_NOT_QUALIFIED'})});
 a.equal(r.status,'OBSERVATION_ENDED_NOT_QUALIFIED');a.equal(calls,2);
 a.equal(r.paperOrdersAllowed,false);a(!JSON.stringify(r).includes('MOCK_ONLY'));
 for(const status of ['AUTH_OR_ENTITLEMENT_REFUSED','PRIVATE_QUOTE_CONSUMER_FAILED','QUOTE_SEQUENCE_GAP_OR_REVERSE']){
  calls=0;r=await reconnect({authorized:true,credential:'MOCK_ONLY',sleep,runProbe:async()=>{calls++;return {status};}});
  a.equal(r.status,'STOPPED_NON_RETRYABLE');a.equal(calls,1);
 }
 const ctl=new AbortController();calls=0;
 r=await reconnect({authorized:true,credential:'MOCK_ONLY',runProbe,sleep:async()=>ctl.abort(),signal:ctl.signal});
 a.equal(r.status,'CANCELLED');a.equal(calls,1);
 console.log('PASS bounded offline reconnect, stop on entitlement/gaps/consumer errors, cancellation between attempts');
})().catch(e=>{console.error(e);process.exitCode=1;});
