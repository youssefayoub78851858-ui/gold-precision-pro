"use strict";
const assert=require("node:assert/strict");
const {assess,checkFrame}=require("./v3_multitimeframe");
const end=Date.parse("2026-11-10T12:00:00Z");
function frame(minutes){
 return Array.from({length:30},(_,i)=>{
 const t=end-(30-i)*minutes*60000;
 return {datetime:new Date(t).toISOString(),open:100,high:101,low:99,close:100};
 });
}
const frames={M15:frame(15),H1:frame(60),H4:frame(240)};
let x=assess(frames,new Date(end).toISOString());
assert.equal(x.signal,"WAIT");assert.equal(x.executable,false);assert.equal(x.candidate,"NONE");
assert.equal(checkFrame(frame(15),15,end).ok,true);
const future=structuredClone(frames);future.M15.push({...future.M15.at(-1),datetime:new Date(end).toISOString()});
assert.match(assess(future,new Date(end).toISOString()).reason,/unclosed/);
const stale=structuredClone(frames);stale.H1.pop();stale.H1.pop();stale.H1.pop();
assert.match(assess(stale,new Date(end).toISOString()).reason,/stale/);
const broken=structuredClone(frames);broken.H4[5].close=200;
assert.match(assess(broken,new Date(end).toISOString()).reason,/invalid OHLC/);
const missing=structuredClone(frames);delete missing.H4;
assert.match(assess(missing,new Date(end).toISOString()).reason,/insufficient/);
assert.throws(()=>assess(frames,"invalid"),/Invalid asOf/);
console.log("PASS V3 MTF closed-bar alignment and fail-closed guards");
