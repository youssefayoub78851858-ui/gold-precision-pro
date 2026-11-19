"use strict";
/*
 * Mobile BiQuote OWNER-ONLY on-demand display. It reuses the exact existing
 * signed HttpOnly viewer cookie and private read-only observation endpoint.
 * No direct vendor requests, no credentials in JS, no paper/broker orders.
 * Anonymous/expired/stale/invalid packets fail closed to WAIT with no prices.
 */
(function(){
 const WIDTH={M15:900000,H1:3600000,H4:14400000};
 const TF=["M15","H1","H4"],ISO=/^20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,3})?Z$/;
 const MAX=48;
 const time=s=>{
  if(typeof s!=="string"||!ISO.test(s))return NaN;
  const t=Date.parse(s);
  return Number.isFinite(t)&&new Date(t).toISOString().slice(0,19)===s.slice(0,19)?t:NaN;
 };
 const finite=x=>typeof x==="number"&&Number.isFinite(x)&&x>0&&x<1e8;
 function validateChart(input,at){
  if(!input||typeof input!=="object"||Array.isArray(input)||
     Object.keys(input).sort().join(",")!=="H1,H4,M15")return null;
  const out={};
  for(const tf of TF){
   const rows=input[tf],width=WIDTH[tf];
   if(!Array.isArray(rows)||rows.length<2||rows.length>MAX)return null;
   let prev=-Infinity;const clean=[];
   for(const x of rows){
    const ts=time(x?.time);
    if(!Number.isFinite(ts)||ts%width!==0||ts<=prev||
       ts+width>at||!["open","high","low","close"].every(k=>finite(x[k]))||
       x.low>Math.min(x.open,x.close)||x.high<Math.max(x.open,x.close)||
       x.low>x.high)return null;
    clean.push({t:ts,open:x.open,high:x.high,low:x.low,close:x.close});
    prev=ts;
   }
   out[tf]=clean;
  }
  return out;
 }
 function validateSnapshot(d,now){
  if(!d||d.signal!=="WAIT"||d.executable!==false||
     d.researchEligible!==false||d.tradePlanExecutable!==false||
     d.paperOrdersAllowed!==false||d.orderEndpointsCalled!==false||
     !["OBSERVED_READONLY_UNVERIFIED","WAIT_CROSS_FRAME_GAPS"].includes(d.status)||
     d.rawQuoteShown!==true||d.privateChartReadOnly!==true||
     d.privateChartDataBasis!=="MID_WITH_POSSIBLE_BID_SEED"||
     !finite(d.bid)||!finite(d.ask)||d.ask<d.bid||
     typeof d.spread!=="number"||!Number.isFinite(d.spread)||
     d.spread<0||Math.abs(d.spread-(d.ask-d.bid))>.0001||
     !Number.isFinite(d.quoteAgeSeconds)||d.quoteAgeSeconds<0||
     d.quoteAgeSeconds>30)return null;
  const at=time(d.observedUTC),qt=time(d.quoteUTC);
  if(!Number.isFinite(at)||!Number.isFinite(qt)||qt>at||
     at>now+5000||now-at>30000||now-qt>30000||qt>now+5000)return null;
  const chart=validateChart(d.privateChart,at);
  if(!chart||!d.frameSummary||!d.crossFrameComparisons||
     typeof d.frameSummary!=="object"||Array.isArray(d.frameSummary)||
     Object.keys(d.frameSummary).sort().join(",")!=="H1,H4,M15")return null;
  for(const tf of TF){
   const s=d.frameSummary[tf],last=chart[tf].at(-1),closedAt=last.t+WIDTH[tf];
   if(!s||!Number.isSafeInteger(s.closedCount)||s.closedCount<50||
      s.closedCount<chart[tf].length||time(s.lastClosedUTC)!==closedAt||
      s.priceBasis!=="MID_WITH_POSSIBLE_BID_SEED"||
      at-closedAt>WIDTH[tf]*2||at<closedAt)return null;
  }
  const comparisons=d.crossFrameComparisons;
  if(Object.keys(comparisons).sort().join(",")!=="H1,H4")return null;
  let sourceGaps=false;
  for(const tf of ["H1","H4"]){
   const c=comparisons[tf];
   if(!c||typeof c!=="object"||Array.isArray(c)||
      Object.keys(c).sort().join(",")!==
       "completeMatches,completeMismatches,incompleteM15Groups,outsideRetentionWindow"||
      !Object.values(c).every(x=>Number.isSafeInteger(x)&&x>=0&&x<=1000))
    return null;
   // The source comparison partitions ALL closed higher-timeframe bars
   // into exactly four mutually exclusive groups. If their counts do not
   // sum to that timeframe's closed count, the packet is self-inconsistent.
   const total=c.completeMatches+c.completeMismatches+
      c.incompleteM15Groups+c.outsideRetentionWindow;
   if(total!==d.frameSummary[tf].closedCount)return null;
   if(c.completeMismatches>0||c.incompleteM15Groups>0)sourceGaps=true;
  }
  if((d.status==="WAIT_CROSS_FRAME_GAPS")!==sourceGaps)return null;
  return {at,chart,d,comparisons};
 }
 // Frontend defense-in-depth on ALREADY private, already-fetched closed bars.
 // A clean server counter alone cannot justify WATCH if the current
 // authenticated chart's latest H1/H4 or H1 parts contradict M15.
 // Nothing here upgrades market rights, first-seen or execution readiness.
 function localLatestParity(chart){
  if(!chart||!chart.M15||!chart.H1||!chart.H4)return false;
  const maps=Object.fromEntries(["M15","H1"].map(tf=>
    [tf,new Map(chart[tf].map(x=>[x.t,x]))]));
  const near=(x,y)=>Number.isFinite(x)&&Number.isFinite(y)&&
    Math.abs(x-y)<=Math.max(.00001,Math.abs(y)*1e-8);
  function match(whole,parts){
   return Boolean(whole)&&parts.length>0&&parts.every(Boolean)&&
     near(whole.open,parts[0].open)&&
     near(whole.high,Math.max(...parts.map(x=>x.high)))&&
     near(whole.low,Math.min(...parts.map(x=>x.low)))&&
     near(whole.close,parts.at(-1).close);
  }
  const h1=chart.H1.at(-1),h4=chart.H4.at(-1);
  if(!h1||!h4)return false;
  const m15h1=Array.from({length:4},(_,i)=>
    maps.M15.get(h1.t+i*WIDTH.M15));
  const m15h4=Array.from({length:16},(_,i)=>
    maps.M15.get(h4.t+i*WIDTH.M15));
  const h1h4=Array.from({length:4},(_,i)=>
    maps.H1.get(h4.t+i*WIDTH.H1));
  if(!match(h1,m15h1)||!match(h4,m15h4)||
     !match(h4,h1h4))return false;
  return h1h4.every(hour=>match(hour,
    Array.from({length:4},(_,i)=>
      maps.M15.get(hour.t+i*WIDTH.M15))));
 }
 // Check EVERY higher-timeframe candle for which all its M15
 // constituents are present in this bounded private snapshot, not merely
 // the latest H1/H4. Counts remain observational, NEVER trade authority.
 function localCoveredParityAudit(chart){
  if(!chart||!Array.isArray(chart.M15)||!Array.isArray(chart.H1)||
     !Array.isArray(chart.H4))return null;
  const m15=new Map(chart.M15.map(x=>[x.t,x]));
  const near=(x,y)=>Number.isFinite(x)&&Number.isFinite(y)&&
    Math.abs(x-y)<=Math.max(.00001,Math.abs(y)*1e-8);
  const equal=(whole,parts)=>Boolean(whole)&&parts.length>0&&
    parts.every(Boolean)&&
    near(whole.open,parts[0].open)&&
    near(whole.high,Math.max(...parts.map(x=>x.high)))&&
    near(whole.low,Math.min(...parts.map(x=>x.low)))&&
    near(whole.close,parts.at(-1).close);
  const result={H1:{fullyCovered:0,disagreed:0},
                H4:{fullyCovered:0,disagreed:0}};
  for(const tf of ["H1","H4"]){
   const n=tf==="H1"?4:16;
   for(const whole of chart[tf]){
    const parts=Array.from({length:n},(_,i)=>
      m15.get(whole.t+i*WIDTH.M15));
    if(parts.some(x=>!x))continue;
    result[tf].fullyCovered++;
    if(!equal(whole,parts))result[tf].disagreed++;
   }
  }
  return result;
 }
 function researchWatch(result){
  const d=result.d,v=d.privateTechnicalWatch,c=result.comparisons;
  if(!v||v.mode!=="PRIVATE_FROZEN_V3_TECHNICAL_WATCH_ONLY"||
     v.signal!=="WAIT"||v.executable!==false||v.tradeEligible!==false||
     v.paperOrdersAllowed!==false||v.liveOrdersAllowed!==false||
     v.sourceRightsVerified!==false||v.firstSeenAtDecisionVerified!==false||
     v.independentMacroNewsGcOrderFlowVerified!==false||
     v.brokerBidAskCostsVerified!==false||v.retrospectiveOnly!==true||
     v.entry!==null||v.stopLoss!==null||v.takeProfit!==null||
     v.brokerOrdersSent!==0||v.providerRequestsMade!==0||
     v.requiredM15ToReconcile21H4!==336||
     v.requiredH1ToReconcile21H4!==84||
     v.privateChartMaxBarsPerFrame!==48||
     v.full21H4CrossFrameAuditPossibleFromPrivateSnapshot!==false)
   return "WAIT — فحص V3 غير مؤكد";
  const localAudit=localCoveredParityAudit(result.chart);
  const clean=d.status==="OBSERVED_READONLY_UNVERIFIED"&&
    localLatestParity(result.chart)===true&&
    localAudit!==null&&
    ["H1","H4"].every(tf=>
      localAudit[tf].fullyCovered>=1&&
      localAudit[tf].disagreed===0&&
      c[tf].completeMatches>=localAudit[tf].fullyCovered&&
      c[tf].completeMismatches===0&&
      c[tf].incompleteM15Groups===0);
  if(clean&&v.status==="TECHNICAL_WATCH_ONLY_NOT_TRADE_READY"&&
     v.lastCrossFrameParityObserved===true&&
     (v.technicalCandidate==="BUY"&&v.watchLabel==="WATCH_BUY"||
      v.technicalCandidate==="SELL"&&v.watchLabel==="WATCH_SELL"))
   return "WAIT · "+v.watchLabel+" — مراقبة فنية رجعية فقط، بلا دخول أو وقف أو هدف";
  return "WAIT — تغطية H1/H4 مع M15 أو الشروط الفنية غير مكتملة";
 }
 // Pure validators are exposed only to local Node offline tests.
 if(typeof module!=="undefined"&&module.exports)
  module.exports={validateChart,validateSnapshot,localLatestParity,
    localCoveredParityAudit,researchWatch};
 if(typeof document==="undefined")return;
 const $=id=>document.getElementById(id);
 let frame="M15",state=null,pending=false,expiry=0;
 // Every user-initiated fetch has a generation. Android can hide or
 // navigate away while a request or JSON body is in flight; response
 // completion must not resurrect private prices after that transition.
 let requestEpoch=0;
 const format=n=>Number.isFinite(n)?n.toLocaleString("en-US",{
  minimumFractionDigits:2,maximumFractionDigits:2}):"—";
 const clock=t=>new Date(t).toLocaleString("ar-LB",{
  timeZone:"Asia/Beirut",day:"2-digit",month:"2-digit",year:"numeric",
  hour:"2-digit",minute:"2-digit"});
 function blank(message){
  const node=$("candles");node.replaceChildren();
  const t=document.createElementNS("http://www.w3.org/2000/svg","text");
  t.setAttribute("x","340");t.setAttribute("y","150");
  t.setAttribute("text-anchor","middle");t.setAttribute("fill","#aab5c4");
  t.textContent=message;node.appendChild(t);
 }
 function reset(message){
  state=null;expiry=0;$("decision").textContent="WAIT";
  $("price").textContent="غير متاح";
  $("timestamp").textContent="لا توجد عيّنة حديثة مؤهّلة";
  $("source").textContent="لا أسعار عامة؛ افتح جلسة المشاهدة الخاصة أولاً";
  $("reason").textContent=message||"WAIT — لا توجد توصية قابلة للتنفيذ";
  $("quality-status").textContent="WAIT — البيانات غير مؤهّلة";
  $("data-state").textContent="● غير متصل / غير متحقق";
  $("trend-status").textContent="غير متاح";
  $("watch-status").textContent="WAIT";
  $("parity-status").textContent="تطابق الفريمات: غير متحقق";
  $("chart-status").textContent="لا تُعرض أسعار غير متحققة أو شموع مفتوحة";
  blank("WAIT — لا توجد شموع خاصة موثقة");
 }
 function draw(){
  if(!state){blank("WAIT — لا توجد شموع مؤهلة");return;}
  // Mobile browsers often throttle background timers. Selecting a new
  // timeframe MUST synchronously clear the price and WATCH when expired.
  if(Date.now()>expiry){
   reset("WAIT — انتهت صلاحية سعر المشاهدة؛ اضغط تحديث للتحقق من جديد");
   return;
  }
  const rows=state.chart[frame].slice(-45),svg=$("candles");
  if(rows.length<2)return blank("WAIT — لا توجد شموع كافية");
  const lo=Math.min(...rows.map(x=>x.low)),
        hi=Math.max(...rows.map(x=>x.high)),range=Math.max(.01,hi-lo);
  svg.replaceChildren();
  const add=(tag,attrs)=>{
   const node=document.createElementNS("http://www.w3.org/2000/svg",tag);
   for(const [k,v] of Object.entries(attrs))node.setAttribute(k,String(v));
   svg.appendChild(node);
  };
  // Chart grid and truthful price-axis labels; no synthetic candles.
  for(let tick=0;tick<=4;tick++){
   const y=40+tick*55;
   add("line",{x1:12,y1:y,x2:625,y2:y,stroke:"#32435a","stroke-width":.8,"stroke-dasharray":"4 5"});
   const label=document.createElementNS("http://www.w3.org/2000/svg","text");
   label.setAttribute("x","665");label.setAttribute("y",String(y-5));
   label.setAttribute("text-anchor","end");label.setAttribute("fill","#b6c3d3");
   label.setAttribute("font-size","11");
   label.textContent=format(hi-tick*range/4);
   svg.appendChild(label);
  }
  rows.forEach((x,i)=>{
   const spacing=600/rows.length,at=18+(i+.5)*spacing,w=Math.max(3,spacing*.55),
     y=p=>260-(p-lo)/range*220,
     color=x.close>=x.open?"#24d2a0":"#f26879";
   add("line",{x1:at,y1:y(x.high),x2:at,y2:y(x.low),
     stroke:color,"stroke-width":1.5});
   add("rect",{x:at-w/2,y:Math.min(y(x.open),y(x.close)),
     width:w,height:Math.max(1,Math.abs(y(x.close)-y(x.open))),fill:color});
  });
  // Time labels come only from validated closed candles, never projected bars.
  for(const i of [0,Math.floor((rows.length-1)/2),rows.length-1]){
   const bar=rows[i],label=document.createElementNS("http://www.w3.org/2000/svg","text");
   label.setAttribute("x",String(18+(i+.5)*600/rows.length));
   label.setAttribute("y","290");label.setAttribute("text-anchor","middle");
   label.setAttribute("fill","#aab5c4");label.setAttribute("font-size","11");
   label.textContent=new Date(bar.t+WIDTH[frame]).toLocaleString("en-GB",{
    timeZone:"Asia/Beirut",day:"2-digit",month:"2-digit",hour:"2-digit",minute:"2-digit"
   });
   svg.appendChild(label);
  }
  $("chart-status").textContent=frame+" — "+rows.length+
    " شمعة BiQuote مغلقة، MID وربما بذرة BID · عرض شخصي غير قابل للتنفيذ";
 }
 document.querySelectorAll("[data-frame]").forEach(btn=>
  btn.addEventListener("click",()=>{
   frame={ "15min":"M15","1h":"H1","4h":"H4"}[btn.dataset.frame]||"M15";
   document.querySelectorAll("[data-frame]").forEach(x=>
    x.setAttribute("aria-pressed",String(x===btn)));
   draw();
  }));
 const refresh=$("refresh");
 refresh.addEventListener("click",async()=>{
  if(pending)return;
  pending=true;refresh.disabled=true;
  const myEpoch=++requestEpoch;
  reset("WAIT — جارٍ تدقيق مصدر BiQuote الخاص عند الطلب");
  try{
   const response=await fetch("/api/v3/ultimate/biquote-observation",{
    method:"GET",credentials:"same-origin",cache:"no-store",
    redirect:"error",headers:{Accept:"application/json"},
    signal:AbortSignal.timeout(15000)
   });
   if(response.status===401||response.status===403)throw Error("SESSION_REQUIRED");
   if(response.status===429)throw Error("RATE_LIMITED");
   if(response.status!==200)throw Error("DATA_UNAVAILABLE");
   if(!/^application\/json(?:\s*;|\s*$)/i.test(response.headers.get("content-type")||""))
    throw Error("INVALID_RESPONSE_TYPE");
   const packet=await response.json();
   const verified=validateSnapshot(packet,Date.now());
   if(myEpoch!==requestEpoch||document.visibilityState==="hidden")
    throw Error("PAGE_CHANGED_DURING_PRIVATE_FETCH");
   if(!verified)throw Error("PRIVATE_SESSION_OR_DATA_INVALID");
   state=verified;expiry=Date.now()+Math.min(15000,
    Math.max(1000,30000-(Date.now()-verified.at)));
   const latest=verified.chart.M15.at(-1);
   $("price").textContent=format(latest.close);
   $("timestamp").textContent="إغلاق M15 المرصود: "+
     clock(latest.t+WIDTH.M15)+" بيروت · آخر فحص "+clock(verified.at);
   $("source").textContent="BiQuote XAUUSD خاص للبحث فقط · MID وربما تاريخ BID · ليس سعر MT5 لحظي ولا سعر تنفيذ";
   $("data-state").textContent="● BiQuote · مشاهدة خاصة متحققة مؤقتاً";
   $("trend-status").textContent="غير مؤهل لإشارة";
   $("watch-status").textContent="WAIT · مراقبة";
   $("parity-status").textContent=localLatestParity(verified.chart)
     ?"تطابق أحدث M15 / H1 / H4: متحقق محلياً (لا يثبت اكتمال التاريخ)"
     :"تطابق أحدث M15 / H1 / H4: غير متحقق — WAIT";
   $("quality-status").textContent="M15 "+packet.frameSummary.M15.closedCount+
     " | H1 "+packet.frameSummary.H1.closedCount+
     " | H4 "+packet.frameSummary.H4.closedCount+
     " شمعة مغلقة محفوظة لدى مزوّد العرض؛ لا يثبت تاريخ الأرشيف الكامل";
   $("reason").textContent=researchWatch(verified)+
     " | التوصيات المعتمدة محجوبة بسبب حقوق الوسيط وGC والأخبار والتكاليف واختبار الأداء";
   $("decision").textContent="WAIT";draw();
  }catch(error){
   reset(error.message==="SESSION_REQUIRED"
    ?"WAIT — جلسة المشاهدة الخاصة غير مفعّلة في هذا المتصفح. افتح Ultimate وأدخل الرمز هناك، ثم ارجع واضغط تحديث."
    :"WAIT — تعذّر التحقق من بيانات BiQuote الحديثة أو الجلسة. افتح Ultimate للتأكد من الجلسة، ثم أعد المحاولة.");
  }finally{pending=false;refresh.disabled=false;}
 });
 // Presentation-only expiry: NO background quote calls, no stored prices.
 // Clear on background/navigation as well: Android may defer the timer, and
 // BFCache/back navigation must not resurrect a private market snapshot.
 if(typeof document.addEventListener==="function")
  document.addEventListener("visibilitychange",()=>{
   if(document.visibilityState==="hidden"){
    requestEpoch++;
    if(state||pending)
     reset("WAIT — خرجت من شاشة المشاهدة؛ اضغط تحديث لتحقق جديد");
   }else if(expiry&&Date.now()>expiry)
    reset("WAIT — انتهت صلاحية السعر المرصود؛ اضغط تحديث");
  });
 if(typeof window!=="undefined"&&typeof window.addEventListener==="function"){
  window.addEventListener("pagehide",()=>{
   requestEpoch++;
   if(state||pending)
    reset("WAIT — غادرت الصفحة؛ الردود القديمة ملغاة");
  });
  window.addEventListener("focus",()=>{
   if(expiry&&Date.now()>expiry)
    reset("WAIT — انتهت صلاحية البيانات بعد الرجوع للصفحة");
  });
 }
 setInterval(()=>{
  if(expiry&&Date.now()>expiry)
   reset("WAIT — انتهت صلاحية السعر المرصود. اضغط تحديث لطلب فحص جديد");
 },5000);
 reset("WAIT — التحديث يدوي. إن كانت جلسة المشاهدة مفعلة من Ultimate، اضغط تحديث.");
})();
