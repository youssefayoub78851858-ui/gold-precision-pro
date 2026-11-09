#!/usr/bin/env node
'use strict';
// Offline historical XAUUSD backtest runner. Never contacts providers or places orders.
const fs=require('node:fs');
const {spawnSync}=require('node:child_process');
const path=require('node:path');
const {backtestFrames}=require('./app/frozen/backtest');
const file=process.argv[2];
if(!file){console.error('Usage: node coordinator/run_historical_backtest.js <history.json>');process.exit(2);}
const validator=spawnSync('python3',[path.join(__dirname,'validate_history.py'),file],{encoding:'utf8'});
if(validator.status!==0){console.error('History validation failed:',validator.stderr||validator.stdout);process.exit(1);}
const document=JSON.parse(fs.readFileSync(file,'utf8'));
if(!document.source||/synthetic|test|fabricated|mock/i.test(document.source)){
 console.error('Refusing to label synthetic data as real historical market performance');process.exit(1);
}
const report=backtestFrames(document.frames,{spread:0.4,risk:1});
const summary={source:document.source,symbol:document.symbol,frames:Object.fromEntries(Object.entries(document.frames).map(([k,v])=>[k,v.length])),engine:report.engine,spreadUSD:0.4,riskUnitUSD:1,signals:report.generatedSignals,trades:report.trades,wins:report.wins,losses:report.losses,winRate:report.winRate,profitFactor:report.profitFactor,totalR:report.totalR,estimatedPnLUSD:report.estimatedPnL,openAtEnd:report.openAtEnd,limitations:report.auditNotes};
console.log(JSON.stringify(summary,null,2));
if(process.argv[3]==='--details')console.log(JSON.stringify(report.tradesDetail,null,2));
