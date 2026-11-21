"use strict";
const a=require("node:assert/strict");
const fs=require("node:fs");
const crypto=require("node:crypto");
const path=require("node:path");
const root=path.join(__dirname,"..");
const {inspect,audit}=require("./historical_accuracy_evidence_audit");
function fixture(){
 const read=p=>JSON.parse(fs.readFileSync(path.join(root,p),"utf8"));
 const manifest=read("research/recorded/manifest.json"),
  walk=read("research/results/ultimate-walkforward.json"),
  archive=read("research/results/ultimate-v2-archive-comparison.json"),
  plan=read("research/ultimate-prospective-plan.json"),hashes={};
 for(const row of manifest.datasets){
  hashes[row.file]=crypto.createHash("sha256").update(
   fs.readFileSync(path.join(root,"research/recorded",row.file))
  ).digest("hex");
 }
 return {manifest,walk,archive,plan,hashes};
}
function safe(x){
 a.equal(x.mode,"GOLD_HISTORICAL_ACCURACY_EVIDENCE_AUDIT_V1");
 a.equal(x.independentAccuracyPct,null);
 a.equal(x.observedIndependentWinRatePct,null);
 a.equal(x.independentHoldoutSamples,0);
 a.equal(x.verifiedBrokerCostSamples,0);
 a.equal(x.independentlyVerifiedFeedRights,false);
 a.equal(x.sourceAuthenticityIndependentlyVerified,false);
 a.equal(x.marketPricesReturned,undefined);
 a.equal(x.historicalRawPricesReturned,false);
 a.equal(x.statisticallyValidated,false);
 a.equal(x.archiveUsedAsIndependentHoldout,false);
 a.equal(x.researchSignal,"WAIT");
 a.equal(x.signal,"WAIT");
 a.equal(x.executable,false);
 a.equal(x.paperOrdersAllowed,false);
 a.equal(x.liveOrdersAllowed,false);
 a.equal(x.providerRequestsMade,0);
 a.equal(x.providerApprovalDeferred,true);
 a(!JSON.stringify(x).includes("apiKey"));
 a(!JSON.stringify(x).includes("SECRET"));
}
const x=inspect();safe(x);
a.equal(x.status,"HASH_CHECKED_DEVELOPMENT_ARCHIVE_NOT_ACCURACY_PROOF");
a.equal(x.archiveHashChecksPassed,2);
a.equal(x.developmentM15Bars,4884);
a.equal(x.historicDevelopmentWindows.length,2);
for(const row of x.historicDevelopmentWindows){
 a(["base","stress"].includes(row.modeledCostScenario));
 a.equal(row.windows.length,3);
 for(const window of row.windows){
  a.equal(window.independent,false);
  a.equal(window.ultimateClosedTrades,0);
  a(window.v2ClosedTrades>0);
 }
}
const base=fixture(),same=audit(...["manifest","walk","archive","plan","hashes"].map(k=>base[k]));
a.deepEqual(same,x);
const mutations=[
 f=>f.hashes["2026-09-bid.json"]="0".repeat(64),
 f=>f.manifest.datasets[0].archiveDigestVerifiedAtImport=false,
 f=>f.manifest.datasets[1].verification="independently verified",
 f=>f.manifest.datasets[0].qualityReport.frames["15min"].count=999999,
 f=>f.archive.isIndependentHoldout=true,
 f=>f.archive.jointCoveragePct=100,
 f=>f.archive.roleCoverage.intraday.DXY=100,
 f=>f.archive.externalEvidence.status="FULL",
 f=>f.archive.noPerformanceInference=false,
 f=>f.walk.statisticallyValidated=true,
 f=>f.walk.provenance[0].sha256="0".repeat(64),
 f=>f.walk.scenarios[0].windows[0].ultimate.trades=20,
 f=>f.walk.scenarios[0].windows[0].v2.winRate=1.5,
 f=>f.plan.status="READY",
 f=>f.plan.protocol.noReuse="archive may be reused",
 f=>f.plan.earliestCaptureUTC="2026-01-01T00:00:00Z"
];
for(const mutate of mutations){
 const f=structuredClone(base);mutate(f);
 const r=audit(f.manifest,f.walk,f.archive,f.plan,f.hashes);safe(r);
 a.equal(r.status,"ARCHIVE_EVIDENCE_CHECK_BLOCKED");
 a.equal(r.archiveHashChecksPassed,0);
 a.equal(r.developmentM15Bars,0);
}
for(const val of [null,{},[],{mode:"READY"},false]){
 const r=audit(val,val,val,val,val);safe(r);
 a.equal(r.status,"ARCHIVE_EVIDENCE_CHECK_BLOCKED");
}
console.log("PASS recorded dev-only 4884 BID bar digests, no independent holdout, no licensed source or BUY/SELL");
