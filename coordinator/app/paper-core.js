'use strict';
const fs=require('node:fs'),crypto=require('node:crypto');
const config=require('./config.json');
const configHash=crypto.createHash('sha256').update(fs.readFileSync(__dirname+'/config.json')).digest('hex');
if(fs.existsSync(__dirname+'/freeze-manifest.json')&&JSON.parse(fs.readFileSync(__dirname+'/freeze-manifest.json')).configSha256!==configHash)throw Error('Frozen prospective config hash mismatch');
const source=fs.readFileSync(__dirname+'/frozen/strategy.js');
if(crypto.createHash('sha256').update(source).digest('hex')!==config.strategySha256)throw Error('Frozen strategy hash mismatch');
const {analyze}=require('./frozen/strategy');
const {admit}=require('../timing');
const durations={'15min':15,'1h':60,'4h':240};
const stamp=c=>Date.parse(c.datetime.includes('T')?c.datetime:c.datetime.replace(' ','T')+'Z');
const date=t=>new Date(t).toISOString();
function marketOpen(t){
 const p=new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',weekday:'short',hour:'2-digit',hourCycle:'h23'}).formatToParts(new Date(t));
 const day=p.find(x=>x.type==='weekday').value,hour=Number(p.find(x=>x.type==='hour').value);
 return day!=='Sat'&&!(day==='Sun'&&hour<18)&&!(day==='Fri'&&hour>=17)&&hour!==17;
}
function normalize(raw,now){
 const frames={},all={};
 for(const [f,m]of Object.entries(durations)){
  if(raw[f]?.symbol!=='XAU/USD'||!Array.isArray(raw[f]?.values))throw Error('Invalid symbol or missing '+f);
  const rows=raw[f].values.map(c=>({datetime:date(stamp(c)),...Object.fromEntries(['open','high','low','close'].map(k=>[k,Number(c[k])]))})).sort((a,b)=>stamp(a)-stamp(b));
  if(rows.some((c,i)=>!Number.isFinite(stamp(c))||stamp(c)>now||![c.open,c.high,c.low,c.close].every(v=>Number.isFinite(v)&&v>0)||c.low>Math.min(c.open,c.close)||c.high<Math.max(c.open,c.close)||(i&&stamp(c)<=stamp(rows[i-1]))))throw Error('Invalid OHLC/time/duplicate '+f);
  all[f]=rows;frames[f]=rows.filter(c=>stamp(c)+m*60000<=now);
 }
 return {frames,all};
}
function costs(){return config.spreadUSDPerOz+config.roundTripCommissionUSDPerOz+2*config.slippagePerSideUSDPerOz;}
function settle(position,bar){
 const buy=position.side==='BUY',risk=Math.abs(position.entry-position.stop);
 let exit=null,reason=null;
 if((buy?bar.open<=position.stop:bar.open>=position.stop)){exit=bar.open;reason='STOP_GAP';}
 else if((buy?bar.open>=position.target2:bar.open<=position.target2)){exit=position.target2;reason='TARGET2_GAP';}
 else if((buy?bar.low<=position.stop:bar.high>=position.stop)){exit=position.stop;reason='STOP_FIRST';}
 else if((buy?bar.high>=position.target2:bar.low<=position.target2)){exit=position.target2;reason='TARGET2';}
 if(exit===null)return null;
 const grossPrice=(buy?1:-1)*(exit-position.entry),netR=(grossPrice-costs())/risk;
 return {exitPrice:exit,exitReason:reason,grossPrice,grossR:grossPrice/risk,roundTripPriceCost:costs(),netR,result:netR>0?'WIN':netR<0?'LOSS':'FLAT'};
}
function enter(decision,bar,now){
 const expected=Date.parse(decision.candleCloseUTC);
 if(now-expected>config.maximumEntryDelaySeconds*1000)return {type:'SKIP_ENTRY',reason:'Missed observation window; no retrospective fill'};
 if(!bar||stamp(bar)!==expected)return null;
 const side=decision.signal,entry=bar.open,stop=decision.stopReference,target2=decision.target2Reference;
 if(side==='BUY'?(stop>=entry||target2<=entry):(stop<=entry||target2>=entry))return {type:'SKIP_ENTRY',reason:'Invalid stop/target after gap'};
 return {type:'PAPER_ENTRY',position:{side,entry,stop,target1:decision.target1Reference,target2,entryBarUTC:bar.datetime,observedAtUTC:date(now),lastProcessedUTC:null,target1Touched:false,estimatedRoundTripPriceCost:costs(),fillType:'observed candle open proxy; not a broker fill'}};
}
function processSnapshot(raw,now,state){
 const events=[];const emit=(type,x={})=>events.push({type,observedAtUTC:date(now),strategyCommit:config.strategyCommit,configSha256:configHash,paperOnly:true,...x});
 let data;try{data=normalize(raw,now)}catch(e){emit('DATA_ERROR',{signal:'WAIT',reason:e.message});return events}
 const {frames,all}=data,m15=frames['15min'];
 // Manage only positions created prospectively; never backfill entries during downtime.
 if(state.position&&!state.position.quarantined){
  const p=state.position,start=Date.parse(p.lastProcessedUTC||p.entryBarUTC);
  let expected=p.lastProcessedUTC?start+900000:start;
  const bars=m15.filter(c=>stamp(c)>=expected);
  if(!bars.length&&m15.length&&stamp(m15[0])>expected){p.quarantined=true;emit('POSITION_QUARANTINED',{reason:'Position history no longer covered by endpoint'});}
  for(const bar of bars){
   while(expected<stamp(bar)&&!marketOpen(expected))expected+=900000;
   if(expected!==stamp(bar)){p.quarantined=true;emit('POSITION_QUARANTINED',{reason:'Missing active M15; cannot infer stop/target result',expectedUTC:date(expected),nextUTC:bar.datetime});break;}
   const outcome=settle(p,bar);p.lastProcessedUTC=bar.datetime;expected=stamp(bar)+900000;
   if(outcome){emit('PAPER_EXIT',{position:{...p},exitCandleOpenUTC:bar.datetime,...outcome});state.closedTrades=(state.closedTrades||0)+1;state.totalNetR=(state.totalNetR||0)+outcome.netR;state.lastExitCandleUTC=bar.datetime;state.position=null;break;}
   if(!p.target1Touched&&(p.side==='BUY'?bar.high>=p.target1:bar.low<=p.target1)){p.target1Touched=true;emit('TARGET1_TOUCHED',{price:p.target1,candleOpenUTC:bar.datetime,partialExit:false});}
  }
 }
 const open=marketOpen(now);
 const admission=admit(frames,now,{marketOpen:open});
 const fresh=admission.accepted;
 const last=m15.at(-1),close=last?stamp(last)+900000:null;
 if(!fresh){emit('STATUS',{signal:'WAIT',reason:open?admission.reason:'MARKET_CLOSED',timingAdmission:admission,frameLastClosed:Object.fromEntries(Object.entries(frames).map(([f,v])=>[f,v.at(-1)?.datetime||null])),entryReference:null,target1Reference:null,target2Reference:null,stopReference:null});return events;}
 if(now<Date.parse(config.prospectiveStartUTC)||now>=Date.parse(config.prospectiveEndUTC)){emit('STATUS',{signal:'WAIT',reason:'OUTSIDE_PREREGISTERED_WINDOW'});return events;}
 if(last.datetime!==state.lastDecisionCandleUTC){
  const decision=analyze(frames,{dataFresh:true});
  const record={...decision,candleOpenUTC:last.datetime,candleCloseUTC:date(close),entryReference:decision.entryReference??null,stopReference:decision.stopReference??null,target1Reference:decision.target1Reference??null,target2Reference:decision.target2Reference??null};
  emit('SIGNAL',record);state.lastDecisionCandleUTC=last.datetime;
  if(['BUY','SELL'].includes(decision.signal)&&!state.position){
   if(state.lastExitCandleUTC&&stamp(last)<=Date.parse(state.lastExitCandleUTC))emit('SKIP_ENTRY',{reason:'Signal on exit candle excluded, matching frozen backtester overlap rule'});
   else state.pending=record;
  }
 }
 if(state.pending&&!state.position){
  const forming=all['15min'].find(c=>stamp(c)===Date.parse(state.pending.candleCloseUTC));
  const result=enter(state.pending,forming,now);
  if(result){if(result.type==='PAPER_ENTRY')state.position=result.position;emit(result.type,result);state.pending=null;}
 }
 emit('HEARTBEAT',{positionOpen:Boolean(state.position),closedTrades:state.closedTrades||0,totalNetR:state.totalNetR||0});
 return events;
}
module.exports={processSnapshot,settle,enter,marketOpen,normalize};
