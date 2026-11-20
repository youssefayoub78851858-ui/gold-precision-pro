"use strict";
// Browser-free mobile research UI mock tests. All quotes are GENERATED FIXTURES;
// the test never calls any provider, handles any API token, or places orders.
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const vm=require("node:vm");
const html=fs.readFileSync(path.join(__dirname,"biquote_mobile_direct_research.html"),"utf8");
const script=html.split("<script>")[1]?.split("</script>")[0];
assert.ok(script);
const W={M15:900000,H1:3600000,H4:14400000};
const NOW=Date.now();
function sample(tf,gap){
 const width=W[tf],end=Math.floor(NOW/width)*width-width,rows=[];
 for(let i=0;i<60;i++){
  if(gap&&tf==="H4"&&i===5)continue;
  const close=3000+(60-i)*0.8;
  rows.push({openTime:new Date(end-i*width).toISOString(),
    open:close-.25,high:close+.25,low:close-.35,close,isOpen:false});
 }
 return {symbol:"XAUUSD",interval:{M15:"15m",H1:"1h",H4:"4h"}[tf],bars:rows};
}
async function check({gap=false,stale=false,outage=false}={}){
 const elements={},calls=[];
 const el=id=>(elements[id]??={textContent:"—",disabled:false,addEventListener(){}});
 const document={hidden:false,getElementById:el,addEventListener(){}};
 async function fetch(url,opts){
  assert.equal(opts.credentials,"omit");assert.equal(opts.redirect,"error");
  assert.ok(url.startsWith("https://biquote.io/api/XAUUSD"));
  assert.equal(opts.method??"GET","GET");
  calls.push(url);
  if(outage)throw Error("fixture_outage");
  let data;
  if(url.includes("interval=")){
   const tf=url.includes("interval=15m")?"M15":url.includes("interval=1h")?"H1":"H4";
   data=sample(tf,gap);
  }else data={symbol:"XAUUSD",bid:3070,ask:3070.5,
    timestamp:new Date(NOW).toISOString(),stale,marketState:"open"};
  return {ok:true,json:async()=>data};
 }
 vm.runInNewContext(script,{document,fetch,AbortController,setTimeout,clearTimeout,
   setInterval(){return 1;},Date,Promise,Number,Math,Error,Object,Array,RegExp},{timeout:2000});
 await new Promise(resolve=>setTimeout(resolve,80));
 assert.equal(calls.length,4);
 assert.ok(el("state").textContent.startsWith("WAIT"));
 assert.equal(el("m15rsi").textContent,outage?"—":"100.0");
 assert.equal(el("m15ema").textContent,outage?"—":"3040.40");
 assert.equal(el("h4ema").textContent,(gap||outage)?"—":"3040.40");
 assert.equal(el("m15atr").textContent,outage?"—":"1.05");
 assert.equal(el("bid").textContent,(stale||outage)?"—":"3070.00");
 if(gap)assert.ok(el("h4coverage").textContent.includes("5 شمعة متجاورة"));
}
(async()=>{
 await check();await check({gap:true});await check({stale:true});await check({outage:true});
 console.log("4 safe offline UI cases: valid, gap, stale, outage. No broker or trades.");
})().catch(e=>{console.error(e);process.exitCode=1;});
