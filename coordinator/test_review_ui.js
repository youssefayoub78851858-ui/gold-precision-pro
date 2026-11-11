'use strict';
// Deterministic controller test. Local browser testing is reported separately.
const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict');
async function check(status,body,reject=false){
 const nodes={};let handler,requests=[];
 const node=id=>nodes[id]??(nodes[id]={textContent:'',disabled:false,children:[],replaceChildren(){this.children=[]},appendChild(x){this.children.push(x)},addEventListener(_,f){handler=f}});
 const context={document:{getElementById:node,createElement:()=>({textContent:''})},window:{GOLD_API_BASE:'https://review.invalid'},AbortSignal:{timeout:()=>null},fetch:async url=>{requests.push(url);if(reject)throw Error('Network disconnected');return {ok:status<400,json:async()=>body}}};
 vm.runInNewContext(fs.readFileSync(require('node:path').join(__dirname,'../review-ui.js'),'utf8'),context);
 assert.equal(requests.length,0);await handler();assert.equal(requests[0],'https://review.invalid/api/v3/research');assert.equal(nodes['decision-state'].textContent,'WAIT');assert.equal(nodes['analyze-v2-button'].disabled,false);return nodes;
}
(async()=>{
 for(const s of ['FRESH','STALE','INVALID','STANDBY','UNAVAILABLE','MARKET_CLOSED']){
  const n=await check(['STANDBY','UNAVAILABLE'].includes(s)?503:200,{engine:'V3',signal:'WAIT',executable:false,dataStatus:s,reason:'Verified reason for '+s});assert.match(n['decision-detail'].textContent,new RegExp(s));
 }
 const n=await check(200,{signal:'BUY',engine:'Gold Precision Pro V2'});assert.match(n['decision-detail'].textContent,/V3/);
 const f=await check(0,null,true);assert.match(f['decision-detail'].textContent,/Network disconnected/);
 const c=await check(200,{engine:'V3',signal:'WAIT',executable:false,dataStatus:'FRESH',reason:'Research only',candidate:'SELL',observedUTC:'2026-11-10T09:00:05.000Z',candles:{'15min':{close:4100.1,closeUTC:'2026-11-10T09:00:00.000Z',ageAfterCloseSeconds:5}}});assert.match(c['gold-analysis-results'].children.at(-1).textContent,/ليس إشارة تداول/);assert.equal(c['gold-live-price'].textContent,'$4,100.10');assert.match(c['gold-price-updated'].textContent,/2026-11-10T09:00:00.000Z/);assert.match(c['gold-price-checked'].textContent,/2026-11-10T09:00:05.000Z/);assert.match(c['gold-price-source'].textContent,/ليس سعراً لحظياً/);
 const standby=await check(503,{engine:'V3',signal:'WAIT',executable:false,dataStatus:'STANDBY',reason:'Provider disabled',observedUTC:'2026-11-10T09:00:05.000Z'});assert.equal(standby['gold-live-price'].textContent,'غير متاح');assert.match(standby['gold-price-source'].textContent,/Standby/);
 const html=fs.readFileSync(require('node:path').join(__dirname,'../index.html'),'utf8');assert.ok(!html.includes('gold-precision-pro.onrender.com'));assert.ok(html.includes('review-ui.js'));assert.ok(html.includes('gold-price-updated'));assert.ok(html.includes('gold-price-checked'));assert.ok(!fs.readFileSync(require('node:path').join(__dirname,'../review-ui.js'),'utf8').includes('setInterval'));
 const ultimate=fs.readFileSync(require('node:path').join(__dirname,'../ultimate.html'),'utf8');assert.ok(ultimate.includes('id="r2-alert-status"'));assert.ok(ultimate.includes('id="r2-alerts"'));assert.ok(ultimate.includes('alerts.delivery'));assert.ok(ultimate.includes('لا يوجد إشعار فوري أو بريد'));
 console.log('PASS V3 review UI: correct endpoint, no automatic quote request, WAIT reasons, errors, legacy refusal, research candidate separated');
})().catch(e=>{console.error(e);process.exitCode=1});
