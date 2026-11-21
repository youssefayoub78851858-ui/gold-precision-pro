"use strict";
/**
 * Strict offline historical evidence firewall. Existing September/October
 * archives were already used to develop V2; a digest and chronological
 * backtest do not turn them into independent holdout accuracy or prove vendor
 * rights. No data vendor, credentials, orders, or strategy execution.
 */
const fs=require("node:fs");
const path=require("node:path");
const crypto=require("node:crypto");
const root=path.resolve(__dirname,"..");
const MODE="GOLD_HISTORICAL_ACCURACY_EVIDENCE_AUDIT_V1";
function blocked(reason){
 return {mode:MODE,status:"ARCHIVE_EVIDENCE_CHECK_BLOCKED",reason,
  archiveHashChecksPassed:0,developmentM15Bars:0,
  independentHoldoutSamples:0,independentAccuracyPct:null,
  observedIndependentWinRatePct:null,verifiedBrokerCostSamples:0,
  independentlyVerifiedFeedRights:false,sourceAuthenticityIndependentlyVerified:false,
  liveMarketDataAvailable:false,statisticallyValidated:false,
  researchSignal:"WAIT",signal:"WAIT",executable:false,
  paperOrdersAllowed:false,liveOrdersAllowed:false,providerRequestsMade:0,
  providerApprovalDeferred:true,archiveUsedAsIndependentHoldout:false,
  historicalRawPricesReturned:false};
}
function audit(manifest,walk,archive,plan,hashes){
 try {
  if(!manifest||!Array.isArray(manifest.datasets)||
     manifest.datasets.length!==2||!walk||!archive||!plan||
     !hashes||typeof hashes!=="object")return blocked("REQUIRED_LOCAL_EVIDENCE_MISSING");
  const names=["2026-09-bid.json","2026-10-bid.json"];
  let bars=0;
  for(const [index,item] of manifest.datasets.entries()){
   if(!item||item.file!==names[index]||
      !/^[a-f0-9]{64}$/.test(item.sha256||"")||
      hashes[item.file]!==item.sha256||
      item.priceConvention!=="BID"||
      item.archiveDigestVerifiedAtImport!==true||
      item.verification!=="Retrieved from existing repository Actions artifact; provider authenticity not independently attested"||
      item.qualityReport?.status!=="VALID"||
      item.qualityReport?.symbol!=="XAU/USD"||
      !Number.isInteger(item.qualityReport.frames?.["15min"]?.count)||
      item.qualityReport.frames["15min"].count<1||
      !Number.isInteger(item.qualityReport.gapCounts?.["15min"])||
      item.qualityReport.gapCounts["15min"]<0||
      Date.parse(item.qualityReport.frames["15min"].lastOpenUTC)>=Date.parse(plan.earliestCaptureUTC))
      return blocked("INVALID_OR_NONINDEPENDENT_ARCHIVE_METADATA");
   bars+=item.qualityReport.frames["15min"].count;
  }
  if(walk.mode!=="RECORDED_BID_RESEARCH"||
     walk.executable!==false||
     walk.statisticallyValidated!==false||
     !Array.isArray(walk.provenance)||
     walk.provenance.length!==2||
     walk.provenance.some((p,i)=>p.file!==names[i]||p.sha256!==hashes[names[i]])||
     !Array.isArray(walk.scenarios)||
     walk.scenarios.length!==2||
     !Array.isArray(walk.limitations)||
     !walk.limitations.some(x=>x.includes("not untouched holdouts"))||
     !walk.limitations.some(x=>x.includes("zero trades is not success")))
   return blocked("RECORDED_DIAGNOSTIC_PROVENANCE_NOT_ATTESTED");
  if(archive.kind!=="ULTIMATE_VERSIONED_ARCHIVE_REPLAY"||
     archive.contractVersion!==2||archive.executable!==false||
     archive.networkEnabled!==false||archive.isIndependentHoldout!==false||
     archive.observedM15Decisions!==bars||archive.jointCoveragePct!==0||
     archive.externalEvidence?.status!=="NO_V2_EVIDENCE_BUNDLE"||
     archive.noPerformanceInference!==true||
     !["DXY","GC","orderFlow"].every(k=>archive.roleCoverage?.intraday?.[k]===0)||
     !["US02Y","US10Y"].every(k=>archive.roleCoverage?.dailyContext?.[k]===0))
   return blocked("DEPENDENT_ARCHIVE_HAS_NO_JOINT_CONTEXT_EVIDENCE");
  if(plan.status!=="DRAFT_BLOCKED"||plan.networkEnabled!==false||
     plan.executionEnabled!==false||plan.providerRequestBudget!==0||
     !Number.isFinite(Date.parse(plan.earliestCaptureUTC))||
     !plan.protocol?.noReuse?.includes("September/October 2026")||
     !plan.unresolvedPrerequisites?.some(s=>s.includes("rights")))
   return blocked("PROSPECTIVE_HOLDOUT_FREEZE_OR_RIGHTS_UNVERIFIED");
  for(const [i,scenario] of walk.scenarios.entries()){
   if(scenario.name!==["base","stress"][i]||
      !Array.isArray(scenario.windows)||
      !["train","validation","test"].every(n=>
        scenario.windows.some(w=>w.window===n)))return blocked("BACKTEST_WINDOWS_INCOMPLETE");
   for(const window of scenario.windows){
    for(const engine of ["v2","ultimate"]){
     const p=window[engine];
     if(!p||!Number.isInteger(p.trades)||p.trades<0||
        typeof p.netPnL!=="number"||!Number.isFinite(p.netPnL)||
        (p.winRate!==null&&
         (typeof p.winRate!=="number"||p.winRate<0||p.winRate>1)))
      return blocked("BACKTEST_METRICS_INVALID");
    }
    // Full Ultimate lacked mandatory context; zero trades must not be
    // relabelled as 100% accuracy or profitable abstention.
    if(window.ultimate.trades!==0)return blocked("UNEXPECTED_FULL_ULTIMATE_ARCHIVE_OUTCOME");
   }
  }
  return {...blocked("DEVELOPMENT_ARCHIVE_ONLY_NOT_UNTOUCHED_HOLDOUT"),
   status:"HASH_CHECKED_DEVELOPMENT_ARCHIVE_NOT_ACCURACY_PROOF",
   archiveHashChecksPassed:2,developmentM15Bars:bars,
   recordedGapCountM15:manifest.datasets.reduce((n,x)=>
     n+x.qualityReport.gapCounts["15min"],0),
   historicDevelopmentWindows:walk.scenarios.map(s=>({
    modeledCostScenario:s.name,
    // Explicitly research-only, never an independent performance claim.
    windows:s.windows.filter(w=>["train","validation","test"].includes(w.window))
      .map(w=>({name:w.window,v2ClosedTrades:w.v2.trades,
       v2DevelopmentWinRatePct:w.v2.winRate===null?null:
        Math.round(w.v2.winRate*10000)/100,
       ultimateClosedTrades:w.ultimate.trades,
       independent:false}))
   })),
   caveat:"Archive hashes verify local file integrity only; development reuse, missing DXY/GC/order flow, and unverified vendor rights prohibit independent accuracy claims."
  };
 }catch(_){return blocked("MALFORMED_OR_INCOMPLETE_ARCHIVAL_EVIDENCE");}
}
function inspect(){
 try{
  const manifest=JSON.parse(fs.readFileSync(path.join(root,"research/recorded/manifest.json"),"utf8"));
  const walk=JSON.parse(fs.readFileSync(path.join(root,"research/results/ultimate-walkforward.json"),"utf8"));
  const archive=JSON.parse(fs.readFileSync(path.join(root,"research/results/ultimate-v2-archive-comparison.json"),"utf8"));
  const plan=JSON.parse(fs.readFileSync(path.join(root,"research/ultimate-prospective-plan.json"),"utf8"));
  const hashes=Object.create(null);
  for(const item of manifest.datasets){
   if(typeof item.file!=="string"||!/^[0-9]{4}-[0-9]{2}-bid\.json$/.test(item.file))
    return blocked("ARCHIVE_FILE_NAME_INVALID");
   hashes[item.file]=crypto.createHash("sha256").update(
     fs.readFileSync(path.join(root,"research/recorded",item.file))
   ).digest("hex");
  }
  return audit(manifest,walk,archive,plan,hashes);
 }catch(_){return blocked("ARCHIVE_NOT_AVAILABLE_OR_READ_FAILED");}
}
module.exports={inspect,audit};
