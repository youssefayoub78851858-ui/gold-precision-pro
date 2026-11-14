'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const nodes=new Map(),tabs=[];
function makeNode(id){
 if(nodes.has(id))return nodes.get(id);
 const handlers={};const node={id,value:'',textContent:'',disabled:false,clientWidth:400,clientHeight:250,
   children:[],style:{},dataset:{},files:[],width:0,height:0,
   addEventListener:(event,fn)=>{handlers[event]=fn},
   trigger:(event='click')=>{if(!handlers[event])throw Error('Missing '+event+' handler for '+id);return handlers[event]({type:event})},
   replaceChildren(){this.children=[]},appendChild(x){this.children.push(x)},classList:{toggle(){}},
   getContext:()=>({fillRect(){},beginPath(){},moveTo(){},lineTo(){},stroke(){},fillText(){},setTransform(){},
      set fillStyle(_){},set strokeStyle(_){},set font(_){},set textAlign(_){}}),
 };
 nodes.set(id,node);return node;
}
for(const id of ['chart','paper-message','research-output','file-input','sample','next','levels','export-journal','inspect','paper-buy','paper-sell','paper-close','reset','trade-rows','replay-bidask','replay-time','source-kind','live-badge','live-decision','live-price','live-time','chart-note','position-status','stat-balance','stat-net','stat-count','stat-win','stat-dd','stat-pf','bias-m15','bias-h1','bias-h4','stop','tp1','tp2','tp3','active-tf-label'])makeNode(id);
for(const tf of ['M15','H1','H4']){let n=makeNode('tab-'+tf);n.dataset.tf=tf;tabs.push(n)}
const storage=new Map(),window={devicePixelRatio:1,confirm:()=>true,addEventListener(){}},
 document={getElementById:makeNode,querySelectorAll:()=>tabs,createElement:(tag)=>({tag,textContent:'',appendChild(){},click(){}})};
const context={window,document,localStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},
 Blob:function(){},URL:{createObjectURL:()=>'',revokeObjectURL:()=>{}},AbortSignal:{timeout:()=>null},
 fetch:()=>{throw Error('Should never auto-fetch market feed')},console};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'paper-terminal-core.js'),'utf8'),context,{timeout:1500});
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'paper-terminal-ui.js'),'utf8'),context,{timeout:1500});
assert.equal(makeNode('live-decision').textContent,'WAIT');assert.equal(makeNode('live-price').textContent,'غير متصل');
assert.equal(makeNode('sample').disabled,false);
makeNode('sample').trigger();
assert.match(makeNode('source-kind').textContent,/اصطناعي/);
assert.match(makeNode('replay-bidask').textContent,/[0-9]+/);
assert.equal(makeNode('live-price').textContent,'غير متصل');
makeNode('levels').trigger();
assert(Number(makeNode('tp1').value)>Number(makeNode('stop').value));
makeNode('paper-buy').trigger();
assert.match(makeNode('position-status').textContent,/BUY/);
assert.equal(makeNode('paper-close').disabled,false);
makeNode('next').trigger();
makeNode('paper-close').trigger();
assert.equal(makeNode('stat-count').textContent,'1');
assert(storage.has('gold-paper-terminal-offline-v1'));
const expected=JSON.parse(storage.get('gold-paper-terminal-offline-v1'));
assert.equal(expected.trades.length,1);
assert.equal(expected.dataset.dataOrigin,'SYNTHETIC_TEST_ONLY');
assert.equal(makeNode('live-decision').textContent,'WAIT');
makeNode('tab-H4').trigger();assert.equal(makeNode('active-tf-label').textContent,'H4');
makeNode('reset').trigger();assert(!storage.has('gold-paper-terminal-offline-v1'));
console.log('PASS paper terminal Android UI DOM simulation: chart, MTF, sample, manual entry/exit, stats, local recovery, WAIT');
