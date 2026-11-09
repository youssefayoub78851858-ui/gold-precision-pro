'use strict';
const assert=require('node:assert/strict');
const {generateHistoricalSignals}=require('./app/frozen/strategy');
const {backtestFrames}=require('./app/frozen/backtest');
const step=900000,origin=Date.parse('2026-09-01T00:00:00Z');
const candle=(t,i)=>{const c=4100+i*.075+Math.sin(i/6)*1.1;return {datetime:new Date(t).toISOString(),open:c-.2,high:c+1,low:c-1,close:c};};
const m15=Array.from({length:960},(_,i)=>candle(origin+i*step,i));
const aggregate=(n)=>Array.from({length:Math.floor(m15.length/n)},(_,j)=>{
 const bars=m15.slice(j*n,(j+1)*n);
 return {datetime:bars[0].datetime,open:bars[0].open,close:bars.at(-1).close,
 high:Math.max(...bars.map(b=>b.high)),low:Math.min(...bars.map(b=>b.low))};
});
const frames={'15min':m15,'1h':aggregate(4),'4h':aggregate(16)};
const signals=generateHistoricalSignals(frames);
const result=backtestFrames(frames,{spread:.4,risk:1});
assert.equal(result.generatedSignals,signals.length);
assert.equal(result.tradesDetail.length,result.trades);
assert.equal(result.estimatedPnLIsHypothetical,true);
assert.ok(Number.isFinite(result.totalR));
const index=800;
const prefix={'15min':m15.slice(0,index+2),'1h':frames['1h'].filter(b=>Date.parse(b.datetime)+3600000<=Date.parse(m15[index+1].datetime)),'4h':frames['4h'].filter(b=>Date.parse(b.datetime)+14400000<=Date.parse(m15[index+1].datetime))};
const before=generateHistoricalSignals(prefix).filter(s=>s.index<=index);
const altered=JSON.parse(JSON.stringify(frames));
for(let i=index+2;i<altered['15min'].length;i++){altered['15min'][i].close+=1000;altered['15min'][i].high+=1000;altered['15min'][i].open+=1000;altered['15min'][i].low+=1000;}
for(const f of ['1h','4h'])for(const b of altered[f])if(Date.parse(b.datetime)>Date.parse(m15[index+1].datetime)){b.open+=1000;b.high+=1000;b.low+=1000;b.close+=1000;}
const after=generateHistoricalSignals(altered).filter(s=>s.index<=index);
assert.deepEqual(after,signals.filter(s=>s.index<=index),'Future candle modifications must not alter past signals');
assert.ok(before.length>=0);
console.log(JSON.stringify({status:'PASS',signals:signals.length,closedTrades:result.trades,syntheticOnly:true,lookaheadRegression:'PASS'}));
