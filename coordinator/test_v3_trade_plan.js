"use strict";
const assert=require("node:assert/strict");
const {plan}=require("./v3_trade_plan");
const {assess}=require("./v3_multitimeframe");
const end=Date.parse("2026-11-10T12:00:00Z");
function frame(m){return Array.from({length:30},(_,i)=>({datetime:new Date(end-(30-i)*m*60000).toISOString(),open:100,high:101,low:99,close:100}));}
const f={M15:frame(15),H1:frame(60),H4:frame(240)};
let p=plan(f,new Date(end).toISOString(),{spread:0.4});
assert.equal(p.signal,"WAIT");assert.equal(p.executable,false);assert.equal(p.candidate,"NONE");
assert.equal(plan(f,new Date(end).toISOString(),{spread:NaN}).executable,false);
const stale=structuredClone(f);stale.H4.pop();stale.H4.pop();
assert.equal(plan(stale,new Date(end).toISOString(),{spread:0.4}).signal,"WAIT");
assert.equal(assess(f,new Date(end).toISOString()).signal,"WAIT");
console.log("PASS research-only plan WAIT and invalid-feed guards");
