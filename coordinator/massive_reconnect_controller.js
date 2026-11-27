'use strict';
// Bounded reconnect controller for the read-only probe. Disabled by default.
// No background launch, provider selection, trading, or entitlement claims.
// A future operator must authorize a real session separately. A gap never
// implies recovered history; consumers must requalify continuity themselves.
const {probe}=require('./massive_readonly_probe');
const retryable=new Set(['SOCKET_ERROR','SOCKET_CLOSED','SOCKET_SETUP_FAILED',
 'HANDSHAKE_TIMEOUT_OR_CLOCK','QUOTE_IDLE_OR_CLOCK','NO_QUOTES_OBSERVED']);
async function reconnect({authorized=false,credential,runProbe=probe,
 sleep=ms=>new Promise(r=>setTimeout(r,ms)),maxAttempts=3,signal,onQuote}={}){
 const report=(status,attempts,delays)=>({status,attempts,delaysMs:delays,
  historyContinuityVerified:false,realDataQualificationProven:false,
  signal:'WAIT',executable:false,paperOrdersAllowed:false,liveOrdersAllowed:false});
 if(authorized!==true)return report('NOT_AUTHORIZED',0,[]);
 if(typeof credential!=='string'||!credential||credential.length>4096||
    typeof runProbe!=='function'||typeof sleep!=='function'||
    !Number.isInteger(maxAttempts)||maxAttempts<1||maxAttempts>5||
    (onQuote!==undefined&&typeof onQuote!=='function'))
  return report('INVALID_CONFIGURATION',0,[]);
 const delays=[];
 for(let i=1;i<=maxAttempts;i++){
  if(signal?.aborted)return report('CANCELLED',i-1,delays);
  let r;
  try{r=await runProbe({authorized:true,credential,onQuote});}
  catch{return report('PROBE_FAILED',i,delays);}
  if(signal?.aborted)return report('CANCELLED',i,delays);
  if(!retryable.has(r?.status))return report(
   r?.status==='BOUNDED_OBSERVATION_ENDED_NOT_QUALIFIED'?
   'OBSERVATION_ENDED_NOT_QUALIFIED':'STOPPED_NON_RETRYABLE',i,delays);
  if(i===maxAttempts)return report('RETRY_LIMIT_REACHED',i,delays);
  const delay=Math.min(30000,1000*2**(i-1));
  delays.push(delay);
  try{await sleep(delay);}catch{return report('RETRY_DELAY_FAILED',i,delays);}
 }
 return report('RETRY_LIMIT_REACHED',maxAttempts,delays);
}
module.exports={reconnect};
