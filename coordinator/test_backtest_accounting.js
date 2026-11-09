'use strict';
const assert=require('node:assert/strict');
const {backtest}=require('./app/frozen/backtest');
function bar(open,high,low,close=open){return {open,high,low,close};}
function check(name,candles,signals,expected){
 const r=backtest(candles,signals,{spread:.4,risk:1});
 for(const [key,value] of Object.entries(expected))assert.equal(r[key],value,name+' '+key);
 assert.equal(r.estimatedPnLIsHypothetical,true);
 console.log('PASS '+name);
}
check('BUY target after costs',[bar(100,101,99),bar(100,104,99),bar(104,106,103)],[{index:0,side:'BUY',stop:98,target:104}],{trades:1,wins:1,totalR:1.8});
check('SELL stop after costs',[bar(100,101,99),bar(100,102,96)],[{index:0,side:'SELL',stop:102,target:96}],{trades:1,wins:0,totalR:-1.2});
check('ambiguous stop first',[bar(100,101,99),bar(100,105,97)],[{index:0,side:'BUY',stop:98,target:104}],{trades:1,wins:0,totalR:-1.2});
check('overlapping signal skipped',[bar(100,101,99),bar(100,101,99),bar(100,105,99)],[{index:0,side:'BUY',stop:98,target:104},{index:1,side:'BUY',stop:98,target:104}],{trades:1});
check('no signal no fabricated profit',[bar(100,101,99),bar(100,101,99)],[],{trades:0,wins:0,totalR:0});
console.log('All cases synthetic; NOT a historical performance result.');
