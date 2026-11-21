"use strict";
/**
 * Local-loopback HTTP smoke only. No external URLs, account secrets, market
 * providers, broker orders, or live trading. The new mobile page must be
 * served by the actual review process, not merely present on GitHub.
 */
const assert=require("node:assert/strict");
const http=require("node:http");
const net=require("node:net");
const {spawn}=require("node:child_process");
const fs=require("node:fs");

async function reservedPort(){
 const s=net.createServer();
 await new Promise((resolve,reject)=>{
  s.once("error",reject);s.listen(0,"127.0.0.1",resolve);
 });
 const port=s.address().port;
 await new Promise(resolve=>s.close(resolve));
 return port;
}
async function main(){
 const html=fs.readFileSync("review-dashboard.html","utf8");
 const original=fs.readFileSync("index.html","utf8");
 assert(html.includes('id="decision"'));
 assert(html.includes('src="/review-dashboard.js"'));
 assert(html.includes('id="viewer-setup-shortcut"'));
 assert(html.includes('href="/ultimate#biquote-viewer-guide"'));
 assert(!html.includes('fetch("/api/v3/research"'));
 assert(!html.includes('src="http'));
 assert(html.includes("WAIT"));
 assert(html.includes("executable = false"));
 assert(original.includes('href="review-dashboard.html"'));
 assert(!/MONITOR_READONLY_TOKEN|BROKER_TOKEN|CFI_PASSWORD/i.test(html));
 const port=await reservedPort();
 const child=spawn(process.execPath,["server.js"],{
  cwd:process.cwd(),
  env:{...process.env,PORT:String(port),DEMO_MODE:"standby",
   MARKET_DATA_BROKER_URL:"",BROKER_TOKEN:"",
   GOLD_SYNTHETIC_PAPER_JOURNAL:""},
  stdio:"ignore"
 });
 const request=(path,method="GET")=>new Promise((resolve,reject)=>{
  const req=http.request({hostname:"127.0.0.1",port,path,method,
   timeout:1800},res=>{
   let body="";
   res.setEncoding("utf8");
   res.on("data",chunk=>{body+=chunk;if(body.length>150000)req.destroy();});
   res.on("end",()=>resolve({status:res.statusCode,headers:res.headers,body}));
  });
  req.once("error",reject);req.once("timeout",()=>req.destroy(new Error("loopback timeout")));
  req.end();
 });
 try{
  let page;
  for(let attempt=0;attempt<30;attempt++){
   if(child.exitCode!==null)throw Error("Preview server exited before readiness");
   try{page=await request("/review-dashboard.html");break;}
   catch{await new Promise(r=>setTimeout(r,100));}
  }
  assert(page,"Preview GET did not start");
  assert.equal(page.status,200);
  assert.match(page.headers["content-type"],/text\/html/);
  assert.equal(page.headers["cache-control"],"no-store");
  assert.equal(page.headers["x-content-type-options"],"nosniff");
  assert.equal(page.headers["referrer-policy"],"no-referrer");
  assert.match(page.headers["content-security-policy"],/frame-ancestors 'none'/);
  assert.match(page.headers["content-security-policy"],/script-src 'self'/);
  assert.match(page.headers["content-security-policy"],/connect-src 'self'/);
  assert(page.body.includes('src="/review-dashboard.js"'));
 // Mobile setup shortcut must navigate to a real existing guide.
 assert(page.body.includes('id="viewer-setup-shortcut"'));
 assert(page.body.includes('href="/ultimate#biquote-viewer-guide"'));
  assert(!page.body.includes("/api/v3/research"));
  assert(page.body.includes('id="decision"'));
  assert(page.body.includes('id="internal-handoff"'));
  assert(page.body.includes('id="internal-gate-note"'));
  assert(page.body.includes('id="release-audit-summary"'));
  assert(page.body.includes('id="historical-archive-audit"'));
  assert(page.body.includes('id="paper-reports"'));
  assert(page.body.includes('id="paper-report-state"'));
  assert(page.body.includes('id="paper-report-hundred"'));
  assert(page.body.includes("توثيق الحساب وحده لا يكفي"));
  assert(page.body.includes("موافقة تخزين بيانات Render معلّقة"));
  assert(page.body.includes("WAIT"));
  assert(!page.body.includes("MONITOR_READONLY_TOKEN"));
  // The exact link shared with mobile users MUST NOT land on /ultimate.
  // HTTP 302 is deliberate: browser URL then visibly becomes the new page.
  const home=await request("/");
  assert.equal(home.status,302);
  assert.equal(home.headers.location,"/review-dashboard.html");
  assert.equal(home.headers["cache-control"],"no-store");
  assert.equal(home.headers["referrer-policy"],"no-referrer");
  assert(!home.body.includes("biquote-mobile-ui.js"));
  // Query strings, especially accidental access tokens, are not forwarded.
  const rootWithQuery=await request("/?token=SECRET_MUST_NOT_LEAK");
  assert.equal(rootWithQuery.status,302);
  assert.equal(rootWithQuery.headers.location,"/review-dashboard.html");
  assert(!JSON.stringify(rootWithQuery).includes("SECRET_MUST_NOT_LEAK"));
  const alias=await request("/review-dashboard");
  assert.equal(alias.status,200);
  assert(alias.body.includes("Gold Precision Pro Ultimate"));
  const script=await request("/review-dashboard.js");
  assert.equal(script.status,200);
  assert.match(script.headers["content-type"],/application\/javascript/);
  assert.equal(script.headers["cache-control"],"no-store");
  assert(script.body.includes('"/api/v3/ultimate/biquote-observation"'));
  assert(script.body.includes('"/api/v3/ultimate/biquote-viewer-status"'));
  assert(script.body.includes('"/api/v3/ultimate/paper-reports"'));
  assert(script.body.includes("AUTO_POLL_MS=10000"));
  assert(script.body.includes("الاتصال والتخزين السحابي مغلقان بانتظار موافقة مكتوبة"));
  assert(script.body.includes('credentials:"same-origin"'));
  assert(script.body.includes('rawQuoteShown!==true'));
  assert(!script.body.includes("MONITOR_READONLY_TOKEN"));
  assert.equal((await request("/review-dashboard.js","POST")).status,405);
  // Auth gate is a no-price, no-provider, read-only API. Anonymous requests
  // are denied and cannot trigger market data polling.
  const cookieCheck=await request("/api/v3/ultimate/biquote-viewer-status");
  assert.equal(cookieCheck.status,401);
  assert.equal(cookieCheck.headers["cache-control"],"private, no-store");
  const denied=JSON.parse(cookieCheck.body);
  assert.equal(denied.viewerSessionReady,false);
  assert.equal(denied.marketDataRequested,false);
  assert.equal(denied.ordersSent,0);
  assert.equal(denied.signal,"WAIT");
  assert.equal(denied.executable,false);
  assert.equal((await request("/api/v3/ultimate/biquote-viewer-status","POST")).status,405);
  const wrongMethod=await request("/review-dashboard.html","POST");
  assert.equal(wrongMethod.status,405);
  const prepared=await request("/api/v3/ultimate/preapproval-status");
  assert.equal(prepared.status,200);
  const safe=JSON.parse(prepared.body);
  assert.equal(safe.mode,"GOLD_PREAPPROVAL_FOUR_TRACKS_V1");
  assert.equal(safe.signal,"WAIT");
  assert.equal(safe.executable,false);
  assert.equal(safe.steps.dxyGcOrderFlow.dxy,"NOT_CONNECTED");
  assert.equal(safe.steps.capitalDemo.connected,false);
  assert.equal((await request("/api/v3/ultimate/preapproval-status","POST")).status,405);
  const reportGet=await request("/api/v3/ultimate/paper-reports");
  assert.equal(reportGet.status,200);
  assert.equal(reportGet.headers["cache-control"],"private, no-store");
  assert.equal(reportGet.headers["vary"],"Cookie");
  const paper=JSON.parse(reportGet.body);
  assert.equal(paper.mode,"GOLD_PRIVATE_OFFLINE_PAPER_REPORT_BRIDGE_V1");
  assert.equal(paper.status,"NO_PERSISTENT_PAPER_JOURNAL_CONNECTED");
  assert.equal(paper.privateJournalConnected,false);
  assert.equal(paper.closedTrades,0);
  assert.equal(paper.netModeledUsd,null);
  assert.equal(paper.winRate,null);
  assert.equal(paper.unverifiedNextM15ForecastAccuracy,null);
  assert.equal(paper.signal,"WAIT");
  assert.equal(paper.executable,false);
  assert.equal(paper.providerRequestsMade,0);
  assert(!reportGet.body.includes("entryPrice"));
  assert.equal((await request("/api/v3/ultimate/paper-reports","POST")).status,405);
  const integrated=await request("/api/v3/ultimate/internal-handoff");
  assert.equal(integrated.status,200);
  assert.equal(integrated.headers["cache-control"],"no-store");
  assert.equal(integrated.headers["x-content-type-options"],"nosniff");
  const handoff=JSON.parse(integrated.body);
  assert.equal(handoff.mode,"GOLD_INTERNAL_OFFLINE_HANDOFF_V1");
  assert.equal(handoff.status,"OFFLINE_INTERFACES_CHECKED_EXTERNAL_EVIDENCE_PENDING");
  assert.equal(handoff.internalOfflineContractsChecked,true);
  assert.equal(handoff.internalCheckCount,6);
  assert.equal(handoff.signal,"WAIT");
  assert.equal(handoff.executable,false);
  assert.equal(handoff.paperOrdersAllowed,false);
  assert.equal(handoff.providerRequestsMade,0);
  assert.equal(handoff.providerConnectionEnabled,false);
  assert.equal(handoff.externalProviderDecisionDeferredToLastStage,true);
  assert.equal(handoff.signalCandidate,null);
  assert.equal(handoff.releaseAudit.mode,"GOLD_PRELICENSE_RELEASE_AUDIT_V1");
  assert.equal(handoff.releaseAudit.internalSoftwareContractsChecked,6);
  assert.equal(handoff.releaseAudit.externalEvidenceVerifiedCount,0);
  assert.equal(handoff.releaseAudit.readyForBuySell,false);
  assert.equal(handoff.releaseAudit.readyForPaperExecution,false);
  assert.equal(handoff.releaseAudit.providerChosenOrConnected,false);
  assert.equal(handoff.releaseAudit.actualCIPassAttestedByRuntime,false);
  assert.equal(handoff.historicalArchiveAudit.mode,"GOLD_HISTORICAL_ACCURACY_EVIDENCE_AUDIT_V1");
  assert.equal(handoff.historicalArchiveAudit.status,"HASH_CHECKED_DEVELOPMENT_ARCHIVE_NOT_ACCURACY_PROOF");
  assert.equal(handoff.historicalArchiveAudit.archiveHashChecksPassed,2);
  assert.equal(handoff.historicalArchiveAudit.developmentM15Bars,4884);
  assert.equal(handoff.historicalArchiveAudit.independentHoldoutSamples,0);
  assert.equal(handoff.historicalArchiveAudit.independentAccuracyPct,null);
  assert.equal(handoff.historicalArchiveAudit.statisticallyValidated,false);
  assert.equal(handoff.historicalArchiveAudit.historicalRawPricesReturned,false);
  assert.equal((await request("/api/v3/ultimate/internal-handoff","POST")).status,405);
  assert.equal((await request("/api/v3/ultimate/internal-handoff","HEAD")).status,405);
  const nav=await request("/review");
  assert.equal(nav.status,200);
  assert(nav.body.includes('href="review-dashboard.html"'));
  const old=await request("/ultimate");
  assert.equal(old.status,200);
  assert(old.body.includes("biquote-mobile-ui.js"));
 assert(old.body.includes('id="biquote-viewer-guide"'));
 assert(old.body.includes('id="return-new-review-dashboard"'));
 assert(old.body.includes('href="/review-dashboard.html"'));
  console.log("PASS home redirects to compact mobile dashboard, explicit /ultimate preserved, viewer cookie remains private, no-store CSP, POST 405, no broker orders");
 }finally{child.kill("SIGTERM");}
}
main().catch(e=>{console.error(e);process.exitCode=1;});
