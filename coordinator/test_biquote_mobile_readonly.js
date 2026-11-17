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
 assert.equal(result.body.privateChart,undefined);
 assert.equal(result.body.rawPrivateChart,undefined);
 assert.equal(result.body.privateStructure,undefined);
 assert.equal(result.body.rawPrivateStructure,undefined);
 assert.equal(result.body.privateChartReadOnly,undefined);
 assert.equal(JSON.stringify(result.body).includes('"bars"'),false);
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
 assert.equal(privateData.body.privateChartReadOnly,true);
 assert.equal(privateData.body.privateStructure.mode,"PRIVATE_READONLY_TECHNICAL_OBSERVATIONS");
 assert.equal(privateData.body.privateStructure.signal,"WAIT");
 assert.equal(privateData.body.privateStructure.executable,false);
 assert.equal(privateData.body.privateStructure.tradeEligible,false);
 assert.equal(privateData.body.privateStructure.newsAndMacroIncluded,false);
 assert.equal(privateData.body.privateStructure.orderFlowIncluded,false);
 for(const tf of ["M15","H1","H4"]){
   const analysis=privateData.body.privateStructure.frames[tf];
   assert.equal(analysis.signal,"WAIT");
   assert.equal(analysis.executable,false);
   assert.equal(analysis.tradeEligible,false);
   assert.equal(analysis.state,"OBSERVATION_ONLY");
   assert.ok(analysis.ema20>0&&analysis.atr14>0);
   assert.ok(analysis.recentRangeHigh20>=analysis.recentRangeLow20);
 }
 assert.equal(privateData.body.privateChartDataBasis,"MID_WITH_POSSIBLE_BID_SEED");
 for(const tf of ["M15","H1","H4"]){
   const rows=privateData.body.privateChart[tf];
   assert.equal(rows.length,48);
   for(let i=0;i<rows.length;i++){
     const row=rows[i];
     assert.deepEqual(Object.keys(row).sort(),["close","high","low","open","time"]);
     assert.match(row.time,/Z$/);
     assert.ok(row.high>=Math.max(row.open,row.close));
     assert.ok(row.low<=Math.min(row.open,row.close));
     if(i)assert.ok(Date.parse(row.time)>Date.parse(rows[i-1].time));
     assert.ok(Date.parse(row.time)+{M15:900000,H1:3600000,H4:14400000}[tf]<=NOW);
   }
 }
 assert.equal(checked,1);
 assert.equal(first.calls.length,4,"Cache avoids redundant rapid requests");

 const denied=await api.snapshot({fetchFn:first.fetch,nowMs:()=>NOW+7000,
   authorization:auth,verifyViewer:async()=>false});
 assert.equal(denied.body.rawQuoteShown,false);
 assert.equal(denied.body.bid,undefined);
 assert.equal(denied.body.privateChart,undefined);
 assert.equal(denied.body.privateStructure,undefined);
 const invalid=await api.snapshot({fetchFn:first.fetch,nowMs:()=>NOW+8000,
   authorization:"Bearer bad",verifyViewer:async()=>{throw Error("must not verify");}});
 assert.equal(invalid.body.rawQuoteShown,false);
 assert.equal(invalid.body.privateChart,undefined);
 assert.equal(invalid.body.privateStructure,undefined);
 // Regression: provider quote can be fresh for 30 seconds, but the
 // old 90-second cache silently caused 503 between seconds 30 and 90.
 // Refresh with a newly timestamped quote BEFORE the validation limit.
 const renewedPacket=packet();
 renewedPacket.quote.timestamp=new Date(NOW+23500).toISOString();
 const renewedFetcher=fake(renewedPacket);
 const renewed=await api.snapshot({fetchFn:renewedFetcher.fetch,nowMs:()=>NOW+25000});
 assert.equal(renewed.httpStatus,200,"Expired quote cache must refetch");
 secure(renewed.body);
 assert.ok(renewed.body.quoteAgeSeconds<=2,renewed.body.quoteAgeSeconds);
 assert.equal(renewedFetcher.calls.length,4,"4 new GETs, never background poll");
 assert.equal(renewed.body.rawQuoteShown,false);
 assert.equal(renewed.body.bid,undefined);
 assert.equal(renewed.body.privateChart,undefined);
 assert.equal(renewed.body.privateStructure,undefined);
 // At +33s (previously an inevitable error), refreshed response stays valid.
 const recovered=await api.snapshot({fetchFn:async()=>{throw Error("Should reuse recent quote")},
   nowMs:()=>NOW+33000});
 assert.equal(recovered.httpStatus,200);
 secure(recovered.body);
 assert.equal(recovered.body.rawQuoteShown,false);

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

 // BiQuote H1/H4 history can straddle a daily/weekend gap, but our
 // read-only viewer must still show strictly within-segment observations
 // from 7+ CLOSED bars, and NEVER invent EMA20 or ATR14 from the gap.
 api.resetForTests();
 const withGaps=packet();
 withGaps.H1.bars.splice(10,1);
 withGaps.H4.bars.splice(10,1);
 const guest=await api.snapshot({fetchFn:fake(withGaps).fetch,nowMs:()=>NOW});
 assert.equal(guest.httpStatus,200);secure(guest.body);
 assert.equal(guest.body.privateChart,undefined);
 assert.equal(guest.body.privateStructure,undefined);
 const accepted=await api.snapshot({nowMs:()=>NOW+500,
   fetchFn:async()=>{throw Error("unexpected fetch")},
   authorization:auth,verifyViewer:async()=>true});
 assert.equal(accepted.httpStatus,200);secure(accepted.body);
 assert.equal(accepted.body.privateStructure.sessionCalendarVerified,false);
 for(const tf of ["H1","H4"]){
   const f=accepted.body.privateStructure.frames[tf];
   assert.equal(f.state,"PARTIAL_OBSERVATION_UNVERIFIED_SESSION");
   assert.equal(f.contiguousBars,10);
   assert.equal(f.unclassifiedGapsInChart,1);
   assert.equal(f.referenceOnlyGapAudit.sessionCalendarVerified,false);
   assert.equal(f.referenceOnlyGapAudit.brokerCalendarVerified,false);
   assert.equal(f.referenceOnlyGapAudit.bridgeBarsAllowed,false);
   assert.equal(f.referenceOnlyGapAudit.gapCount,1);
   assert.equal(f.ema20,null);
   assert.equal(f.atr14,null);
   assert.ok(f.recentRangeHigh20>=f.recentRangeLow20);
   assert.equal(f.validForEntry,false);
   assert.equal(f.executable,false);
   assert.equal(f.paperOrdersAllowed,false);
 }
 assert.equal(accepted.body.privateStructure.frames.M15.state,"OBSERVATION_ONLY");

 // Explicit provider market closure: no fake live trend and no historical
 // requests. A market-closed state is not labeled as an HTTP outage.
 api.resetForTests();
 const marketClosed=packet();marketClosed.quote.marketState="closed";
 const closedFetcher=fake(marketClosed);
 const marketResult=await api.snapshot({fetchFn:closedFetcher.fetch,nowMs:()=>NOW});
 assert.equal(marketResult.httpStatus,503);secure(marketResult.body);
 assert.deepEqual(marketResult.body.blockerCodes,["PROVIDER_REPORTED_CLOSED"]);
 assert.equal(marketResult.body.rawQuoteShown,false);
 assert.deepEqual(Object.keys(marketResult.body.frameSummary),[]);
 assert.equal(closedFetcher.calls.length,1,"No OHLC requests when reported closed");

 // Current quote with M15 history that ended hours ago must fail closed,
 // rather than generating an apparently current EMA trend from stale bars.
 api.resetForTests();
 const stale=packet();
 for(const row of stale.M15.bars)row.openTime=
   new Date(Date.parse(row.openTime)-6*3600000).toISOString();
 const staleResult=await api.snapshot({fetchFn:fake(stale).fetch,nowMs:()=>NOW});
 assert.equal(staleResult.httpStatus,503);secure(staleResult.body);
 assert.deepEqual(staleResult.body.blockerCodes,["CLOSED_CANDLE_STALE"]);
 assert.equal(staleResult.body.frameSummary.M15,undefined);

 // Unreachable quote cannot be misrepresented as a confirmed closure.
 api.resetForTests();
 const unavailable=await api.snapshot({fetchFn:async()=>{throw Error("network down")},nowMs:()=>NOW});
 assert.equal(unavailable.httpStatus,503);secure(unavailable.body);
 assert.deepEqual(unavailable.body.blockerCodes,["PUBLIC_FEED_INVALID_STALE_OR_UNAVAILABLE"]);

 // Response never contains historical OHLC raw rows, even when authorized.
 assert.equal(JSON.stringify(privateData.body).includes('"bars"'),false);
 assert.equal(JSON.stringify(privateData.body).includes('"rawPrivateChart"'),false);
 assert.equal(JSON.stringify(privateData.body).includes('"rawPrivateStructure"'),false);
 console.log("PASS BiQuote XAUUSD: anonymous no raw OHLC, authorized read-only 48 closed bars per frame, strict WAIT and no paper engine integration");
}
main().catch(e=>{console.error(e);process.exitCode=1;});
