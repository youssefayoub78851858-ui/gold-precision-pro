"use strict";
// V3 research-only market structure. Every pivot is confirmed using right-side CLOSED bars.
function valid(c){return Array.isArray(c)&&c.every(x=>Number.isFinite(+x.open)&&Number.isFinite(+x.high)&&Number.isFinite(+x.low)&&Number.isFinite(+x.close)&&+x.low<=+x.open&&+x.open<=+x.high&&+x.low<=+x.close&&+x.close<=+x.high);}
function structure(candles,options={}){
 const left=options.left??2,right=options.right??2;
 if(!Number.isInteger(left)||!Number.isInteger(right)||left<1||right<1)throw Error("Invalid pivot windows");
 if(!valid(candles)||candles.length<left+right+3)return {signal:"WAIT",reason:"Insufficient valid closed candles",executable:false};
 const c=candles.map(x=>({open:+x.open,high:+x.high,low:+x.low,close:+x.close}));
 const highs=[],lows=[];
 for(let i=left;i+right<c.length;i++){
   if(c.slice(i-left,i).every(x=>c[i].high>x.high)&&c.slice(i+1,i+right+1).every(x=>c[i].high>=x.high))highs.push({index:i,confirmedAt:i+right,price:c[i].high});
   if(c.slice(i-left,i).every(x=>c[i].low<x.low)&&c.slice(i+1,i+right+1).every(x=>c[i].low<=x.low))lows.push({index:i,confirmedAt:i+right,price:c[i].low});
 }
 const last=c.length-1,prior=c[last-1],bar=c[last];
 const high=highs.filter(x=>x.confirmedAt<last).at(-1)||null;
 const low=lows.filter(x=>x.confirmedAt<last).at(-1)||null;
 const bosUp=!!high&&prior.close<=high.price&&bar.close>high.price;
 const bosDown=!!low&&prior.close>=low.price&&bar.close<low.price;
 const sweepHigh=!!high&&bar.high>high.price&&bar.close<high.price;
 const sweepLow=!!low&&bar.low<low.price&&bar.close>low.price;
 // A three-candle imbalance is known only at the third candle close.
 const fvgBull=c.length>=3&&c[last-2].high<bar.low?{lower:c[last-2].high,upper:bar.low}:null;
 const fvgBear=c.length>=3&&c[last-2].low>bar.high?{lower:bar.high,upper:c[last-2].low}:null;
 return {signal:"WAIT",executable:false,high,low,bosUp,bosDown,sweepHigh,sweepLow,fvgBull,fvgBear,
   reason:"Market-structure observations only; multi-timeframe, risk and external-feed gates not yet implemented"};
}
module.exports={structure};
