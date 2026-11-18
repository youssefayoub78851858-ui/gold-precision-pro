"use strict";
/* Gold Precision — authenticated BiQuote sampled forming-candle overlay.
 * In-memory, read-only, not a complete exchange/broker OHLC candle.
 * No provider calls, storage, orders, indicators, or paper execution.
 * A new quote can change a partial bar; ONLY provider-closed source bars
 * are admitted to the separate technical engine.
 */
(function(root,factory){
 const api=factory();
 if(typeof module==="object"&&module.exports)module.exports=api;
 if(root)root.GoldBiQuoteCandlePreview=api;
})(typeof window!=="undefined"?window:null,function(){
 const WIDTH=Object.freeze({M15:900000,H1:3600000,H4:14400000});
 const FRAMES=Object.freeze(["M15","H1","H4"]);
 const MAX_AGE_MS=30000;
 const finitePositive=x=>typeof x==="number"&&Number.isFinite(x)&&x>0;
 const isoMs=s=>typeof s==="string"&&/^20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,3})?Z$/.test(s)
   ?Date.parse(s):NaN;
 function clear(){return {M15:null,H1:null,H4:null};}
 function update(previous,packet,closed,clientNowMs){
   const empty=clear();
   if(!packet||packet.rawQuoteShown!==true||
      packet.privateChartReadOnly!==true||
      packet.privateChartDataBasis!=="MID_WITH_POSSIBLE_BID_SEED"||
      packet.signal!=="WAIT"||packet.executable!==false||
      packet.researchEligible!==false||packet.paperOrdersAllowed!==false||
      !["OBSERVED_READONLY_UNVERIFIED","WAIT_CROSS_FRAME_GAPS"].includes(packet.status)||
      !closed||typeof closed!=="object"||
      !finitePositive(packet.bid)||!finitePositive(packet.ask)||packet.ask<packet.bid||
      typeof packet.quoteAgeSeconds!=="number"||
      !Number.isFinite(packet.quoteAgeSeconds)||
      packet.quoteAgeSeconds<0||packet.quoteAgeSeconds>30)
      return empty;
   const tick=isoMs(packet.quoteUTC),observed=isoMs(packet.observedUTC);
   if(!Number.isFinite(tick)||!Number.isFinite(observed)||
      observed<tick||observed-tick>MAX_AGE_MS||
      packet.quoteAgeSeconds*1000+1700<observed-tick||
      !Number.isFinite(clientNowMs)||clientNowMs<tick-5000||
      clientNowMs-observed>MAX_AGE_MS) return empty;
   const mid=(packet.bid+packet.ask)/2;
   if(!finitePositive(mid))return empty;
   const next={};
   for(const tf of FRAMES){
     const candles=closed[tf],width=WIDTH[tf];
     if(!Array.isArray(candles)||!candles.length){next[tf]=null;continue;}
     const last=candles.at(-1);
     const bucketStart=Math.floor(tick/width)*width;
     // Never overlay an in-progress price on a closed or not-yet-closed
     // source bucket. A late quote from prior hour is not the new H1.
     if(!last||!Number.isFinite(last.t)||
        last.t+width>bucketStart||tick>=bucketStart+width||
        bucketStart+width<=clientNowMs-5000){
       next[tf]=null;continue;
     }
     const old=previous?.[tf];
     if(old&&old.t>bucketStart){next[tf]=null;continue;}
     if(old&&old.t===bucketStart){
       if(tick<old.lastTickMs){next[tf]=null;continue;}
       if(tick===old.lastTickMs){
         if(Math.abs(mid-old.close)>1e-8){next[tf]=null;continue;}
         next[tf]={...old};continue;
       }
       next[tf]={...old,high:Math.max(old.high,mid),
         low:Math.min(old.low,mid),close:mid,
         lastTickMs:tick,samples:old.samples+1};
     }else{
       // Opening value is FIRST OBSERVED quote in this hour, not the
       // real broker's hour-open. Do not invent intervening ticks.
       next[tf]={t:bucketStart,open:mid,high:mid,low:mid,close:mid,
         firstTickMs:tick,lastTickMs:tick,samples:1,partial:true};
     }
   }
   return next;
 }
 return Object.freeze({WIDTH,clear,update});
});
