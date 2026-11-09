'use strict';
const {admit,duration,stamp}=require('./timing');
const {marketOpen}=require('./app/paper-core');
let input='';process.stdin.on('data',x=>input+=x);process.stdin.on('end',()=>{
 try{const {raw,now}=JSON.parse(input),frames={};for(const f of Object.keys(duration)){if(raw[f]?.symbol!=='XAU/USD')throw Error('Invalid symbol');frames[f]=raw[f].values.slice().sort((a,b)=>stamp(a)-stamp(b));}const g=admit(frames,now,{marketOpen:marketOpen(now)});delete g.frames;process.stdout.write(JSON.stringify(g));}
 catch(e){process.stdout.write(JSON.stringify({accepted:false,reason:'INVALID_INPUT'}));}
});
