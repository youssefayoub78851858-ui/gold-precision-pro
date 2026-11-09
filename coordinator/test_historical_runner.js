'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),{spawnSync}=require('node:child_process');
const dir=fs.mkdtempSync(path.join(os.tmpdir(),'gold-hist-'));
try{
 const file=path.join(dir,'history.json');
 const start=Date.parse('2026-09-01T00:00:00Z');
 const frames={};
 for(const [frame,min] of [['15min',15],['1h',60],['4h',240]]){
  frames[frame]=Array.from({length:65},(_,i)=>({datetime:new Date(start+i*min*60000).toISOString(),open:4100,high:4102,low:4098,close:4101}));
 }
 fs.writeFileSync(file,JSON.stringify({source:'synthetic-test-only',symbol:'XAU/USD',frames}));
 const run=spawnSync(process.execPath,[path.join(__dirname,'run_historical_backtest.js'),file],{encoding:'utf8'});
 assert.notEqual(run.status,0,'Synthetic source must be rejected as real');
 assert.match(run.stderr,/Refusing to label synthetic/);
 const invalid=JSON.parse(fs.readFileSync(file));invalid.source='recorded-market-data';invalid.frames['1h'][1].low=5000;
 fs.writeFileSync(file,JSON.stringify(invalid));
 const fail=spawnSync(process.execPath,[path.join(__dirname,'run_historical_backtest.js'),file],{encoding:'utf8'});
 assert.notEqual(fail.status,0);
 assert.match(fail.stderr,/History validation failed/);
 console.log('PASS: historical runner rejects fabricated provenance and invalid OHLC');
}finally{fs.rmSync(dir,{recursive:true,force:true});}
