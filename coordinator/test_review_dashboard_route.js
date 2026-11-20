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
   MARKET_DATA_BROKER_URL:"",BROKER_TOKEN:""},
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
  assert(!page.body.includes("/api/v3/research"));
  assert(page.body.includes('id="decision"'));
  assert(page.body.includes("WAIT"));
  assert(!page.body.includes("MONITOR_READONLY_TOKEN"));
  const alias=await request("/review-dashboard");
  assert.equal(alias.status,200);
  assert(alias.body.includes("Gold Precision Pro Ultimate"));
  const script=await request("/review-dashboard.js");
  assert.equal(script.status,200);
  assert.match(script.headers["content-type"],/application\/javascript/);
  assert.equal(script.headers["cache-control"],"no-store");
  assert(script.body.includes('"/api/v3/ultimate/biquote-observation"'));
  assert(script.body.includes('"/api/v3/ultimate/biquote-viewer-status"'));
  assert(script.body.includes("AUTO_POLL_MS=10000"));
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
  const nav=await request("/review");
  assert.equal(nav.status,200);
  assert(nav.body.includes('href="review-dashboard.html"'));
  const old=await request("/ultimate");
  assert.equal(old.status,200);
  assert(old.body.includes("biquote-mobile-ui.js"));
  console.log("PASS local review mobile page served by real demo process, no-store CSP, old Ultimate intact, POST 405, no external calls or orders");
 }finally{child.kill("SIGTERM");}
}
main().catch(e=>{console.error(e);process.exitCode=1;});
