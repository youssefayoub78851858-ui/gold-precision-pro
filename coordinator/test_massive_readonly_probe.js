'use strict';
const a=require('node:assert/strict');
const {probe}=require('./massive_readonly_probe');
let created=0;
const now=Date.parse('2026-11-27T12:00:00Z');
class FakeSocket{
 constructor(url){created++;a.equal(url,'wss://socket.massive.com/forex');
  this.handlers={};queueMicrotask(()=>this.emit('message',JSON.stringify({ev:'status',status:'connected'})));}
 addEventListener(k,fn){this.handlers[k]=fn;}
 emit(k,data){this.handlers[k]?.({data});}
 send(raw){const x=JSON.parse(raw);
  if(x.action==='auth'){a.equal(x.params,'MOCK_ONLY');queueMicrotask(()=>this.emit('message',JSON.stringify({ev:'status',status:'auth_success'})));}
  else{a.equal(x.params,'C.XAU-USD');queueMicrotask(()=>{
   this.emit('message',JSON.stringify([{ev:'status',status:'success',message:'subscribed to: C.XAU-USD'},
    {ev:'C',p:'XAU/USD',b:100,a:100.4,t:now}]));
  });}}
 close(){}
}
(async()=>{
 const blocked=await probe({WebSocketImpl:FakeSocket,credential:'MOCK_ONLY'});
 a.equal(blocked.socketAttempted,false);a.equal(created,0);
 const invalid=await probe({authorized:true,WebSocketImpl:FakeSocket,credential:'MOCK_ONLY',durationMs:1});
 a.equal(invalid.status,'INVALID_PROBE_CONFIGURATION');a.equal(created,0);
 const result=await probe({authorized:true,credential:'MOCK_ONLY',WebSocketImpl:FakeSocket,durationMs:1000,clock:()=>now});
 a.equal(created,1);a.equal(result.acceptedQuoteMessages,1);
 a.equal(result.status,'BOUNDED_OBSERVATION_ENDED_NOT_QUALIFIED');
 a.equal(result.signal,'WAIT');a.equal(result.executable,false);a.equal(result.realDataQualificationProven,false);
 a(!JSON.stringify(result).includes('MOCK_ONLY'));a(!JSON.stringify(result).includes('100.4'));
 class BadSocket extends FakeSocket{send(){queueMicrotask(()=>this.emit('message',JSON.stringify({ev:'status',status:'auth_failed'})));}}
 const bad=await probe({authorized:true,credential:'MOCK_ONLY',WebSocketImpl:BadSocket,durationMs:1000,clock:()=>now});
 a.equal(bad.status,'AUTH_OR_ENTITLEMENT_REFUSED');a.equal(bad.acceptedQuoteMessages,0);
 console.log('PASS disabled-default and bounded read-only socket probe with mock transport only');
})().catch(e=>{console.error(e);process.exitCode=1;});
