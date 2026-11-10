"use strict";
// V3 research-only M15/H1/H4 alignment; never sends orders.
const {structure}=require("./v3_market_structure");
const MIN={M15:15,H1:60,H4:240};
function parseTime(x){const t=Date.parse(x.datetime??x.timestamp??"");return Number.isFinite(t)?t:NaN;}
function checkFrame(rows,minutes,asOf){
 if(!Array.isArray(rows)||rows.length<12)return {ok:false,reason:"insufficient candles"};
 let prev=-Infinity;
 for(const x of rows){
  const t=parseTime(x);
  if(!Number.isFinite(t)||t<=prev||t% (minutes*60000)!==0||t+minutes*60000>asOf)return {ok:false,reason:"timestamp, alignment or unclosed candle"};
  for(const k of ["open","high","low","close"])if(!Number.isFinite(x[k])||x[k]<=0)return {ok:false,reason:"invalid OHLC"};
  if(x.low>Math.min(x.open,x.close)||x.high<Math.max(x.open,x.close))return {ok:false,reason:"invalid OHLC"};
  prev=t;
 }
 if(asOf-(prev+minutes*60000)>minutes*60000)return {ok:false,reason:"stale candles"};
 return {ok:true};
}
function assess(frames,asOfISO){
 const asOf=Date.parse(asOfISO);
 if(!Number.isFinite(asOf))throw Error("Invalid asOf");
 const observations={};
 for(const [name,minutes] of Object.entries(MIN)){
  const rows=frames?.[name];
  const status=checkFrame(rows,minutes,asOf);
  if(!status.ok)return {signal:"WAIT",executable:false,reason:name+": "+status.reason};
  observations[name]=structure(rows);
 }
 const {M15,H1,H4}=observations;
 // Require directional agreement; risk, event, spread and feed checks still unavailable.
 const alignedUp=M15.bosUp&&H1.bosUp&&H4.bosUp;
 const alignedDown=M15.bosDown&&H1.bosDown&&H4.bosDown;
 return {signal:"WAIT",executable:false,observations,
  candidate:alignedUp?"BUY":alignedDown?"SELL":"NONE",
  reason:"Research only: broker spread, event risk, volatility and position sizing gates not validated"};
}
module.exports={assess,checkFrame};
