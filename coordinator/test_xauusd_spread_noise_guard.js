'use strict';
const a=require('node:assert/strict');
const fs=require('node:fs');
const {evaluate}=require('./xauusd_spread_noise_guard');
const ASOF='2026-11-10T12:00:00Z',WIDTH=900000;
function sample(){
 const start=Date.parse(ASOF)-21*WIDTH;
 const env={sourceDataMode:'SYNTHETIC_TEST_ONLY',instrument:'XAU/USD',
 bid:[],ask:[],mid:[]};
 for(let i=0;i<21;i++){
  const t=new Date(start+i*WIDTH).toISOString();
  for(const [key,value] of [['bid',1999.9],['ask',2000.1],['mid',2000]]){
   env[key].push({openTime:t,open:value,high:value+.1,low:value-.1,close:value});
  }
 }
 return env;
}
const p=evaluate(sample(),ASOF,'BUY');
a.equal(p.status,'NO_20_BAR_CLOSE_BREAKOUT');
a.equal(p.signal,'WAIT');a.equal(p.executable,false);
a.equal(p.historicalLiveBboParityVerified,false);
a.equal(p.medianHistoricalCloseSpread,.2);
a.equal(p.predictedWinRate,null);
a.equal(p.providerRequestsMade,0);
a.equal(evaluate(undefined,ASOF).reasonCode,'CLOSED_BID_ASK_HISTORY_NOT_CONNECTED');
a.equal(evaluate(sample(),ASOF,'STRONG_BUY').status,'BLOCKED');
const valid=sample();
valid.bid.at(-1).open=2000.15;valid.bid.at(-1).close=2000.15;
valid.bid.at(-1).high=2000.23;valid.bid.at(-1).low=2000.07;
valid.ask.at(-1).open=2000.35;valid.ask.at(-1).close=2000.35;
valid.ask.at(-1).high=2000.43;valid.ask.at(-1).low=2000.27;
valid.mid.at(-1).open=2000.25;valid.mid.at(-1).close=2000.25;
valid.mid.at(-1).high=2000.33;valid.mid.at(-1).low=2000.17;
const q=evaluate(valid,ASOF,'BUY');
a.equal(q.status,'SYNTHETIC_DUAL_BASIS_BREAKOUT_ONLY');
a.equal(q.mid20BarCloseBreakout,true);
a.equal(q.bidHighLowCloseConfirmed,true);
a.equal(q.askHighLowCloseConfirmed,true);
a.equal(q.warnings.length,0);
a.equal(q.executable,false);
const midOnly=sample();
midOnly.bid.at(-1).open=1999.95;midOnly.bid.at(-1).close=1999.95;
midOnly.bid.at(-1).high=2000.03;midOnly.bid.at(-1).low=1999.87;
midOnly.ask.at(-1).open=2000.45;midOnly.ask.at(-1).close=2000.45;
midOnly.ask.at(-1).high=2000.53;midOnly.ask.at(-1).low=2000.37;
midOnly.mid.at(-1).open=2000.2;midOnly.mid.at(-1).close=2000.2;
midOnly.mid.at(-1).high=2000.28;midOnly.mid.at(-1).low=2000.12;
const z=evaluate(midOnly,ASOF,'BUY');
a.equal(z.status,'MID_ONLY_BREAKOUT_UNCONFIRMED');
a.equal(z.bidHighLowCloseConfirmed,false);
a.equal(z.askHighLowCloseConfirmed,true);
a(z.warnings.includes('MID_CLOSE_BREAKOUT_NOT_CONFIRMED_BY_BOTH_BID_AND_ASK'));
const wide=structuredClone(valid);
wide.ask.at(-1).open=2001;wide.ask.at(-1).close=2001;
wide.ask.at(-1).high=2001.08;wide.ask.at(-1).low=2000.92;
wide.mid.at(-1).open=(2000.15+2001)/2;wide.mid.at(-1).close=(2000.15+2001)/2;
wide.mid.at(-1).high=wide.mid.at(-1).close+.08;
wide.mid.at(-1).low=wide.mid.at(-1).close-.08;
const x=evaluate(wide,ASOF,'BUY');
a.equal(x.status,'SPREAD_WIDENING_RISK');
a(x.warnings.includes('SYNCHRONIZED_CLOSE_SPREAD_OVER_3X_PRIOR_MEDIAN'));
function fail(change,code){
 const s=sample();change(s);
 const r=evaluate(s,ASOF,'BUY');a.equal(r.status,'BLOCKED',JSON.stringify(r));
 a.equal(r.reasonCode,code);
 a.equal(r.signal,'WAIT');a.equal(r.executable,false);
}
fail(s=>{s.ask.at(-1).close=1999.7;},'INVALID_CLOSED_BBO_OHLC'); // ask close below low
fail(s=>{s.mid.at(-1).close+=.5;s.mid.at(-1).high+=.5;},'CROSSED_OR_NONPARITY_BID_ASK_MID');
fail(s=>{s.mid[7].openTime='2026-11-10T08:46:00Z';},'MISALIGNED_GAPPED_UNCLOSED_OR_FUTURE_M15');
fail(s=>{s.ask.at(-1).openTime=ASOF;},'MISALIGNED_GAPPED_UNCLOSED_OR_FUTURE_M15');
fail(s=>{s.bid.pop();},'M15_THREE_BASIS_CLOSED_HISTORY_REQUIRED');
fail(s=>{s.bid[3].high=NaN;},'INVALID_CLOSED_BBO_OHLC');
fail(s=>{s.ask[1].open=s.bid[1].open-.01;},'CROSSED_OR_NONPARITY_BID_ASK_MID');
fail(s=>{s.sourceDataMode='RECORDED_REAL_LIVE';},'SYNTHETIC_XAUUSD_BBO_ONLY');
fail(s=>{s.instrument='XAUUSDT';},'SYNTHETIC_XAUUSD_BBO_ONLY');
a.equal(evaluate(sample(),'2026-11-10T11:45:00Z','BUY').status,'BLOCKED');
const src=fs.readFileSync(require.resolve('./xauusd_spread_noise_guard'),'utf8');
a(!/new\s+WebSocket\s*\(/.test(src));
a(!/\bfetch\s*\(/.test(src));a(!/process\.env/.test(src));
console.log('PASS closed bid/ask/mid parity, median spread shock, mid-only breakout, gap/future/quarantine, WAIT');
