"use strict";
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const {inspectCandleSource}=require("./candle_source_readiness");
const policyFile=path.join(__dirname,"..","research","official","dukascopy-source-permissions.json");
const feasibilityFile=path.join(__dirname,"..","research","results","dukascopy-free-feasibility-2026-11-11.json");
function run(){
 const report=inspectCandleSource();
 assert.equal(report.mode,"CANDLE_SOURCE_FEASIBILITY_ONLY");
 assert.equal(report.signal,"WAIT");
 assert.equal(report.executable,false);
 assert.equal(report.automaticPollingEnabled,false);
 assert.equal(report.latestConnected,false);
 assert.equal(report.m15Live,false);
 assert.equal(report.h1Live,false);
 assert.equal(report.h4Live,false);
 assert.equal(report.publicOhlcDistributionEnabled,false);
 assert.deepEqual(report.derivedSampleCounts,{M15:96,H1:24,H4:6});
 assert.equal(report.legalStatus,"AWAITING_WRITTEN_PERMISSION");
 assert.equal(report.permissionEvidenceAvailable,false);
 assert.ok(!["candles","ohlc","bars","prices","frames","values"].some(k=>Object.hasOwn(report,k)));
 assert.ok(!Object.values(report).some(value=>Array.isArray(value)));
 const policy=JSON.parse(fs.readFileSync(policyFile,"utf8"));
 for(const flag of ["writtenPermissionReceived","automatedCollectionAuthorized",
   "scheduledPollingAuthorized","privateDataStorageAuthorized",
   "derivedDisplayAuthorized","publicRedistributionAuthorized",
   "productionIngestionEnabled","reviewIngestionEnabled","continuousPollingEnabled",
   "tradingExecutionEnabled"])assert.equal(policy[flag],false,flag);
 assert.equal(policy.writtenPermissionEvidenceReference,null);
 const metadata=JSON.parse(fs.readFileSync(feasibilityFile,"utf8"));
 assert.equal(metadata.latestProbe.latestBarClosedAtProbe,false);
 assert.equal(metadata.latestProbe.rawOHLCStoredOrPublished,false);
 console.log("PASS private candle feasibility remains metadata-only while Dukascopy permissions are pending; live and redistribution blocked");
}
run();
