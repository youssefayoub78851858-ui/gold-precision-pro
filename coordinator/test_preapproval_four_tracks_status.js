"use strict";
const a=require("node:assert/strict");
const {inspect}=require("./preapproval_four_tracks_status");
const {snapshot}=require("./multi_source_public_readiness");
const x=inspect();
a.equal(x.mode,"GOLD_PREAPPROVAL_FOUR_TRACKS_V1");
a.equal(x.signal,"WAIT");a.equal(x.executable,false);
a.equal(x.paperOrdersAllowed,false);a.equal(x.liveOrdersAllowed,false);
a.equal(x.providerRequestsMade,0);a.equal(x.brokerOrdersSent,0);
a.equal(x.sourceRightsVerified,false);a.equal(x.allFourTracksTradeReady,false);
a.equal(x.status,"OFFLINE_PREPARATION_ONLY");
a.equal(Object.keys(x.steps).length,4);
a.equal(x.steps.dxyGcOrderFlow.dxy,"NOT_CONNECTED");
a.equal(x.steps.capitalDemo.connected,false);
a.equal(x.steps.capitalDemo.privateCloudStorageApproved,false);
a.equal(x.steps.paperRisk.paperOrdersActivated,false);
for(const name of Object.keys(x.steps))a.equal(x.steps[name].liveTradeReady,false);
const src=snapshot();
for(const fake of [
 {...src,verifiedLiveLayerCount:1},
 {...src,executable:true},
 {...src,sourceRequestsMade:1},
 {...src,layers:{...src.layers,DXY:{...src.layers.DXY,liveReady:true}}},
 {...src,capitalDemoPreKyc:{...src.capitalDemoPreKyc,connected:true}},
 {...src,capitalDemoPreKyc:{...src.capitalDemoPreKyc,permissionToStoreOnPrivateRenderConfirmed:true}},
]){
 const r=inspect(fake);
 a.equal(r.status,"BLOCKED_REQUIREMENTS_UNVERIFIED");
 a.equal(r.signal,"WAIT");a.equal(r.executable,false);a.equal(r.steps,null);
}
for(const forbidden of ["apiKey","secret","CST","X-SECURITY-TOKEN","brokerPassword"])
 a.equal(JSON.stringify(x).includes(forbidden),false);
console.log("PASS four-track preparations: offline-only and all four non-executable");
