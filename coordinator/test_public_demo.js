'use strict';
const assert=require('node:assert/strict');
const {spawn}=require('node:child_process');
const net=require('node:net');
const vm=require('node:vm');
const path=require('node:path');

async function freePort(){
 const probe=net.createServer();
 await new Promise(resolve=>probe.listen(0,'127.0.0.1',resolve));
 const port=probe.address().port;
 await new Promise(resolve=>probe.close(resolve));
 return port;
}

async function main(){
 const port=await freePort();
 const root=path.resolve(__dirname,'..');
 const child=spawn(process.execPath,[path.join(root,'server.js')],{
  cwd:root,
  env:{...process.env,PORT:String(port),DEMO_MODE:'standby',MARKET_DATA_BROKER_URL:'',BROKER_TOKEN:''},
  stdio:'ignore'
 });
 const base=`http://127.0.0.1:${port}`;
 try{
  let health;
  for(let i=0;i<50;i++){
   try{health=await fetch(base+'/health');if(health.ok)break;}catch{}
   await new Promise(resolve=>setTimeout(resolve,50));
  }
  assert.ok(health?.ok,'demo server did not start');
  const status=await health.json();
  assert.equal(status.mode,'DEMO_STANDBY');
  assert.equal(status.providerAccess,false);
  assert.equal(status.trading,'disabled');
  const page=await fetch(base+'/');
  assert.equal(page.status,200);
  const html=await page.text();
  assert.match(html,/مراجعة V3/);
  assert.match(html,/id="gold-live-price">غير متاح/);
  assert.match(html,/id="decision-state">WAIT/);
  assert.match(html,/لا يوجد سعر لحظي موصول/);
  const reviewPage=await fetch(base+'/review');
  assert.equal(reviewPage.status,200);
  assert.match(await reviewPage.text(),/مراجعة V3/);
  // Parse every inline Ultimate script, so a broken button handler fails CI.
  const ultimatePage=await fetch(base+'/ultimate');
  assert.equal(ultimatePage.status,200);
  const ultimateHtml=await ultimatePage.text();
  assert.match(ultimateHtml,/id="recorded-review-load"/);
  const embeddedScripts=[...ultimateHtml.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/gi)];
  assert.ok(embeddedScripts.length>=2,'Ultimate inline scripts missing');
  for(const [i,match] of embeddedScripts.entries()){
   assert.doesNotThrow(()=>new vm.Script(match[1],{filename:'ultimate-inline-'+i+'.js'}));
  }
  const response=await fetch(base+'/api/v3/research');
  assert.equal(response.status,200);
  const result=await response.json();
  assert.equal(result.engine,'V3');
  assert.equal(result.signal,'WAIT');
  assert.equal(result.executable,false);
  assert.equal(result.dataStatus,'STANDBY');
  assert.equal(Object.hasOwn(result,'price'),false);
  assert.match(result.reason,/لا تُعرض أسعار افتراضية/);
  const candles=await fetch(base+'/api/candles?interval=15min');
  assert.equal(candles.status,503);
  console.log('PASS public review demo: UI served, V3 WAIT/STANDBY, provider off, no price fabricated, candles unavailable, trading disabled');
 }finally{
  child.kill('SIGTERM');
 }
}
main().catch(error=>{console.error(error);process.exitCode=1;});
