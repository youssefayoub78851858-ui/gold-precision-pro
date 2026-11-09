#!/usr/bin/env node
'use strict';
const fs=require('node:fs');
const {backtestFrames}=require('./app/frozen/backtest');
const {generateHistoricalSignals}=require('./app/frozen/strategy');
const data=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const report=backtestFrames(data.frames,{spread:0.4,risk:1});
const allSignals=generateHistoricalSignals(data.frames);
const rawSignalSides={BUY:allSignals.filter(s=>s.side==='BUY').length,SELL:allSignals.filter(s=>s.side==='SELL').length};
const bars=data.frames['15min'];
const closed=report.tradesDetail;
const count=(xs)=>({count:xs.length,wins:xs.filter(t=>t.netR>0).length,losses:xs.filter(t=>t.netR<=0).length,totalR:+xs.reduce((a,t)=>a+t.netR,0).toFixed(2)});
const group=(fn)=>Object.fromEntries([...new Set(closed.map(fn))].sort().map(k=>[k,count(closed.filter(t=>fn(t)===k))]));
const trades=closed.map(t=>({...t,signalUTC:bars[t.signalIndex]?.datetime,entryUTC:bars[t.entryIndex]?.datetime,exitUTC:bars[t.exitIndex]?.datetime,holdingBars:t.exitIndex-t.entryIndex,stopDistance:+Math.abs(t.entry-t.stop).toFixed(3)}));
const losers=trades.filter(t=>t.netR<=0);
const summary={source:data.source,period:'2026-09-01 to 2026-10-01',signals:report.generatedSignals,rawSignalSides,closedTrades:closed.length,openAtEnd:report.openAtEnd,overall:count(closed),bySide:group(t=>t.side),byEntryHourUTC:group(t=>String(new Date(bars[t.entryIndex].datetime).getUTCHours()).padStart(2,'0')),byWeekUTC:group(t=>bars[t.entryIndex].datetime.slice(0,10).replace(/-\\d\\d$/,'')),losses:losers.map(t=>({side:t.side,signalUTC:t.signalUTC,entryUTC:t.entryUTC,exitUTC:t.exitUTC,netR:+t.netR.toFixed(3),holdingBars:t.holdingBars,stopDistance:t.stopDistance})),cautions:['Diagnostic grouping is descriptive only; no optimized parameters or claimed edge.','BID candles, fixed spread 0.4, no commission/slippage.','Missing sessions or gaps must be reviewed; results are not live execution.']};
console.log(JSON.stringify(summary,null,2));
