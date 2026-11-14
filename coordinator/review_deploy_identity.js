'use strict';
// Review-demo ONLY. Render's built-in deployment metadata; no secrets or market IO.
// Validate exact branch, service name and a 40-character revision before labeling verified.
const BRANCH='review/v2-portable-tests-20261109';
const SERVICE='gold-precision-v3-review-demo';
function inspect(env=process.env){
 const revision=env.RENDER_GIT_COMMIT;
 const sha=(typeof revision==='string'&&/^[a-f0-9]{40}$/i.test(revision))
   ?revision.toLowerCase():null;
 const valid=!!sha&&env.RENDER_GIT_BRANCH===BRANCH&&
   env.RENDER_SERVICE_NAME===SERVICE&&env.RENDER==='true';
 return {
   system:'Gold Precision Pro Ultimate',
   mode:'DEMO_STANDBY',
   service:SERVICE,
   status:valid?'REVIEW_REVISION_VERIFIED':'REVIEW_REVISION_UNVERIFIED',
   buildCommit:valid?sha:null,
   buildShort:valid?sha.slice(0,8):null,
   branch:valid?BRANCH:null,
   deploymentIdentityVerified:valid,
   signal:'WAIT',executable:false,tradingEnabled:false,
   providerAccess:false,marketRequests:0,licensedFXCM:false
 };
}
module.exports={inspect};
