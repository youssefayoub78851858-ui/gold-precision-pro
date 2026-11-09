'use strict';
// Research-only, fixed filter. No change to V2 signal engine.
const fs=require('fs');
const {generateHistoricalSignals}=require('./app/frozen/strategy');
const {backtest}=require('./app/frozen/backtest');
const doc=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const bars=doc.frames['15min'];
const raw=generateHistoricalSignals(doc.frames);
const candidates=[
 {name:'baseline',filter:()=>true},
 {name:'cooldown_8_bars',filter:(s,previous)=>previous===null||s.index-previous>=8},
 {name:'cooldown_16_bars',filter:(s,previous)=>previous===null||s.index-previous>=16},
 {name:'cooldown_32_bars',filter:(s,previous)=>previous===null||s.index-previous>=32},
 {name:'avoid_first_2h_of_UTC_day',filter:s=>new Date(bars[s.index].datetime).getUTCHours()>=2},
 {name:'avoid_last_2h_of_UTC_day',filter:s=>new Date(bars[s.index].datetime).getUTCHours()<22}
];
const results=candidates.map(({name,filter})=>{
 let last=null;
 const signals=raw.filter(s=>{const keep=filter(s,last);if(keep)last=s.index;return keep});
 const r=backtest(bars,signals,{spread:0.4,risk:1});
 return {name,signals:signals.length,trades:r.trades,wins:r.wins,losses:r.losses,winRate:r.winRate,totalR:r.totalR,profitFactor:r.profitFactor,openAtEnd:r.openAtEnd};
});
console.log(JSON.stringify({source:doc.source,results,warning:'In-sample diagnostic only. Do not select a winner without separate out-of-sample testing; no orders placed.'},null,2));
