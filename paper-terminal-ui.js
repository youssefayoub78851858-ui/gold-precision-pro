'use strict';
(function(){
const C=window.GoldPaperCore;
if(!C){return;}
const $=id=>document.getElementById(id);
const KEY='gold-paper-terminal-offline-v1';
let state=null,tf='M15',analysis=null;
const fmt=n=>Number.isFinite(n)?Number(n).toFixed(2):'—';
function msg(t){$('paper-message').textContent=t;}
function persist(){
 if(!state)return;
 try{const content=JSON.stringify(state);if(content.length<1100000)localStorage.setItem(KEY,content);
 else msg('الملف كبير للحفظ المحلي. استخدم تصدير السجل.');}
 catch(_){msg('تعذّر الحفظ في المتصفح. صدّر السجل للاحتفاظ بالصفقات.');}
}
function frameRows(){if(!state)return [];return C.group(state.dataset.bars.slice(0,state.cursor+1),tf);}
function draw(){
 const canvas=$('chart'),ctx=canvas.getContext('2d');
 const dpr=Math.min(2,window.devicePixelRatio||1),width=Math.max(280,canvas.clientWidth),height=canvas.clientHeight||260;
 canvas.width=Math.round(width*dpr);canvas.height=Math.round(height*dpr);ctx.setTransform(dpr,0,0,dpr,0,0);
 ctx.fillStyle='#0d1a2c';ctx.fillRect(0,0,width,height);
 const rows=frameRows().slice(-44);
 if(!rows.length){ctx.fillStyle='#a7bbd6';ctx.font='15px system-ui';ctx.textAlign='center';ctx.fillText('لا توجد شموع مغلقة للعرض',width/2,height/2);return;}
 let lo=Math.min(...rows.map(x=>x.bid.low)),hi=Math.max(...rows.map(x=>x.ask.high));
 const range=Math.max(1,hi-lo);lo-=range*.10;hi+=range*.10;
 const right=64,left=14,top=20,bottom=30,plotW=width-left-right,plotH=height-top-bottom;
 const y=n=>top+(hi-n)/(hi-lo)*plotH;
 ctx.font='11px system-ui';ctx.textAlign='right';ctx.strokeStyle='#304054';ctx.fillStyle='#90a5c4';
 for(let i=0;i<=4;i++){const price=lo+(hi-lo)*i/4,Y=y(price);ctx.beginPath();ctx.moveTo(left,Y);ctx.lineTo(width-right+4,Y);ctx.stroke();ctx.fillText(fmt(price),width-5,Y+4);}
 const step=plotW/rows.length;
 for(let i=0;i<rows.length;i++){
  const r=rows[i],p=r.bid,X=left+step*(i+.5),up=p.close>=p.open;
  ctx.strokeStyle=up?'#43cba6':'#e07f8c';ctx.fillStyle=ctx.strokeStyle;
  ctx.beginPath();ctx.moveTo(X,y(p.high));ctx.lineTo(X,y(p.low));ctx.stroke();
  const Y=Math.min(y(p.open),y(p.close)),h=Math.max(1,Math.abs(y(p.open)-y(p.close)));
  ctx.fillRect(X-Math.max(1,step*.28),Y,Math.max(2,step*.56),h);
 }
 ctx.fillStyle='#9aacc5';ctx.textAlign='left';ctx.fillText(rows[0].time.slice(5,16).replace('T',' '),left,height-10);
 ctx.textAlign='right';ctx.fillText(rows.at(-1).time.slice(5,16).replace('T',' '),width-right,height-10);
}
function render(){
 const loaded=!!state;
 $('source-kind').textContent=!loaded?'لا توجد شموع':state.dataset.dataOrigin==='SYNTHETIC_TEST_ONLY'?'اصطناعي · اختبار فقط':'مسجّل · غير موثّق';
 $('live-badge').textContent='WAIT · بيانات حية غير متصلة';$('live-decision').textContent='WAIT';
 $('live-price').textContent='غير متصل';$('live-time').textContent='غير متاح';
 if(loaded){const q=C.quote(state);$('replay-bidask').textContent=fmt(q.bid)+' / '+fmt(q.ask);$('replay-time').textContent=q.closeUTC.replace('T',' ').slice(0,19)+' UTC';
  $('chart-note').textContent='إعادة تاريخية على '+state.dataset.source+' — '+(state.cursor+1)+' / '+state.dataset.bars.length+' شمعة M15. الشارت ليس حياً.';
 }else{$('replay-bidask').textContent='— / —';$('replay-time').textContent='—';$('chart-note').textContent='اختر عينة اختبار أو ملف Bid/Ask مغلق. لا توجد أسعار حية.';}
 $('next').disabled=!loaded||state.cursor>=state.dataset.bars.length-1;
 $('levels').disabled=!loaded||state.position!==null;
 $('paper-buy').disabled=!loaded||!!state.position||state.cursor>=state.dataset.bars.length-1;
 $('paper-sell').disabled=$('paper-buy').disabled;
 $('paper-close').disabled=!loaded||!state.position;
 $('inspect').disabled=!loaded||state.dataset.dataOrigin!=='SYNTHETIC_TEST_ONLY';
 $('export-journal').disabled=!loaded;
 if(state){const q=C.quote(state),pos=state.position;
  $('position-status').textContent=pos?('ورقي فقط: '+pos.side+' · دخول '+fmt(pos.entry)+' · SL '+fmt(pos.stop)+' · TP1/2/3 '+pos.tp.map(fmt).join(' / ')):'لا توجد صفقة ورقية مفتوحة.';
  const x=C.stats(state);
  $('stat-balance').textContent='$'+fmt(x.balance);$('stat-net').textContent='$'+fmt(x.net);$('stat-count').textContent=String(x.closed);$('stat-win').textContent=fmt(x.winRatePct)+'%';$('stat-dd').textContent=fmt(x.maxDrawdownPct)+'%';$('stat-pf').textContent=x.profitFactor===null?'—':fmt(x.profitFactor);
  const tbody=$('trade-rows');tbody.replaceChildren();
  if(!state.trades.length){const tr=document.createElement('tr'),td=document.createElement('td');td.colSpan=6;td.textContent='لا توجد صفقات بعد';tr.appendChild(td);tbody.appendChild(tr);}
  for(const trade of state.trades.slice(-25).reverse()){
   const tr=document.createElement('tr');
   for(const value of [trade.side,fmt(trade.entry),fmt(trade.exit),fmt(trade.net),trade.reason,trade.closedUTC]){
    const td=document.createElement('td');td.textContent=String(value);tr.appendChild(td);
   }tbody.appendChild(tr);
  }
 }else{$('position-status').textContent='لا توجد صفقة مفتوحة.';}
 draw();
}
function initialize(dataset){state=C.defaultSession(C.validate(dataset));analysis=null;$('research-output').textContent='WAIT — محرك V3 لم يجرِ فحص هذه العينة. مصادر DXY/GC/الأخبار/Order Flow غير متاحة.';persist();render();}
function field(id){const x=$ (id).value.trim();return x===''?NaN:Number(x);}
function paperTrade(side){
 try{if(!state)throw Error('لا توجد بيانات محلية');C.open(state,side,field('stop'),[field('tp1'),field('tp2'),field('tp3')]);persist();render();msg('تم فتح صفقة '+side+' ورقية محلية — ليست أمراً لدى وسيط.');}
 catch(err){msg('لم تُفتح الصفقة: '+err.message);}
}
$('paper-buy').addEventListener('click',()=>paperTrade('BUY'));
$('paper-sell').addEventListener('click',()=>paperTrade('SELL'));
$('paper-close').addEventListener('click',()=>{
 try{C.close(state);persist();render();msg('أُغلقت الصفقة الورقية عند سعر إعادة الشمعة.');}catch(e){msg(e.message);}
});
$('next').addEventListener('click',()=>{
 try{C.advance(state);persist();render();msg('انتقلت لشمعة M15 مغلقة جديدة. سعر مباشر: غير متاح.');}
 catch(e){msg(e.message);}
});
$('levels').addEventListener('click',()=>{
 if(!state||state.position)return;
 const q=C.quote(state),bidRows=state.dataset.bars.slice(Math.max(0,state.cursor-13),state.cursor+1).map(x=>x.bid);
 const radius=Math.max(.7,bidRows.reduce((a,x)=>a+x.high-x.low,0)/Math.max(1,bidRows.length));
 // These are an illustration for a BUY paper scenario, NOT an engine signal.
 $('stop').value=fmt(q.ask-radius*1.6);
 $('tp1').value=fmt(q.ask+radius);
 $('tp2').value=fmt(q.ask+2*radius);
 $('tp3').value=fmt(q.ask+3*radius);
 msg('تم تعبئة مستويات BUY ورقية تجريبية فقط. يمكنك تعديلها أو تجربة SELL بمستويات معاكسة. ليست توصية.');
});
$('sample').addEventListener('click',()=>{
 if(state?.position&&!window.confirm('لديك صفقة ورقية مفتوحة. بدء عينة جديدة يمحو جلسة المحاكاة الحالية. هل تريد المتابعة؟'))return;
 initialize(C.sample());msg('تم تحميل 512 شمعة اصطناعية مغلقة؛ يمكنك تحريك الإعادة وفتح صفقات ورقية.');
});
$('file-input').addEventListener('change',async()=>{
 try{const f=$('file-input').files?.[0];if(!f)return;if(f.size>950000)throw Error('ملف كبير، الحد 950KB');
  const payload=JSON.parse(await f.text());if(payload.dataOrigin!=='RECORDED_UNVERIFIED')throw Error('للتسجيل التاريخي استخدم dataOrigin=RECORDED_UNVERIFIED؛ لا يمكن ادعاء بيانات حية');
  if(state?.position&&!window.confirm('هذا يمحو جلسة محاكاة بها صفقة مفتوحة. هل تتابع؟'))return;
  initialize(payload);msg('ملف مسجّل محلياً؛ حقوق المصدر ومصداقيته غير محققتين. القرار الحي WAIT.');
 }catch(err){msg('لم يُقبل الملف: '+err.message);}
});
for(const button of document.querySelectorAll('button[data-tf]'))button.addEventListener('click',()=>{tf=button.dataset.tf;$('active-tf-label').textContent=tf;document.querySelectorAll('button[data-tf]').forEach(b=>b.classList.toggle('active',b===button));draw();});
$('inspect').addEventListener('click',async()=>{
 if(!state||state.dataset.dataOrigin!=='SYNTHETIC_TEST_ONLY')return;
 const button=$('inspect');button.disabled=true;$('research-output').textContent='جاري فحص بيانات الاختبار فقط بمحرك V3...';
 try{
  const payload={...state.dataset,bars:state.dataset.bars.slice(0,state.cursor+1)};
  const response=await fetch('/api/v3/paper/inspect',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),credentials:'omit',cache:'no-store',signal:AbortSignal.timeout(10000)});
  if(!response.ok)throw Error('خادم التحليل غير متوفر أو النسخة غير منشورة');
  const r=await response.json();
  if(r.mode!=='OFFLINE_SYNTHETIC_REPLAY'||r.signal!=='WAIT'||r.executable!==false||r.researchEligible!==false||r.connectedRealMarketData!==false||r.providerRequests!==0||r.ordersSent!==0)throw Error('رد محرك غير آمن');
  analysis=r;
  for(const x of ['M15','H1','H4'])$('bias-'+x.toLowerCase()).textContent=r.structure?.[x]?.bias||'غير متاح';
  const obs=(r.structure?.M15||{}),ind=r.indicators||{};
  $('research-output').textContent='قرار V3: WAIT (المصادر الخارجية ناقصة)\n'+
   'EMA20: '+fmt(ind.ema20)+' · EMA50: '+fmt(ind.ema50)+' · RSI14: '+fmt(ind.rsi14)+' · ATR14: '+fmt(ind.atr14)+'\n'+
   'BOS صعود/هبوط: '+(obs.bosUp?'نعم':'لا')+'/'+(obs.bosDown?'نعم':'لا')+
   ' · CHoCH: '+(obs.chochUp||obs.chochDown?'مرصود':'غير مرصود')+
   ' · Liquidity sweep: '+(obs.sweepHigh||obs.sweepLow?'مرصود':'غير مرصود')+
   ' · FVG: '+(obs.fvgBull||obs.fvgBear?'مرصود':'غير مرصود')+'\n'+
   'VWAP وOrder Block: غير موثّقين.\n'+
   'المصادر المفقودة: '+r.blocked.join('، ')+'\nتحليل تاريخي/اصطناعي فقط، لا توصية قابلة للتنفيذ.';
 }catch(e){$('research-output').textContent='WAIT — تعذّر الفحص: '+e.message;}
 finally{button.disabled=false;}
});
$('export-journal').addEventListener('click',()=>{
 if(!state)return;
 const exportData={mode:'LOCAL_PAPER_REPLAY',liveData:false,executable:false,source:state.dataset.source,dataOrigin:state.dataset.dataOrigin,
  costs:C.COSTS,cursor:state.cursor,stats:C.stats(state),position:state.position,trades:state.trades,
  note:'Private offline paper test only; no trading broker or verified returns.'};
 const blob=new Blob([JSON.stringify(exportData,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='gold-paper-journal.json';a.click();URL.revokeObjectURL(url);
});
$('reset').addEventListener('click',()=>{if(!window.confirm('مسح كل بيانات وجلسة التداول الورقي المحفوظة في هذا المتصفح؟'))return;state=null;analysis=null;try{localStorage.removeItem(KEY);}catch(_){ }render();msg('تم مسح جلسة المحاكاة المحلية.');});
window.addEventListener('resize',draw,{passive:true});
try{const saved=localStorage.getItem(KEY);if(saved&&saved.length<1100000){state=C.checkedSession(JSON.parse(saved));msg('تمت استعادة جلسة ورقية محلية سابقة، وليست أسعار حية.');}}catch(_){state=null;msg('جلسة المتصفح السابقة غير صالحة؛ ابدأ عينة جديدة.');}
render();
})();
