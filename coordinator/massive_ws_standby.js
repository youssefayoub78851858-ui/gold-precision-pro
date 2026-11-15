'use strict';
// Massive forex BBO WebSocket PROTOCOL REHEARSAL ONLY.
// No WebSocket, fetch, env variables, API keys, storage, broker or service
// connection is created in this file, including when imported.
// Real personal data on Render remains forbidden absent rights and operator approval.
const WIDTH=900000,MAX_AGE_MS=30000,FUTURE_TOLERANCE_MS=5000;
const MAX_QUOTE_GAP_MS=90000,OPEN_CLOSE_MARGIN_MS=60000,IDLE_MS=180000;
const MAX_CLOSED=2048,MAX_FRAME_CHARS=65536;
const SYMBOL='XAU/USD',TOPIC='C.XAU-USD';
function validPrice(x){return typeof x==='number'&&Number.isFinite(x)&&x>0;}
function aggregate(items,n){
 const width=WIDTH*n,map=new Map();
 for(const c of items){const s=Math.floor(Date.parse(c.openTime)/width)*width;if(!map.has(s))map.set(s,[]);map.get(s).push(c);}
 return [...map].sort((a,b)=>a[0]-b[0]).flatMap(([s,rows])=>{
  if(rows.length!==n||rows.some((c,i)=>Date.parse(c.openTime)!==s+i*WIDTH))return [];
  return [{openTime:new Date(s).toISOString(),open:rows[0].open,
   high:Math.max(...rows.map(c=>c.high)),low:Math.min(...rows.map(c=>c.low)),close:rows.at(-1).close}];
 });
}
const safeClock=x=>typeof x==='number'&&Number.isFinite(x)&&x>0;
function transportPlan(){
 return Object.freeze({
  provider:'Massive',instrument:'XAU/USD',restTicker:'C:XAUUSD',
  websocketPair:SYMBOL,websocketTopic:TOPIC,
  documentedEndpoint:'wss://socket.massive.com/forex',
  sequence:'CONNECT_THEN_AUTH_THEN_SUBSCRIBE',
  sampleOnly:true,mode:'OFFLINE_PROTOCOL_REHEARSAL_ONLY',
  socketOpened:false,transportImplemented:false,connectionApproved:false,
  entitlementVerified:false,cloudLicenseVerified:false,credentialsRead:false,
  networkRequestsMade:0,ordersSent:0,signal:'WAIT',executable:false
 });
}
function newBar(t,v){return {openTime:new Date(t).toISOString(),open:v,high:v,low:v,close:v};}
function extend(bar,value){bar.high=Math.max(bar.high,value);bar.low=Math.min(bar.low,value);bar.close=value;}
class MassiveQuoteStandby{
 constructor(clock=Date.now){
  if(typeof clock!=='function')throw Error('Independent clock required');
  this.clock=clock;this.closed={bid:[],ask:[],mid:[]};
  this.mode='NOT_CONNECTED';this.reason='OFFLINE_STANDBY';this.authenticated=false;
  this.subscribed=false;this.lastTs=null;this.lastReceivedAt=null;this.current=null;this.connectedAt=null;
  this.lastQuote=null;this.count=0;this.malformed=0;this.discarded=0;
 }
 disconnect(reason='OFFLINE_DISCONNECTED'){
  this.mode='NOT_CONNECTED';this.reason=reason;this.authenticated=false;
  this.subscribed=false;this.lastTs=null;this.lastReceivedAt=null;this.current=null;this.connectedAt=null;
  this.lastQuote=null;
  return {kind:'blocked',reason,signal:'WAIT',executable:false};
 }
 expired(now=this.clock()){
  if(!safeClock(now))return true;
  // No-quote sockets after auth are not a healthy connection.
  const reference=this.lastReceivedAt??this.connectedAt;
  return reference!==null&&(now<reference||now-reference>=IDLE_MS);
 }
 checkIdle(now=this.clock()){
  if(this.expired(now))return this.disconnect('QUOTE_STREAM_SILENT');
  return {kind:'wait',reason:this.reason,signal:'WAIT',executable:false};
 }
 handle(input){
  let events=input;
  if(typeof input==='string'){
   if(input.length>MAX_FRAME_CHARS)return this.disconnect('FRAME_SIZE_EXCEEDED');
   try{events=JSON.parse(input);}catch{this.malformed++;return this.disconnect('INVALID_JSON');}
  }
  const batch=Array.isArray(events)?events:[events];
  if(batch.length<1||batch.length>2000||batch.some(x=>!x||typeof x!=='object'||Array.isArray(x)))
   return this.disconnect('INVALID_FRAME');
  const replies=[];
  for(const item of batch){
   const reply=item.ev==='status'?this.status(item):item.ev==='C'?this.quote(item):{kind:'ignored'};
   replies.push(reply);
   if(reply.kind==='blocked')break;
  }
  return replies.length===1?replies[0]:replies;
 }
 status(item){
  if(item.status==='auth_success'){
   if(this.authenticated)return this.disconnect('REPEATED_AUTH_HANDSHAKE');
   const now=this.clock();
   if(!safeClock(now))return this.disconnect('INVALID_AUTH_CLOCK');
   this.connectedAt=now;
   this.authenticated=true;this.mode='AUTHENTICATED_WAIT_SUBSCRIPTION';
   this.reason='WAIT_SUBSCRIPTION';
   return {kind:'authenticated',allowedNextAction:'SUBSCRIBE_AFTER_AUTH_ONLY',
           topic:TOPIC,signal:'WAIT',executable:false};
  }
  if(item.status==='success'&&typeof item.message==='string'&&
     item.message.trim()==='subscribed to: '+TOPIC&&this.authenticated){
   this.subscribed=true;this.mode='SYNTHETIC_SUBSCRIPTION_ONLY';
   this.reason='WAIT_NO_REAL_SOURCE_OR_LICENSE';
   return {kind:'subscribed',signal:'WAIT',executable:false};
  }
  if(item.status==='auth_failed'||item.status==='error'||item.status==='max_connections'||
     item.status==='not_authorized'||item.status==='unauthorized'){
   return this.disconnect('AUTH_OR_ENTITLEMENT_REFUSED');
  }
  // A TCP handshake, "connected", unrelated channel or a status=success
  // is NOT proof of stream entitlement or actual market activity.
  return {kind:'ignored',signal:'WAIT',executable:false};
 }
 quote(item){
  if(item.p!==SYMBOL)return {kind:'ignored',signal:'WAIT',executable:false};
  if(!this.authenticated||!this.subscribed)return this.disconnect('QUOTE_BEFORE_SUBSCRIPTION');
  const now=this.clock();
  if(this.expired(now))return this.disconnect('QUOTE_STREAM_SILENT');
  if(!safeClock(now)||!Number.isSafeInteger(item.t)||item.t<=0||
     now-item.t>MAX_AGE_MS||item.t>now+FUTURE_TOLERANCE_MS)
   return this.disconnect('STALE_OR_FUTURE_QUOTE');
  if(!validPrice(item.a)||!validPrice(item.b)||item.a<item.b)
   return this.disconnect('INVALID_OR_CROSSED_BBO');
  if(this.lastTs!==null&&(item.t<this.lastTs||item.t-this.lastTs>MAX_QUOTE_GAP_MS))
   return this.disconnect('REVERSED_OR_GAPPED_QUOTE');
  const start=Math.floor(item.t/WIDTH)*WIDTH,bid=item.b,ask=item.a,mid=(bid+ask)/2;
  if(this.current&&this.current.start!==start){
   const prev=this.current;
   if(start!==prev.start+WIDTH||prev.first>prev.start+OPEN_CLOSE_MARGIN_MS||
      prev.last<prev.start+WIDTH-OPEN_CLOSE_MARGIN_MS){
    this.discarded++;
    return this.disconnect('INCOMPLETE_OR_DISCONTINUOUS_M15');
   }
   for(const basis of ['bid','ask','mid']){
    const list=this.closed[basis];list.push(prev[basis]);
    if(list.length>MAX_CLOSED)list.shift();
   }
   this.current=null;
  }
  if(!this.current){
   this.current={start,first:item.t,last:item.t,bid:newBar(start,bid),
       ask:newBar(start,ask),mid:newBar(start,mid)};
  }else{
   this.current.last=item.t;extend(this.current.bid,bid);
   extend(this.current.ask,ask);extend(this.current.mid,mid);
  }
  // Multiple distinct bank quotes can share a millisecond; keep receipt
  // order, as in historical /v3/quotes. Never call this trade volume.
  this.lastTs=item.t;this.lastReceivedAt=now;this.count++;
  this.lastQuote={timestampUTC:new Date(item.t).toISOString(),bid,ask};
  this.reason='WAIT_INDEPENDENT_SOURCE_VALIDATION';
  return {kind:'synthetic_quote',signal:'WAIT',executable:false};
 }
 snapshot(){
  const frames=family=>({
   M15:this.closed[family].map(c=>({...c})),
   H1:aggregate(this.closed[family],4),H4:aggregate(this.closed[family],16)
  });
  return {
   provider:'Massive',mode:'OFFLINE_SYNTHETIC_REVIEW_ONLY',
   sourceDataMode:'SYNTHETIC_TEST_ONLY',instrument:'XAU/USD',signal:'WAIT',
   executable:false,researchEligible:false,paperOrdersAllowed:false,
   liveTradingAllowed:false,providerRequestsMade:0,ordersSent:0,
   historicalLiveParityVerified:false,independentSessionCalendarVerified:false,
   cloudRightsVerified:false,entitlementVerified:false,
   lastKnownQuoteIsReal:false,quoteActivityIsTradeVolume:false,
   subscribedToActualProvider:false,reason:this.reason,
   syntheticStatus:this.mode,syntheticFramesProcessed:this.count,
   incompleteM15Discarded:this.discarded,
   lastSyntheticQuote:this.lastQuote&&{...this.lastQuote},
   frames:frames('mid'),bidFrames:frames('bid'),askFrames:frames('ask')
  };
 }
}
module.exports={MassiveQuoteStandby,transportPlan,aggregate};
if(require.main===module){
 process.stdout.write(JSON.stringify(transportPlan())+'\n');
}
