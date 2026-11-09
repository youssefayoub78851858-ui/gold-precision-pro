'use strict';
const fs=require('node:fs');
const {backtestFrames}=require('./app/frozen/backtest');
const d=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const r=backtestFrames(d.frames,{spread:0.4,risk:1});
const trades=r.tradesDetail;
const sum=(arr)=>+arr.reduce((a,b)=>a+b,0).toFixed(3);
const rounded=(x)=>+x.toFixed(3);
const out={source:d.source,trades:trades.length,overallR:r.totalR,exitType:{stop:0,target:0,other:0},targetRR:{min:null,max:null,average:null},entryGapFromSignal:{meanAbsolute:null,maxAbsolute:null},spreadCostR:0,stopDistance:{min:null,max:null},issues:[]};
const rr=[],dist=[],gap=[];
for(const t of trades){
 const risk=Math.abs(t.entry-t.stop);
 const reward=Math.abs(t.target-t.entry);
 rr.push(reward/risk);dist.push(risk);
 const signalClose=d.frames['15min'][t.signalIndex]?.close;
 if(Number.isFinite(signalClose))gap.push(Math.abs(t.entry-signalClose));
 out.spreadCostR+=0.4/risk;
 if(t.result==='WIN')out.exitType.target++;
 else if(Math.abs(t.exitPrice-t.stop)<1e-8)out.exitType.stop++;
 else out.exitType.other++;
}
if(trades.length){
 out.targetRR={min:rounded(Math.min(...rr)),max:rounded(Math.max(...rr)),average:rounded(sum(rr)/rr.length)};
 out.stopDistance={min:rounded(Math.min(...dist)),max:rounded(Math.max(...dist))};
 out.spreadCostR=rounded(out.spreadCostR);
 out.entryGapFromSignal={meanAbsolute:gap.length?rounded(sum(gap)/gap.length):null,maxAbsolute:gap.length?rounded(Math.max(...gap)):null};
}
out.issues.push('Backtest honors signal target from signal-close rather than rebuilding a fixed RR from next-bar entry; realized RR varies.');
out.issues.push('Spread is subtracted in R using 0.4/stop distance; broker bid/ask fills and variable spread are not modeled.');
out.issues.push('No slippage, commission, latency, partial fills or order rejections.');
console.log(JSON.stringify(out,null,2));
