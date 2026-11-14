/* Gold Precision Pro Ultimate: offline paper-session core.
 * This is NOT a live broker adapter, signal generator or licensed data gateway.
 */
(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  if(root)root.GoldPaperCore=api;
})(typeof window!=='undefined'?window:null,function(){
'use strict';
const MS={M15:900000,H1:3600000,H4:14400000};
const SIDES=['bid','ask'],OHLC=['open','high','low','close'];
const ORIGINS=['SYNTHETIC_TEST_ONLY','RECORDED_UNVERIFIED'];
const COSTS=Object.freeze({lot:.01,valuePerPoint:100,slippage:0.05,commissionPerLotRoundTrip:7,maxRiskFraction:.005,maxDailyLossFraction:.02});
function must(ok,code){if(!ok)throw Error(code);}
function num(n){return typeof n==='number'&&Number.isFinite(n);}
function time(s){must(typeof s==='string'&&/^20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,3})?Z$/.test(s),'UTC_Z_TIMESTAMP_REQUIRED');const n=Date.parse(s);must(Number.isFinite(n)&&new Date(n).toISOString().slice(0,19)===s.slice(0,19),'INVALID_TIMESTAMP');return n;}
function validate(dataset,nowMs=Date.now()){
  must(dataset&&typeof dataset==='object'&&!Array.isArray(dataset),'DATASET_OBJECT_REQUIRED');
  must(dataset.symbol==='XAUUSD'&&ORIGINS.includes(dataset.dataOrigin),'EXPLICIT_XAUUSD_ORIGIN_REQUIRED');
  must(typeof dataset.source==='string'&&dataset.source.trim().length>=3&&dataset.source.length<=160,'DATASET_SOURCE_REQUIRED');
  const rows=dataset.bars;
  must(Array.isArray(rows)&&rows.length>=48&&rows.length<=2400,'M15_BAR_COUNT_OUT_OF_RANGE');
  let prev=-1;const bars=[];
  for(const r of rows){
    const t=time(r?.time);
    must(t%MS.M15===0&&t+MS.M15<=nowMs,'BAR_FORMING_FUTURE_OR_UNALIGNED');
    if(prev>=0)must(t-prev===MS.M15,'MISSING_DUPLICATE_OR_UNVERIFIED_SESSION_GAP');
    const sides={};
    for(const side of SIDES){
      const p=r?.[side];must(p&&typeof p==='object'&&!Array.isArray(p),'SEPARATE_BID_ASK_REQUIRED');
      const values={};for(const field of OHLC){const v=p[field];must(num(v)&&v>0,'NONFINITE_OR_INVALID_PRICE');values[field]=v;}
      must(values.low<=Math.min(values.open,values.close)&&values.high>=Math.max(values.open,values.close)&&values.high>=values.low,'INVALID_OHLC_EXTREMA');
      sides[side]=values;
    }
    for(const field of OHLC)must(sides.ask[field]>=sides.bid[field],'CROSSED_BID_ASK');
    bars.push({time:new Date(t).toISOString(),bid:sides.bid,ask:sides.ask});prev=t;
  }
  return {symbol:'XAUUSD',dataOrigin:dataset.dataOrigin,source:dataset.source.trim(),bars};
}
function group(bars,tf){
  if(tf==='M15')return bars;
  must(tf==='H1'||tf==='H4','INVALID_TIMEFRAME');
  const step=MS[tf]/MS.M15,result=[];
  for(let i=0;i+step<=bars.length;i++){
    const start=Date.parse(bars[i].time);
    if(start%MS[tf]!==0)continue;
    const section=bars.slice(i,i+step);
    if(Date.parse(section.at(-1).time)!==start+(step-1)*MS.M15)continue;
    const item={time:bars[i].time};
    for(const side of SIDES){const ss=section.map(x=>x[side]);item[side]={open:ss[0].open,high:Math.max(...ss.map(x=>x.high)),low:Math.min(...ss.map(x=>x.low)),close:ss.at(-1).close};}
    result.push(item);i+=step-1;
  }
  return result;
}
function defaultSession(dataset){return {version:1,dataset,cursor:Math.min(63,dataset.bars.length-1),initialBalance:10000,balance:10000,peak:10000,position:null,trades:[],lastEntryAt:null,locked:false};}
function checkedSession(raw){
  must(raw?.version===1,'INVALID_SESSION_VERSION');
  const dataset=validate(raw.dataset);
  must(Number.isInteger(raw.cursor)&&raw.cursor>=0&&raw.cursor<dataset.bars.length,'INVALID_CURSOR');
  must(num(raw.initialBalance)&&raw.initialBalance>0&&num(raw.balance)&&raw.balance>0&&num(raw.peak)&&raw.peak>=raw.balance,'INVALID_PAPER_BALANCE');
  must(Array.isArray(raw.trades)&&raw.trades.length<=2400,'INVALID_TRADE_LOG');
  must(raw.position===null||typeof raw.position==='object','INVALID_POSITION');
  return {...raw,dataset};
}
function clamp(n){return Math.round(n*100)/100;}
function quote(state){const b=state.dataset.bars[state.cursor];return {bid:b.bid.close,ask:b.ask.close,time:b.time,closeUTC:new Date(Date.parse(b.time)+MS.M15).toISOString()};}
function lossToday(s){const day=quote(s).closeUTC.slice(0,10);return s.trades.filter(t=>t.closedUTC.slice(0,10)===day&&t.net<0).reduce((a,t)=>a-t.net,0);}
function open(s,side,stop,tp){
  must(s&&s.dataset&&s.position===null&&!s.locked,'POSITION_OR_KILL_SWITCH_ACTIVE');
  must(['BUY','SELL'].includes(side),'INVALID_SIDE');
  must(s.cursor>=14&&s.cursor<s.dataset.bars.length-1,'REPLAY_POSITION_OUTSIDE_AVAILABLE_BARS');
  must(Array.isArray(tp)&&tp.length===3&&tp.every(num)&&num(stop),'STOP_AND_THREE_TARGETS_REQUIRED');
  const q=quote(s),entry=side==='BUY'?q.ask+COSTS.slippage:q.bid-COSTS.slippage;
  const sign=side==='BUY'?1:-1;
  must((entry-stop)*sign>0&&tp.every(x=>(x-entry)*sign>0)&&
    (tp[1]-tp[0])*sign>0&&(tp[2]-tp[1])*sign>0,'INVALID_STOP_TARGET_GEOMETRY');
  must(s.lastEntryAt!==s.cursor,'DUPLICATE_ENTRY_ON_SAME_BAR');
  const risk=((entry-stop)*sign+2*COSTS.slippage)*COSTS.lot*COSTS.valuePerPoint+COSTS.commissionPerLotRoundTrip*COSTS.lot;
  must(risk<=s.balance*COSTS.maxRiskFraction+1e-8,'PAPER_RISK_LIMIT_EXCEEDED');
  must(lossToday(s)<s.balance*COSTS.maxDailyLossFraction,'PAPER_DAILY_LOSS_LIMIT');
  s.position={id:'P'+(s.trades.length+1)+'-'+s.cursor,side,entry:clamp(entry),stop,tp:tp.map(clamp),lots:COSTS.lot,risk:clamp(risk),openedUTC:q.closeUTC,openedIndex:s.cursor};
  s.lastEntryAt=s.cursor;
  return s.position;
}
function close(s,reason='MANUAL',trigger=null){
  must(s.position!==null,'NO_OPEN_POSITION');
  const p=s.position,q=quote(s);
  const sign=p.side==='BUY'?1:-1;
  const exit=(trigger===null?(sign===1?q.bid:q.ask):trigger)-sign*COSTS.slippage;
  const gross=(exit-p.entry)*sign*p.lots*COSTS.valuePerPoint;
  const commission=p.lots*COSTS.commissionPerLotRoundTrip;
  const net=gross-commission;
  const t={...p,exit:clamp(exit),gross:clamp(gross),commission:clamp(commission),net:clamp(net),closedUTC:q.closeUTC,reason};
  s.balance=clamp(s.balance+net);s.peak=Math.max(s.peak,s.balance);s.trades.push(t);s.position=null;
  if(s.balance<=0)s.locked=true;
  return t;
}
function advance(s){
  must(s.cursor+1<s.dataset.bars.length,'REPLAY_END');
  s.cursor++;
  const p=s.position;
  if(p){
    const b=s.dataset.bars[s.cursor],buy=p.side==='BUY';
    const hitStop=buy?b.bid.low<=p.stop:b.ask.high>=p.stop;
    const hitTarget=buy?b.bid.high>=p.tp[2]:b.ask.low<=p.tp[2];
    if(hitStop)close(s,hitTarget?'STOP_FIRST_BOTH_TOUCHED':'STOP',p.stop);
    else if(hitTarget)close(s,'TP3',p.tp[2]);
  }
  return s;
}
function stats(s){
  const trades=s.trades,wins=trades.filter(x=>x.net>0),total=trades.reduce((a,x)=>a+x.net,0);
  let bal=s.initialBalance,peak=bal,dd=0;
  for(const t of trades){bal+=t.net;peak=Math.max(peak,bal);dd=Math.max(dd,peak>0?(peak-bal)/peak*100:0);}
  return {closed:trades.length,winRatePct:trades.length?clamp(wins.length/trades.length*100):0,
    net:clamp(total),balance:s.balance,maxDrawdownPct:clamp(dd),open:s.position?1:0,
    profitFactor:(()=>{const profits=trades.filter(t=>t.net>0).reduce((a,t)=>a+t.net,0),losses=-trades.filter(t=>t.net<0).reduce((a,t)=>a+t.net,0);return losses?clamp(profits/losses):null;})()};
}
// Illustrative fixture only, never returned by a provider or AI signal engine.
function sample(){
  const start=Date.parse('2026-11-09T00:00:00Z'),bars=[];
  let prev=4000;
  for(let i=0;i<512;i++){
    const delta=Math.sin(i*.28)*.7+Math.cos(i*.069)*.35;
    const next=prev+delta,bid={open:clamp(prev),high:clamp(Math.max(prev,next)+.27),low:clamp(Math.min(prev,next)-.27),close:clamp(next)};
    const ask=Object.fromEntries(Object.entries(bid).map(([k,v])=>[k,clamp(v+.36)]));
    bars.push({time:new Date(start+i*MS.M15).toISOString(),bid,ask});prev=next;
  }
  return validate({symbol:'XAUUSD',source:'GENERATED_OFFLINE_DETERMINISTIC_TEST',dataOrigin:'SYNTHETIC_TEST_ONLY',bars});
}
return {MS,COSTS,validate,group,defaultSession,checkedSession,quote,open,close,advance,stats,sample};
});
