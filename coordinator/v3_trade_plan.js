"use strict";
// Research-only trade plan. Not executable. No provider access or order placement.
const {assess}=require("./v3_multitimeframe");
function plan(frames,asOfISO,options={}){
 const a=assess(frames,asOfISO);
 const base={signal:"WAIT",executable:false,candidate:a.candidate||"NONE",reason:a.reason};
 if(a.candidate!=="BUY"&&a.candidate!=="SELL")return base;
 const rows=frames.M15, last=rows.at(-1);
 const n=options.lookback??8,rr=options.rr??2,spread=options.spread;
 if(!Number.isInteger(n)||n<3||n>50||rows.length<n+1)return {...base,reason:"Invalid stop lookback"};
 if(!Number.isFinite(rr)||rr<1.5||rr>4)return {...base,reason:"Invalid reward/risk"};
 if(!Number.isFinite(spread)||spread<0)return {...base,reason:"Broker spread unavailable or invalid"};
 const entry=last.close;
 const recent=rows.slice(-n);
 const stop=a.candidate==="BUY"?Math.min(...recent.map(x=>x.low)):Math.max(...recent.map(x=>x.high));
 if(a.candidate==="BUY"?stop>=entry:stop<=entry)return {...base,reason:"Stop is on wrong side of entry"};
 const risk=Math.abs(entry-stop);
 if(!Number.isFinite(risk)||risk<=0||spread>=risk/3)return {...base,reason:"Stop distance too small for spread"};
 const tp=a.candidate==="BUY"?entry+rr*risk:entry-rr*risk;
 if(tp<=0||stop<=0)return {...base,reason:"Invalid price geometry"};
 return {...base,entry,stop,target:tp,stopDistance:risk,rewardRisk:rr,spread,reason:"Research candidate only; fees, slippage, broker feed, event risk and position sizing unverified"};
}
module.exports={plan};
