'use strict';
// Intentionally accepts synthetic-only local replay candles, not live market data.
// This routes the existing V3 Ultimate research engine into a fail-closed terminal.
const paper=require('../paper-terminal-core');
const {evaluate}=require('./ultimate_v2');
function number(n){return Number.isFinite(n)?Math.round(n*100)/100:null;}
function ema(values,period){if(values.length<period)return null;let x=values.slice(0,period).reduce((a,b)=>a+b,0)/period;const a=2/(period+1);for(let i=period;i<values.length;i++)x=values[i]*a+x*(1-a);return number(x);}
function rsi(closes,period=14){if(closes.length<=period)return null;let gains=0,losses=0;for(let i=1;i<=period;i++){let d=closes[i]-closes[i-1];gains+=Math.max(d,0);losses+=Math.max(-d,0);}gains/=period;losses/=period;for(let i=period+1;i<closes.length;i++){let d=closes[i]-closes[i-1];gains=(gains*(period-1)+Math.max(d,0))/period;losses=(losses*(period-1)+Math.max(-d,0))/period;}return number(losses?100-100/(1+gains/losses):100);}
function atr(rows,period=14){if(rows.length<period+1)return null;let sum=0;for(let i=rows.length-period;i<rows.length;i++){const a=rows[i],prior=rows[i-1];sum+=Math.max(a.high-a.low,Math.abs(a.high-prior.close),Math.abs(a.low-prior.close));}return number(sum/period);}
function inspect(payload){
 if(!payload||payload.dataOrigin!=='SYNTHETIC_TEST_ONLY'||payload.symbol!=='XAUUSD'||payload.source!=='GENERATED_OFFLINE_DETERMINISTIC_TEST'||payload.researchApproved===true)
  throw Error('ONLY_SYNTHETIC_OFFLINE_REPLAY_ACCEPTED');
 const dataset=paper.validate(payload);
 const asOfUTC=new Date(Date.parse(dataset.bars.at(-1).time)+paper.MS.M15).toISOString();
 const frames={};
 for(const tf of ['M15','H1','H4'])frames[tf]=paper.group(dataset.bars,tf).map(x=>({datetime:x.time,...x.bid}));
 const bid=frames.M15,closes=bid.map(x=>x.close);
 const input={asOfUTC,frames,feeds:{},spread:dataset.bars.at(-1).ask.close-dataset.bars.at(-1).bid.close,
   risk:{equity:10000,dailyLoss:0,riskFraction:.005,dailyLossFraction:.02,
    valuePerPoint:100,lotStep:.01,minLot:.01,maxLot:10,
    commissionPerLot:7,slippage:.05,killSwitch:true,activeTrades:0}};
 const result=evaluate(input);
 if(result.signal!=='WAIT'||result.executable!==false||result.networkEnabled!==false||result.researchCandidate!=='NONE')
   throw Error('V3_RESEARCH_GATE_DID_NOT_FAIL_CLOSED');
 const detail={};
 const {structure}=require('./v3_market_structure');
 const {context}=require('./v3_ultimate');
 for(const tf of ['M15','H1','H4']){
  const data=frames[tf],ms=paper.MS[tf],last=data.at(-1);
  const fresh=last&&Date.parse(last.datetime)+ms<=Date.parse(asOfUTC)&&Date.parse(asOfUTC)-(Date.parse(last.datetime)+ms)<=ms;
  const obs=structure(data);
  const ctx=context(data,asOfUTC);
  detail[tf]={bars:data.length,alignedAndClosed:Boolean(fresh),bias:ctx.priorRangeBias||'UNKNOWN',
    bosUp:Boolean(obs.bosUp),bosDown:Boolean(obs.bosDown),
    chochUp:Boolean(ctx.chochUp),chochDown:Boolean(ctx.chochDown),
    sweepHigh:Boolean(obs.sweepHigh),sweepLow:Boolean(obs.sweepLow),
    fvgBull:Boolean(obs.fvgBull),fvgBear:Boolean(obs.fvgBear),
    ob:'UNAVAILABLE_NOT_VERIFIED'};
 }
 const status={mode:'OFFLINE_SYNTHETIC_REPLAY',dataOrigin:'SYNTHETIC_TEST_ONLY',
  signal:'WAIT',executable:false,researchEligible:false,brokerExecution:false,
  paperExecutionOnServer:false,connectedRealMarketData:false,
  engine:'V3 Ultimate r2 (existing research engine)',
  technicalCandidate:result.technical?.candidate||'NONE',
  tradePlanExecutable:false,entry:null,stop:null,tp1:null,tp2:null,tp3:null,
  indicators:{ema20:ema(closes,20),ema50:ema(closes,50),rsi14:rsi(closes),atr14:atr(bid),vwap:null,vwapStatus:'NO_VERIFIED_TRADES_OR_VOLUME'},
  structure:detail,blocked:[...new Set(['NOT_LICENSED_LIVE_DATA',...result.monitoring.blocked])],
  sourceStatus:{XAUUSD:'SYNTHETIC_TEST_ONLY',DXY:'UNAVAILABLE',US02Y:'UNAVAILABLE',US10Y:'UNAVAILABLE',GC:'UNAVAILABLE',calendar:'UNAVAILABLE',headlines:'UNAVAILABLE',orderFlow:'UNAVAILABLE'},
  asOfUTC,frameCounts:Object.fromEntries(Object.entries(frames).map(([k,v])=>[k,v.length])),
  providerRequests:0,ordersSent:0,credentialsRead:0,reason:'Recorded/test analysis is not a real-time trading recommendation; missing authorized external feeds.'};
 return status;
}
module.exports={inspect};
