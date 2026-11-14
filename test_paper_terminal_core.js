'use strict';
const assert=require('node:assert/strict');
const c=require('./paper-terminal-core');
const a=c.sample();
assert.equal(a.dataOrigin,'SYNTHETIC_TEST_ONLY');
assert.equal(a.bars.length,512);
assert.equal(c.group(a.bars,'H1').length,128);
assert.equal(c.group(a.bars,'H4').length,32);
let s=c.defaultSession(a);
assert.equal(c.stats(s).closed,0);
assert.throws(()=>c.open(s,'BUY',4000,[4010,4020,4030]),/INVALID_STOP_TARGET_GEOMETRY/);
const q=c.quote(s);
const p=c.open(s,'BUY',q.ask-2,[q.ask+2,q.ask+4,q.ask+8]);
assert.equal(p.side,'BUY');
assert.equal(p.lots,.01);
assert.equal(p.openedUTC,q.closeUTC);
assert.throws(()=>c.open(s,'SELL',q.bid+2,[q.bid-2,q.bid-4,q.bid-8]),/POSITION_OR_KILL_SWITCH/);
assert.equal(s.position!==null,true);
c.advance(s); // stop/TP logic is conservative and never enters without manual input
if(s.position){let trade=c.close(s,'MANUAL');assert(Number.isFinite(trade.net));assert.equal(s.trades.length,1)}
assert.equal(s.position,null);
assert.equal(c.stats(s).closed,1);
assert.equal(c.stats(s).balance,s.balance);
// A new bar may open a new manual paper position; same-bar duplicates are rejected in a separate test.
const single=c.defaultSession(a);const qq=c.quote(single);c.open(single,'BUY',qq.ask-2,[qq.ask+2,qq.ask+4,qq.ask+8]);c.close(single,'MANUAL');assert.throws(()=>c.open(single,'BUY',qq.ask-2,[qq.ask+2,qq.ask+4,qq.ask+8]),/DUPLICATE_ENTRY_ON_SAME_BAR/);
// Gap, unclosed, nonfinite, false origins, bid/ask crossing all rejected.
function bad(mut,re){let d=JSON.parse(JSON.stringify(a));mut(d);assert.throws(()=>c.validate(d),re)}
bad(d=>d.dataOrigin='LIVE',/EXPLICIT_XAUUSD_ORIGIN/);
bad(d=>d.bars[8].bid.high=NaN,/NONFINITE_OR_INVALID_PRICE/); // JSON cloning mutation creates NaN
bad(d=>d.bars[8].ask.open=1,/CROSSED_BID_ASK|INVALID_OHLC/);
bad(d=>d.bars.splice(3,1),/MISSING_DUPLICATE/);
bad(d=>d.bars.at(-1).time='2090-01-01T00:00:00Z',/BAR_FORMING/);
assert.throws(()=>c.validate({}),/EXPLICIT_XAUUSD_ORIGIN/);
assert.throws(()=>c.checkedSession({...c.defaultSession(a),cursor:99999}),/INVALID_CURSOR/);
const state=c.defaultSession(a);state.cursor=64;
const qu=c.quote(state);const sh=c.open(state,'SELL',qu.bid+3,[qu.bid-1,qu.bid-2,qu.bid-3]);
assert.equal(sh.side,'SELL');
const back=c.checkedSession(JSON.parse(JSON.stringify(state)));assert.equal(back.position.side,'SELL');
// Cannot consume futures without explicit replay advance.
assert.equal(back.cursor,64);
console.log('PASS paper terminal core: M15/H1/H4, closed BID/ASK, manual paper, costs, stats, replay, fail closed');
// Conservative stop-first and adverse gap fill in a synthetic-only next candle.
const conservative=c.defaultSession(c.sample());
const p0=c.quote(conservative);
const pos=c.open(conservative,'BUY',p0.ask-3,[p0.ask+.8,p0.ask+1.5,p0.ask+2]);
const next=conservative.dataset.bars[conservative.cursor+1];
next.bid.open=pos.stop-1.5;next.bid.low=pos.stop-2;
next.bid.high=pos.tp[2]+1; // stop and target are both reachable; STOP must win.
next.ask.open=next.bid.open+.36;next.ask.low=next.bid.low+.36;next.ask.high=next.bid.high+.36;
c.advance(conservative);
assert.equal(conservative.position,null);
assert.equal(conservative.trades.at(-1).reason,'STOP_FIRST_BOTH_TOUCHED');
assert(conservative.trades.at(-1).exit<=pos.stop-1.5);
assert(conservative.trades.at(-1).net<0);
console.log('PASS conservative gap fill and stop-first when SL and TP are hit in the same M15 bar');

// Deterministic independent stop-loss scenarios; no provider, no future market feed.
const standalone=c.stopLossSelfTest();
assert.equal(standalone.signal,'WAIT');
assert.equal(standalone.executable,false);
assert.equal(standalone.liveData,false);
assert.equal(standalone.providerRequests,0);
assert.equal(standalone.ordersSent,0);
assert.equal(standalone.existingPaperJournalChanged,false);
assert.deepEqual(standalone.cases.map(x=>x.reason),['STOP','STOP','STOP_FIRST_BOTH_TOUCHED']);
assert.deepEqual(standalone.cases.map(x=>x.side),['BUY','SELL','BUY']);
assert(standalone.cases.every(x=>x.net<0&&x.lossIncludesCosts));
assert(standalone.cases[0].exit<standalone.cases[0].stop);
assert(standalone.cases[1].exit>standalone.cases[1].stop);
assert.deepEqual(standalone,c.stopLossSelfTest());
console.log('PASS deterministic independent stop-only BUY/SELL, stop-first, adverse gap and fee tests');
