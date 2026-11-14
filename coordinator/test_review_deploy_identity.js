'use strict';
const assert=require('node:assert/strict');
const {inspect}=require('./review_deploy_identity');
const sha='1234567890abcdef1234567890abcdef12345678';
const good={RENDER:'true',RENDER_GIT_COMMIT:sha,
 RENDER_GIT_BRANCH:'review/v2-portable-tests-20261109',
 RENDER_SERVICE_NAME:'gold-precision-v3-review-demo'};
function safe(x){
 assert.equal(x.mode,'DEMO_STANDBY');
 assert.equal(x.signal,'WAIT');
 assert.equal(x.executable,false);
 assert.equal(x.tradingEnabled,false);
 assert.equal(x.providerAccess,false);
 assert.equal(x.marketRequests,0);
 assert.equal(x.licensedFXCM,false);
 for(const k of Object.keys(x))assert(!/token|password|secret|apiKey/i.test(k),k);
}
let x=inspect(good);safe(x);
assert.equal(x.status,'REVIEW_REVISION_VERIFIED');
assert.equal(x.buildCommit,sha);assert.equal(x.buildShort,sha.slice(0,8));
assert.equal(x.deploymentIdentityVerified,true);
for(const corrupt of [
 {RENDER:'false'},
 {RENDER_GIT_COMMIT:'notsha'},
 {RENDER_GIT_COMMIT:'a'.repeat(41)},
 {RENDER_GIT_COMMIT:undefined},
 {RENDER_GIT_BRANCH:'main'},
 {RENDER_SERVICE_NAME:'gold-precision-pro'},
 {RENDER_SERVICE_NAME:undefined}
]){
 const z=inspect({...good,...corrupt});safe(z);
 assert.equal(z.status,'REVIEW_REVISION_UNVERIFIED');
 assert.equal(z.deploymentIdentityVerified,false);
 assert.equal(z.buildCommit,null);assert.equal(z.buildShort,null);assert.equal(z.branch,null);
}
safe(inspect({}));
console.log('PASS: verified Render commit identity, wrong branch/service rejected, no market, no secrets');
