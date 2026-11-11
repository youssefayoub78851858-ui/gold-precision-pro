"use strict";
// Review source feasibility metadata: never fetches, stores, or exposes vendor OHLC.
const fs=require("node:fs");
const path=require("node:path");
const base=path.join(__dirname,"..","research");
const policyPath=path.join(base,"official","dukascopy-source-permissions.json");
const resultPath=path.join(base,"results","dukascopy-free-feasibility-2026-11-11.json");

function inspectCandleSource(){
 const p=JSON.parse(fs.readFileSync(policyPath,"utf8"));
 const r=JSON.parse(fs.readFileSync(resultPath,"utf8"));
 if(p.policyVersion!==1||p.status!=="AWAITING_WRITTEN_PERMISSION"||
    p.writtenPermissionReceived!==false||p.writtenPermissionEvidenceReference!==null||
    p.automatedCollectionAuthorized!==false||p.scheduledPollingAuthorized!==false||
    p.privateDataStorageAuthorized!==false||p.derivedDisplayAuthorized!==false||
    p.publicRedistributionAuthorized!==false||p.productionIngestionEnabled!==false||
    p.reviewIngestionEnabled!==false||p.continuousPollingEnabled!==false||
    p.tradingExecutionEnabled!==false)throw Error("Unknown or unsafe source permissions state");
 const sample=r.sample,probe=r.latestProbe;
 if(sample?.validM15!==96||sample?.completeH1!==24||sample?.completeH4!==6||
    sample?.rawSamplesCommitted!==false||probe?.latestBarClosedAtProbe!==false||
    probe?.rawOHLCStoredOrPublished!==false)throw Error("Unverified sample metadata");
 return {
  mode:"CANDLE_SOURCE_FEASIBILITY_ONLY",source:"Dukascopy XAUUSD",
  signal:"WAIT",executable:false,trading:"disabled",
  historicalSampleVerifiedFormat:true,independentlyAuthenticated:false,
  legalStatus:p.status,permissionEvidenceAvailable:false,
  automaticPollingEnabled:false,publicOhlcDistributionEnabled:false,
  latestConnected:false,m15Live:false,h1Live:false,h4Live:false,
  derivedSampleCounts:{M15:sample.validM15,H1:sample.completeH1,H4:sample.completeH4},
  sampleDateUTC:sample.observedStartUTC?.slice(0,10),
  lastOneTimeProbeUTC:probe.checkedUTC,
  lastOneTimeProbeFormingBarExcluded:true,
  requiredNextStep:"Obtain express written authorization for automated use and storage, or use an explicitly licensed broker/private export. Never treat this historical diagnostic as live.",
  providerTerms:p.evidenceURL,
  note:"No market data is fetched by this endpoint; response is metadata only. No live OHLC, signals or trades."
 };
}
module.exports={inspectCandleSource};
