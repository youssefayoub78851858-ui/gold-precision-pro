"use strict";
const assert=require("node:assert/strict");
const api=require("./biquote_mobile_readonly");

const NOW=Date.parse("2026-11-16T20:00:00.000Z");
const STEP=900000;
function unit(t){
 const i=Math.floor(t/STEP)%31;
 const p=3840+(i/10);
 return {open:p,high:p+1,low:p-1,close:p+0.4};
}
function candle(t,tf){
 const k={M15:1,H1:4,H4:16}[tf],pieces=Array.from({length:k},(_,i)=>unit(t+i*STEP));
 return {openTime:new Date(t).toISOString(),isOpen:false,
   open:pieces[0].open,high:Math.max(...pieces.map(x=>x.high)),
   low:Math.min(...pieces.map(x=>x.low)),close:pieces.at(-1).close,
   tickVolume:12,volume:12};
}
function fixture(tf,n=65){
 const widths={M15:900000,H1:3600000,H4:14400000};
 const names={M15:"15m",H1:"1h",H4:"4h"};
 const duration=widths[tf],end=Math.floor(NOW/duration)*duration;
 return {symbol:"XAUUSD",interval:names[tf],
   bars:Array.from({length:n},(_,i)=>candle(end-(i+1)*duration,tf))};
}
function packet(){
 return {
  quote:{symbol:"XAUUSD",timestamp:new Date(NOW-1500).toISOString(),
    bid:3840,ask:3840.22,mid:3840.11,spread:0.22,
    marketState:"open",stale:false},
  M15:fixture("M15"),H1:fixture("H1"),H4:fixture("H4")
 };
}
function fake(packets){
 const urls=Object.values(api.URLS),keys=["quote","M15","H1","H4"],calls=[];
 return {calls,fetch:async(url,opt)=>{
   calls.push({url,opt});
   const key=keys[urls.indexOf(url)];
   assert.ok(key,"Unexpected endpoint "+url);
   assert.equal(opt.method,"GET");assert.equal(opt.redirect,"error");
   assert.equal(opt.credentials,"omit");assert.equal(opt.cache,"no-store");
   return {status:200,headers:{get(){return null}},
     async text(){return JSON.stringify(packets[key]);}};
 }};
}
function secure(body){
 assert.equal(body.signal,"WAIT");
 assert.equal(body.executable,false);
 assert.equal(body.researchEligible,false);
 assert.equal(body.tradePlanExecutable,false);
 assert.equal(body.paperOrdersAllowed,false);
 assert.equal(body.orderEndpointsCalled,false);
}
async function main(){
 api.resetForTests();
 const first=fake(packet());
 const result=await api.snapshot({fetchFn:first.fetch,nowMs:()=>NOW});
 assert.equal(result.httpStatus,200);
 secure(result.body);
 assert.equal(result.body.rawQuoteShown,false);
 assert.equal(result.body.bid,undefined);
 assert.equal(result.body.ask,undefined);
 assert.equal(result.body.frameSummary.M15.closedCount,65);
 assert.equal(result.body.frameSummary.H1.closedCount,65);
 assert.equal(result.body.frameSummary.H4.closedCount,65);
 assert.ok(result.body.crossFrameComparisons.H1.completeMatches>=10);
 assert.ok(result.body.crossFrameComparisons.H4.completeMatches>=2);
 assert.equal(result.body.crossFrameComparisons.H4.completeMismatches,0);
 assert.equal(first.calls.length,4);
 assert.equal(first.calls.some(x=>x.opt.headers.Authorization),false);
 assert.equal(result.body.blockerCodes.includes("GC_DXY_US_YIELDS_ORDERFLOW_AND_NEWS_NOT_COMPLETE"),true);
 // Private viewer verification is independent from upstream vendor quote.
 const auth="Bearer "+("a".repeat(50));
 let checked=0;
 const privateData=await api.snapshot({fetchFn:first.fetch,nowMs:()=>NOW+5000,
   authorization:auth,verifyViewer:async x=>{assert.equal(x,auth);checked++;return true;}});
 assert.equal(privateData.httpStatus,200);secure(privateData.body);
 assert.equal(privateData.body.bid,3840);
 assert.equal(privateData.body.ask,3840.22);
 assert.equal(privateData.body.rawQuoteShown,true);
 assert.equal(checked,1);
 assert.equal(first.calls.length,4,"Cache avoids redundant rapid requests");
 const denied=await api.snapshot({fetchFn:first.fetch,nowMs:()=>NOW+7000,
   authorization:auth,verifyViewer:async()=>false});
 assert.equal(denied.body.rawQuoteShown,false);
 assert.equal(denied.body.bid,undefined);
 const invalid=await api.snapshot({fetchFn:first.fetch,nowMs:()=>NOW+8000,
   authorization:"Bearer bad",verifyViewer:async()=>{throw Error("must not verify");}});
 assert.equal(invalid.body.rawQuoteShown,false);
 // Expired cached quote must not claim the initial observation remains fresh.
 api.resetForTests();
 let current=packet();current.quote.timestamp=new Date(NOW-61000).toISOString();
 const old=await api.snapshot({fetchFn:fake(current).fetch,nowMs:()=>NOW});
 assert.equal(old.httpStatus,503);secure(old.body);
 api.resetForTests();
 const crossed=packet();crossed.quote.ask=crossed.quote.bid-0.1;
 const no=await api.snapshot({fetchFn:fake(crossed).fetch,nowMs:()=>NOW});
 assert.equal(no.httpStatus,503);secure(no.body);
 api.resetForTests();
 const openBar=packet();
 openBar.M15.bars[4].isOpen=true;
 const bad=await api.snapshot({fetchFn:fake(openBar).fetch,nowMs:()=>NOW});
 assert.equal(bad.httpStatus,503);secure(bad.body);
 api.resetForTests();
 const missing=packet();missing.H4.bars=[];
 const badHistory=await api.snapshot({fetchFn:fake(missing).fetch,nowMs:()=>NOW});
 assert.equal(badHistory.httpStatus,503);secure(badHistory.body);
 api.resetForTests();
 const incorrect=packet();incorrect.H1.bars[0].close+=0.1;
 const mismatch=await api.snapshot({fetchFn:fake(incorrect).fetch,nowMs:()=>NOW});
 assert.equal(mismatch.httpStatus,200);secure(mismatch.body);
 assert.ok(["WAIT_CROSS_FRAME_GAPS","OBSERVED_READONLY_UNVERIFIED"].includes(mismatch.body.status));
 // Response never contains historical OHLC raw rows, even when authorized.
 assert.equal(JSON.stringify(privateData.body).includes('"bars"'),false);
 console.log("PASS BiQuote real-formatted XAUUSD derived M15/H1/H4 telemetry; no raw candles, read-only WAIT, private quote gate");
}
main().catch(e=>{console.error(e);process.exitCode=1;});
