'use strict';
// Public-package installation smoke in disposable GitHub CI only.
// Never import/execute FXCM SDK, log into broker, fetch quotes, or send orders.
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const cp=require('node:child_process');
const PACKAGE='@gehtsoft/forex-connect-lite-node';
const REGISTRY='https://www.myget.org/F/gehtsoft-public/npm/';
function probe(){
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'fxcm-fclite-public-npm-'));
 const safeEnv={PATH:process.env.PATH||'/usr/bin:/bin',HOME:root,CI:'true',
  NPM_CONFIG_USERCONFIG:'/dev/null',
  NPM_CONFIG_CACHE:path.join(root,'npm-cache'),NPM_CONFIG_UPDATE_NOTIFIER:'false',
  NPM_CONFIG_AUDIT:'false',NPM_CONFIG_FUND:'false'};
 fs.writeFileSync(path.join(root,'package.json'),JSON.stringify({name:'fxcm-fclite-sandbox',version:'0.0.0',private:true}));
 fs.writeFileSync(path.join(root,'.npmrc'),'@gehtsoft:registry='+REGISTRY+'\nignore-scripts=true\naudit=false\nfund=false\n');
 const result=cp.spawnSync('npm',['install',PACKAGE,'--ignore-scripts','--no-audit',
  '--no-fund','--no-save','--fetch-retries=0','--fetch-timeout=12000'],{
  cwd:root,env:safeEnv,encoding:'utf8',timeout:45000,maxBuffer:512*1024,stdio:'pipe'});
 const pkgFile=path.join(root,'node_modules','@gehtsoft','forex-connect-lite-node','package.json');
 let metadata=null;
 if(fs.existsSync(pkgFile)){
  const pkg=JSON.parse(fs.readFileSync(pkgFile,'utf8'));
  metadata={name:pkg.name,version:pkg.version,engines:pkg.engines??null,main:pkg.main??null};
 }
 const success=result.status===0&&metadata?.name===PACKAGE;
 const stderr=(result.stderr||'').slice(-2000).replace(/https?:\/\/[^\s]+:[^\s]+@/g,'[REDACTED]');
 const outcome={mode:'PUBLIC_PACKAGE_METADATA_ONLY',package:PACKAGE,registry:REGISTRY,
  node:process.version,os:process.platform,arch:process.arch,
  status:success?'INSTALLED_NO_SCRIPTS':'BLOCKED_NOT_VERIFIED',
  packageFetchedAndUnpacked:success,sdkModuleLoaded:false,installScriptsExecuted:false,
  fxcmAccountUsed:false,fxcmMarketRequests:0,tradeOrders:0,paidCharges:0,
  metadata,exitCode:result.status,timeout:result.error?.code==='ETIMEDOUT',
  errorCode:result.error?.code||null,errorSummary:success?null:stderr.slice(-700)};
 const output=process.env.GITHUB_OUTPUT_DIR||path.join(root,'fxcm-package-probe.json');
 fs.mkdirSync(path.dirname(output),{recursive:true});
 fs.writeFileSync(output,JSON.stringify(outcome,null,2)+'\n');
 console.log(JSON.stringify({...outcome,errorSummary:outcome.errorSummary?.slice(-400)}));
 if(process.env.GITHUB_STEP_SUMMARY){
  fs.appendFileSync(process.env.GITHUB_STEP_SUMMARY,
   '\n### FXCM FCLite public-package smoke\n- Result: '+outcome.status+'\n- Install scripts: disabled\n- SDK login, trading, market requests: not attempted\n- See JSON artifact for details.\n');
 }
 fs.rmSync(root,{recursive:true,force:true});
 return outcome;
}
if(require.main===module)probe();
module.exports={probe};
