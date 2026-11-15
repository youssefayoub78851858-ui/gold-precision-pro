'use strict';
// Hermetic compatibility check only. Reads one synthetic JSON fixture from stdin,
// never reads credentials, starts transports, fetches data or places paper orders.
const fs=require('node:fs');
const {MassiveQuoteStandby}=require('./massive_ws_standby');
function fail(){throw Error('OFFLINE_SYNTHETIC_FIXTURE_REJECTED');}
function run(raw){
 if(typeof raw!=='string'||raw.length>4000000)fail();
 let input;
 try{input=JSON.parse(raw);}catch{fail();}
 if(!input||typeof input!=='object'||Array.isArray(input)||
    Object.keys(input).sort().join(',')!=='asOfUTC,quotes,sourceDataMode,ticker'||
    input.sourceDataMode!=='SYNTHETIC_TEST_ONLY'||input.ticker!=='C:XAUUSD'||
    !Array.isArray(input.quotes)||input.quotes.length<1||input.quotes.length>25000||
    typeof input.asOfUTC!=='string'||!/\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ/.test(input.asOfUTC))fail();
 const limit=Date.parse(input.asOfUTC);if(!Number.isFinite(limit))fail();
 let now;
 const review=new MassiveQuoteStandby(()=>now);
 const first=input.quotes[0];
 const firstRaw=first?.participant_timestamp;
 if(!/^[1-9]\d{18}$/.test(String(firstRaw)))fail();
 now=Number(BigInt(firstRaw)/1000000n)+500;
 if(review.handle({ev:'status',status:'auth_success'}).kind!=='authenticated')fail();
 if(review.handle({ev:'status',status:'success',message:'subscribed to: C.XAU-USD'}).kind!=='subscribed')fail();
 let prev=-1;
 for(const item of input.quotes){
  if(!item||typeof item!=='object'||Array.isArray(item)||
     !/^[1-9]\d{18}$/.test(String(item.participant_timestamp))||
     typeof item.bid_price!=='number'||!Number.isFinite(item.bid_price)||
     typeof item.ask_price!=='number'||!Number.isFinite(item.ask_price))fail();
  const nanos=BigInt(item.participant_timestamp);
  if(nanos%1000000n!==0n)fail(); // exact ms for cross-language WS fixture
  const time=Number(nanos/1000000n);
  if(!Number.isSafeInteger(time)||time<prev||time>=limit)fail();
  now=time+500;
  const result=review.handle({ev:'C',p:'XAU/USD',t:time,b:item.bid_price,a:item.ask_price,x:44});
  if(result.kind!=='synthetic_quote')fail();
  prev=time;
 }
 const output=review.snapshot();
 if(output.signal!=='WAIT'||output.executable!==false||
    output.researchEligible!==false||output.paperOrdersAllowed!==false||
    output.providerRequestsMade!==0||output.subscribedToActualProvider!==false)fail();
 return output;
}
if(require.main===module){
 try{const result=run(fs.readFileSync(0,'utf8'));process.stdout.write(JSON.stringify(result)+'\n');}
 catch(_err){process.stderr.write('OFFLINE_FIXTURE_REJECTED\n');process.exitCode=1;}
}
module.exports={run};
