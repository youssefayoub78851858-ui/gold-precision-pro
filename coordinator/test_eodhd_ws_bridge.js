'use strict';
const a=require('node:assert/strict');
const {XauusdReview,aggregate}=require('./eodhd_ws_bridge');
const base=1794493813003,quote=(t,ask=3903.04,bid=3902.46)=>({s:'XAUUSD',a:ask,b:bid,t});
let now=base,review=new XauusdReview(()=>now+1000);
a.equal(review.receive(quote(base)).reason,'AUTHORIZATION_MISSING');
a.equal(review.receive({status_code:200}).kind,'authorized');
a.equal(review.receive(quote(base)).kind,'quote');
a.equal(review.snapshot().signal,'WAIT');
a.equal(review.snapshot().executable,false);
a.equal(review.snapshot().frames.M15.length,0);
review=new XauusdReview(()=>base+1000);review.receive({status_code:200});
a.equal(review.receive(quote(base,3902,3903)).reason,'INVALID_QUOTE');
review=new XauusdReview(()=>base+1000);review.receive({status_code:200});
a.equal(review.receive(quote(base-100000)).reason,'STALE_OR_FUTURE');
review=new XauusdReview(()=>base+1000);review.receive({status_code:200});
review.receive(quote(base));a.equal(review.receive(quote(base)).reason,'TICK_GAP_OR_ORDER');
a.equal(review.snapshot().frames.M15.length,0);
review=new XauusdReview(()=>base+1000);review.receive({status_code:200});
a.equal(review.receive({status_code:422}).reason,'PROVIDER_STATUS_422');
review=new XauusdReview(()=>base+1000);review.receive({status_code:200});
a.equal(review.receive('{invalid').reason,'INVALID_JSON');
const start=Math.floor(base/(16*900000))*(16*900000);
review=new XauusdReview(()=>now+1000);review.receive({status_code:200});
for(let i=0;i<16;i++){
 const s=start+i*900000;
 for(let j=1;j<=29;j++){now=s+j*30000;a.equal(review.receive(quote(now)).kind,'quote');}
 now=s+899000;a.equal(review.receive(quote(now)).kind,'quote');
}
now=start+16*900000+1000;
a.equal(review.receive(quote(now)).kind,'quote');
a.equal(review.snapshot().frames.M15.length,16);
a.equal(review.snapshot().frames.H1.length,4);
a.equal(review.snapshot().frames.H4.length,1);
a.equal(review.snapshot().researchEligible,false);
review.reset();a.equal(review.snapshot().frames.M15.length,0);
a.equal(aggregate([],4).length,0);
console.log('PASS: EODHD offline quote checks, complete UTC candles and WAIT');
