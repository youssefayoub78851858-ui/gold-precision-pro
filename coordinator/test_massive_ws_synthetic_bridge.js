'use strict';
const a=require('node:assert/strict');
const {spawnSync}=require('node:child_process');
const {createSyntheticBridge}=require('./massive_ws_synthetic_bridge');
const start=Date.parse('2026-11-10T08:00:00Z');
let now=start;const b=createSyntheticBridge(()=>now);
const msg=e=>b.frame(JSON.stringify(e));
msg({ev:'status',status:'connected'});
msg({ev:'status',status:'auth_success'});
msg({ev:'status',status:'success',message:'subscribed to: C.XAU-USD'});
a.equal(b.packet(),null);
for(let i=0;i<16*45;i++){
 now=start+10000+i*20000;
 const bid=100+i*.001;
 a.equal(msg({ev:'C',p:'XAU/USD',t:now,b:bid,a:bid+.4}).state,'STREAMING');
}
a.equal(b.packet(),null); // last H4 is still open
now=start+16*900000+10000;
msg({ev:'C',p:'XAU/USD',t:now,b:101,a:101.4});
const packet=b.packet();a(packet);
a.deepEqual(Object.values(packet.frames).map(f=>f.candles.length),[16,4,1]);
a.equal(packet.mode,'synthetic');
a.equal(packet.frames['4h'].candles[0].open,100);
a.equal(packet.frames['4h'].candles[0].close,100+719*.001);
// Exercise the actual Python intake and research gate, not a duplicate mock.
const py=[
 'import json,sys',
 'from xauusd_feed_gate import SourcePolicy, intake_payload, parse_utc',
 'from xauusd_research_pipeline import run_research_pipeline',
 'p=json.load(sys.stdin); now=parse_utc(p["receivedUTC"])',
 'x=intake_payload(p,now,SourcePolicy())',
 'assert x["status"]=="SYNTHETIC_TEST_ONLY"',
 'assert x["researchEligible"] is False',
 'assert [x["frames"][k]["count"] for k in ("15min","1h","4h")]==[16,4,1]',
 'r=run_research_pipeline(p,now,SourcePolicy(),{})',
 'assert r["signal"]=="WAIT" and r["executable"] is False',
 'assert all(v=="SKIPPED" for v in r["engines"].values())',
 'assert "paperSnapshot" not in r',
 'p["mode"]="live"; p["provider"]="Massive"',
 'assert intake_payload(p,now,SourcePolicy())["status"]=="BLOCKED"',
].join('\n');
const run=spawnSync('python',['-c',py],{cwd:__dirname,input:JSON.stringify(packet),encoding:'utf8',timeout:15000});
a.equal(run.status,0,run.stderr||String(run.error||'Python test failed'));
now+=30000;a.equal(b.tick().state,'CLOSED');a.equal(b.packet(),null);
// A reversed timestamp inside the otherwise fresh transport window closes
// both layers and prevents the bridge from producing a packet.
now=start;const c=createSyntheticBridge(()=>now);
for(const e of [{ev:'status',status:'connected'},{ev:'status',status:'auth_success'},
 {ev:'status',status:'success',message:'subscribed to: C.XAU-USD'}])c.frame(JSON.stringify(e));
now+=10000;c.frame(JSON.stringify({ev:'C',p:'XAU/USD',t:now,b:100,a:100.4}));
now+=1;a.equal(c.frame(JSON.stringify({ev:'C',p:'XAU/USD',t:now-2,b:100,a:100.4})).reason,'QUOTE_SEQUENCE_GAP_OR_REVERSE');
a.equal(c.packet(),null);
console.log('PASS synthetic handshake -> closed 16 M15/4 H1/1 H4 -> real research gate; no provider or orders');
