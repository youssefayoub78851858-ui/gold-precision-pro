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
 // Only for the authenticated, currently fresh private H4 chart:
 // compare a vendor-declared (not broker-certified) market-session tail
 // with the raw four-hour UTC tail. Never accept a supplied readiness,
 // broker rights flag, price or trade direction from this diagnostic.
 function vendorH4SessionLabel(result){
  const v=result?.d?.privateVendorH4Tail,rows=result?.chart?.H4;
  const fallback="H4: جدول وسيط MT5 غير مثبت؛ لا اعتماد للتسلسل السوقي";
  if(!Array.isArray(rows)||!rows.length||!v||
     v.mode!=="BIQUOTE_VENDOR_DECLARED_H4_ADJACENCY_RESEARCH_ONLY"||
     v.status!=="PROVIDER_DECLARED_PAUSE_SCENARIO_NOT_TRADING_PROOF"||
     v.signal!=="WAIT"||v.executable!==false||
     v.originalBrokerIdentified!==false||
     v.originalBrokerCalendarVerified!==false||
     v.brokerMarketDataRightsVerified!==false||
     v.all21H4M15ParityVerified!==false||
     v.perBarFirstSeenVerified!==false||
     v.researchWarmupApproved!==false||
     v.paperOrdersAllowed!==false||v.liveOrdersAllowed!==false||
     v.brokerOrdersSent!==0||v.paperOrdersSent!==0||
     v.providerRequestsMade!==0||v.missingCandlesSynthesized!==0)
   return fallback;
  const number=x=>Number.isSafeInteger(x)&&x>=0&&x<=48;
  if(![v.observedClosedH4Bars,v.strictUtcH4Tail,
    v.providerDeclaredSessionAdjacentH4Tail,
    v.providerDeclaredPauseGapPairs,
    v.providerDeclaredPauseMissingH4Slots,
    v.unexplainedGapPairs,v.unknownCalendarGapPairs].every(number)||
    v.observedClosedH4Bars!==rows.length||
    v.strictUtcH4Tail<1||
    v.providerDeclaredSessionAdjacentH4Tail<v.strictUtcH4Tail||
    v.providerDeclaredSessionAdjacentH4Tail>rows.length||
    v.providerScenarioReached21H4!==
      (v.providerDeclaredSessionAdjacentH4Tail>=21))
    return fallback;
  let localTail=1;
  for(let i=rows.length-1;i>0;i--){
   if(rows[i].t-rows[i-1].t!==WIDTH.H4)break;
   localTail++;
  }
  if(localTail!==v.strictUtcH4Tail)return fallback;
  return "H4 مغلقة: "+v.observedClosedH4Bars+
   " | UTC متتالية: "+v.strictUtcH4Tail+
   " | حسب استراحات BiQuote: "+v.providerDeclaredSessionAdjacentH4Tail+
   " (توضيحي فقط؛ جدول الوسيط الأصلي وحقوق المصدر غير مثبتين)";
 }

 // Display-only, strictly contiguous CLOSED UTC bar indicators.
 // This local calculation NEVER approves a trading signal or broker market data.
 const TECHNICAL_MIN=21;
 function technicalObservations(chart){
  const out={};
  for(const tf of TF){
   const rows=chart?.[tf],tail=[],width=WIDTH[tf];
   if(!Array.isArray(rows)||rows.length>MAX){out[tf]={status:"INSUFFICIENT",count:0};continue;}
   for(let i=rows.length-1;i>=0;i--){
    const b=rows[i],newer=tail[0];
    if(!b||!Number.isFinite(b.t)||b.t%width!==0||
       !["open","high","low","close"].every(k=>finite(b[k]))||
       b.high<Math.max(b.open,b.close)||b.low>Math.min(b.open,b.close)||b.high<b.low||
       (newer&&newer.t-b.t!==width))break;
    tail.unshift(b);
   }
   if(tail.length<TECHNICAL_MIN){
    out[tf]={status:"INSUFFICIENT",count:tail.length};continue;
   }
   const closes=tail.map(b=>b.close);
   let ema=closes.slice(0,20).reduce((x,y)=>x+y,0)/20;
   for(let i=20;i<closes.length;i++)ema=(closes[i]*2+ema*19)/21;
   let gains=0,losses=0;
   for(let i=1;i<=14;i++){
    const delta=closes[i]-closes[i-1];
    gains+=Math.max(0,delta);losses+=Math.max(0,-delta);
   }
   gains/=14;losses/=14;
   for(let i=15;i<closes.length;i++){
    const delta=closes[i]-closes[i-1];
    gains=(gains*13+Math.max(0,delta))/14;
    losses=(losses*13+Math.max(0,-delta))/14;
   }
   const rsi=losses===0?(gains===0?50:100):100-100/(1+gains/losses);
   const ranges=[];
   for(let i=1;i<tail.length;i++){
    const b=tail[i],prev=tail[i-1].close;
    ranges.push(Math.max(b.high-b.low,Math.abs(b.high-prev),Math.abs(b.low-prev)));
   }
   let atr=ranges.slice(0,14).reduce((x,y)=>x+y,0)/14;
   for(let i=14;i<ranges.length;i++)atr=(atr*13+ranges[i])/14;
   if(![ema,rsi,atr].every(Number.isFinite)||rsi<0||rsi>100||atr<0){
    out[tf]={status:"INVALID",count:tail.length};continue;
   }
   const close=closes.at(-1);
   out[tf]={status:"LOCAL_CLOSED_MID_ONLY",count:tail.length,
    ema20:ema,rsi14:rsi,atr14:atr,
    closeVsEma:close>ema?"ABOVE":close<ema?"BELOW":"EQUAL"};
  }
  return out;
 }

 // Pure validators are exposed only to local Node offline tests.
 if(typeof module!=="undefined"&&module.exports)
  module.exports={validateChart,validateSnapshot,localLatestParity,
    localCoveredParityAudit,researchWatch,vendorH4SessionLabel,technicalObservations};
 if(typeof document==="undefined")return;
 const $=id=>document.getElementById(id);
 let frame="M15",state=null,pending=false,expiry=0;
 const AUTO_POLL_MS=60000, MAX_STALE_MS=600000;
 let autoEnabled=false,viewerReady=false,checkingViewer=false,nextPollAt=Infinity;
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
  resetTechnical();
  $("trend-status").textContent="غير متاح";
  $("watch-status").textContent="WAIT";
  $("parity-status").textContent="تطابق الفريمات: غير متحقق";
  $("vendor-h4-session").textContent=
    "H4: جدول وسيط MT5 غير مثبت؛ لا اعتماد للتسلسل السوقي";
  $("chart-status").textContent="لا تُعرض أسعار غير متحققة أو شموع مفتوحة";
  blank("WAIT — لا توجد شموع خاصة موثقة");
 }
 
 function resetTechnical(){
  $("technical-short").textContent="غير متاح";
  $("technical-note").textContent="لا قراءة فنية قبل جلسة خاصة وبيانات مغلقة حديثة.";
  for(const tf of TF){
   const id=tf.toLowerCase();
   $(id+"-technical").textContent="—";
   for(const k of ["ema","rsi","atr"])
    $(id+"-"+k).textContent="—";
   $(id+"-technical-quality").textContent="WAIT · غير متاح";
  }
 }
 function renderTechnical(chart){
  const all=technicalObservations(chart);
  let count=0;
  for(const tf of TF){
   const metric=all[tf],id=tf.toLowerCase();
   if(metric.status!=="LOCAL_CLOSED_MID_ONLY"){
    $(id+"-technical").textContent="غير كافٍ";
    for(const k of ["ema","rsi","atr"])$(id+"-"+k).textContent="—";
    $(id+"-technical-quality").textContent="WAIT · "+metric.count+"/21 شمعة UTC متتابعة";
    continue;
   }
   count++;
   $(id+"-technical").textContent=metric.closeVsEma==="ABOVE"?"الإغلاق فوق EMA20":
     metric.closeVsEma==="BELOW"?"الإغلاق تحت EMA20":"الإغلاق عند EMA20";
   $(id+"-ema").textContent=format(metric.ema20);
   $(id+"-rsi").textContent=metric.rsi14.toFixed(1);
   $(id+"-atr").textContent=format(metric.atr14);
   $(id+"-technical-quality").textContent=metric.count+" شمعة MID مغلقة UTC";
  }
  $("technical-short").textContent=count?count+"/3 مرصودة":"غير كافٍ";
  $("technical-note").textContent=count
    ?"مؤشرات MID محلية فقط؛ ليست إشارة، ولا تثبت حقوق المصدر أو تطابق أسعار الوسيط."
    :"WAIT · لا توجد شموع متتابعة كافية لعرض المؤشرات.";
 }


 // Bounded historical-on-screen display, never a live quote or a trade signal.
 // Hidden/pagehide or ten minutes without a valid update clears all private values.
 function markStale(message){
  if(!state)return false;
  if(document.visibilityState==="hidden"||Date.now()-state.at>MAX_STALE_MS){
   reset("WAIT — آخر بيانات تجاوزت حد الاحتفاظ؛ يلزم تحديث جديد");
   return false;
  }
  $("decision").textContent="WAIT";
  $("watch-status").textContent="WAIT · لا فرصة صالحة";
  $("trend-status").textContent="غير مؤهل لإشارة";
  $("data-state").textContent="● لقطة قديمة · ليست مباشرة";
  $("source").textContent="BiQuote آخر مشاهدة تاريخية · MID وربما تاريخ BID · ليست سعراً للتنفيذ";
  $("reason").textContent=message||"WAIT — آخر لقطة قديمة؛ فحص تلقائي مستمر";
  $("technical-note").textContent=
    "المؤشرات المعروضة تاريخية فقط من شموع مغلقة؛ ليست توصية تداول.";
  $("auto-state").textContent="تلقائي · بيانات قديمة";
  updateAutoLabel();
  return true;
 }


 // Foreground-only UI countdown; NEVER treats next poll time as a live tick.
 function updateAutoLabel(){
  if(document.visibilityState==="hidden")return;
  if(pending){
   $("auto-state").textContent="تلقائي · جاري التحقق";
   return;
  }
  if(checkingViewer){
   $("auto-state").textContent="تلقائي · فحص الجلسة";
   return;
  }
  if(!Number.isFinite(nextPollAt)){
   $("auto-state").textContent="تلقائي · يحتاج جلسة خاصة";
   return;
  }
  const seconds=Math.max(0,Math.ceil((nextPollAt-Date.now())/1000));
  const label=viewerReady?"فحص السعر":"محاولة اتصال";
  const old=state&&Date.now()>expiry?"بيانات قديمة · ":"";
  $("auto-state").textContent=old+"تلقائي · "+label+" بعد "+seconds+" ث";
 }

 function draw(){
  if(!state){blank("WAIT — لا توجد شموع مؤهلة");return;}
  // Mobile browsers often throttle background timers. Selecting a new
  // timeframe MUST synchronously clear the price and WATCH when expired.
  if(Date.now()>expiry&&!markStale("WAIT — أحدث لقطة قديمة، التحديث التلقائي يعمل"))return;
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
    " شمعة BiQuote مغلقة، MID وربما بذرة BID · "+
    (Date.now()>expiry?"تاريخية قديمة · ":"")+"عرض شخصي غير قابل للتنفيذ";
 }
 document.querySelectorAll("[data-frame]").forEach(btn=>
  btn.addEventListener("click",()=>{
   frame={ "15min":"M15","1h":"H1","4h":"H4"}[btn.dataset.frame]||"M15";
   document.querySelectorAll("[data-frame]").forEach(x=>
    x.setAttribute("aria-pressed",String(x===btn)));
   draw();
  }));
 const refresh=$("refresh");
 // All observed snapshots remain WAIT; no broker, paper or live order routes.
 async function refreshSnapshot(){
  if(pending||document.visibilityState==="hidden")return;
  pending=true;refresh.disabled=true;
  const ownEpoch=++requestEpoch;
  if(!state)reset("WAIT — جارٍ فحص المصدر الخاص");
  else markStale("WAIT — جارٍ طلب لقطة جديدة، السابقة تاريخية فقط");
  $("auto-state").textContent="تحديث تلقائي · جارٍ الفحص";
  try{
   const response=await fetch("/api/v3/ultimate/biquote-observation",{
     method:"GET",credentials:"same-origin",cache:"no-store",
     redirect:"error",headers:{Accept:"application/json"},
     signal:AbortSignal.timeout(15000)
   });
   if(response.status===401||response.status===403)throw Error("SESSION_REQUIRED");
   if(response.status===429)throw Error("RATE_LIMITED");
   if(response.status===503){
    let code="";
    try{
     if(/^application\/json(?:\s*;|\s*$)/i.test(response.headers.get("content-type")||"")){
      const d=await response.json();
      const allowed=["PROVIDER_REPORTED_CLOSED","CLOSED_CANDLE_STALE",
       "QUOTE_STALE_OR_UNVERIFIED","PUBLIC_HTTP_UNAVAILABLE",
       "PUBLIC_FEED_INVALID_STALE_OR_UNAVAILABLE","LATEST_QUOTE_NO_LONGER_FRESH"];
      if(d?.signal==="WAIT"&&d?.executable===false&&Array.isArray(d.blockerCodes)&&
        allowed.includes(d.blockerCodes[0]))code=d.blockerCodes[0];
     }
    }catch(_ignored){}
    throw Error(code||"DATA_UNAVAILABLE");
   }
   if(response.status!==200)throw Error("DATA_UNAVAILABLE");
   if(!/^application\/json(?:\s*;|\s*$)/i.test(response.headers.get("content-type")||""))
    throw Error("INVALID_RESPONSE_TYPE");
   const packet=await response.json();
   const verified=validateSnapshot(packet,Date.now());
   if(ownEpoch!==requestEpoch||document.visibilityState==="hidden")
    throw Error("PAGE_CHANGED_DURING_PRIVATE_FETCH");
   if(!verified)throw Error("PRIVATE_SESSION_OR_DATA_INVALID");
   state=verified;
   viewerReady=true;
   expiry=Date.now()+Math.min(15000,Math.max(1000,30000-(Date.now()-verified.at)));
   nextPollAt=Date.now()+AUTO_POLL_MS;
   const latest=verified.chart.M15.at(-1);
   $("price").textContent=format(latest.close);
   $("timestamp").textContent="إغلاق M15 المرصود: "+
     clock(latest.t+WIDTH.M15)+" بيروت · آخر فحص "+clock(verified.at);
   $("source").textContent="BiQuote XAUUSD خاص للبحث فقط · MID وربما تاريخ BID · ليس سعر MT5 لحظي ولا سعر تنفيذ";
   $("data-state").textContent="● BiQuote · مشاهدة خاصة متحققة مؤقتاً";
   $("auto-state").textContent="تلقائي كل 60 ثانية · الصفحة مفتوحة";
   renderTechnical(verified.chart);
   $("trend-status").textContent="غير مؤهل لإشارة";
   $("watch-status").textContent="WAIT · مراقبة";
   $("parity-status").textContent=localLatestParity(verified.chart)
    ?"تطابق أحدث M15 / H1 / H4: متحقق محلياً (لا يثبت اكتمال التاريخ)"
    :"تطابق أحدث M15 / H1 / H4: غير متحقق — WAIT";
   $("vendor-h4-session").textContent=vendorH4SessionLabel(verified);
   $("quality-status").textContent="M15 "+packet.frameSummary.M15.closedCount+
    " | H1 "+packet.frameSummary.H1.closedCount+" | H4 "+packet.frameSummary.H4.closedCount+
    " شمعة مغلقة لدى المزوّد؛ لا يثبت الأرشيف الكامل";
   $("reason").textContent=researchWatch(verified)+
    " | لا توصيات معتمدة قبل حقوق الوسيط وGC والأخبار والتكاليف واختبار الأداء";
   $("decision").textContent="WAIT";draw();
   updateAutoLabel();
  }catch(error){
   if(ownEpoch!==requestEpoch||document.visibilityState==="hidden")return;
   const reasons={
    PROVIDER_REPORTED_CLOSED:"WAIT — مزوّد BiQuote أعلن إغلاق السوق.",
    CLOSED_CANDLE_STALE:"WAIT — لم تتحدث الشموع المغلقة.",
    QUOTE_STALE_OR_UNVERIFIED:"WAIT — السعر الجديد قديم أو غير متحقق.",
    PUBLIC_HTTP_UNAVAILABLE:"WAIT — مصدر البيانات لا يستجيب حالياً.",
    PUBLIC_FEED_INVALID_STALE_OR_UNAVAILABLE:"WAIT — بيانات المصدر غير مكتملة.",
    LATEST_QUOTE_NO_LONGER_FRESH:"WAIT — انتهت صلاحية السعر أثناء الفحص.",
    RATE_LIMITED:"WAIT — حدّ الطلبات؛ سنخفف معدل التحديث."
   };
   if(["SESSION_REQUIRED","PRIVATE_SESSION_OR_DATA_INVALID"].includes(error.message)){
    viewerReady=false;nextPollAt=Infinity;
    reset(error.message==="SESSION_REQUIRED"?
     "WAIT — جلسة المشاهدة غير مفعّلة؛ افتح Ultimate لتجديدها.":
     "WAIT — لم نتمكن من إثبات صلاحية الجلسة أو البيانات.");
   }else{
    const message=reasons[error.message]||
      "WAIT — تعذّر فحص بيانات جديدة؛ آخر لقطة تاريخية فقط.";
    if(!markStale(message))reset(message);
    nextPollAt=Date.now()+(error.message==="RATE_LIMITED"?180000:AUTO_POLL_MS);
    $("auto-state").textContent=error.message==="RATE_LIMITED"?
     "تلقائي · إعادة بعد 3 دقائق":"تلقائي · محاولة خلال دقيقة";
   }
  }finally{pending=false;refresh.disabled=false;updateAutoLabel();}
 }
 refresh.addEventListener("click",refreshSnapshot);
 // This preliminary same-origin cookie check has NO upstream market requests.
 // Anonymous visitors do not start automatic BiQuote polling.
 async function startAuto(){
  if(!autoEnabled||checkingViewer||pending||document.visibilityState==="hidden")return;
  checkingViewer=true;const ownEpoch=++requestEpoch;
  try{
   const response=await fetch("/api/v3/ultimate/biquote-viewer-status",{
    method:"GET",credentials:"same-origin",cache:"no-store",
    redirect:"error",headers:{Accept:"application/json"},
    signal:AbortSignal.timeout(9000)
   });
   const packet=response.status===200?await response.json():null;
   if(ownEpoch!==requestEpoch||document.visibilityState==="hidden")return;
   if(response.status!==200||packet?.viewerSessionReady!==true||
     packet?.signal!=="WAIT"||packet?.executable!==false){
    viewerReady=false;nextPollAt=Infinity;
    reset("WAIT — جلسة المشاهدة غير مفعلة؛ افتح Ultimate لتسجيل الدخول.");
   }else{
    viewerReady=true;nextPollAt=Date.now();
   }
  }catch(_error){
   if(ownEpoch!==requestEpoch||document.visibilityState==="hidden")return;
   viewerReady=false;nextPollAt=Date.now()+AUTO_POLL_MS;
   if(!markStale("WAIT — فحص الجلسة تعذر مؤقتاً"))
    reset("WAIT — تعذر فحص الجلسة؛ ستجري محاولة تلقائية.");
  }finally{checkingViewer=false;updateAutoLabel();}
  if(viewerReady&&autoEnabled&&document.visibilityState!=="hidden")
   await refreshSnapshot();
 }
 if(typeof document.addEventListener==="function"){
  document.addEventListener("DOMContentLoaded",()=>{
   autoEnabled=true;void startAuto();
  });
  document.addEventListener("visibilitychange",()=>{
   if(document.visibilityState==="hidden"){
    requestEpoch++;viewerReady=false;nextPollAt=Infinity;
    reset("WAIT — الشاشة بالخلفية؛ تم مسح بيانات المشاهدة الخاصة.");
   }else if(autoEnabled)void startAuto();
  });
 }
 if(typeof window!=="undefined"&&typeof window.addEventListener==="function"){
  window.addEventListener("pagehide",()=>{
   requestEpoch++;autoEnabled=false;viewerReady=false;nextPollAt=Infinity;
   reset("WAIT — غادرت الشاشة؛ لم نحتفظ بالأسعار الخاصة.");
  });
  window.addEventListener("pageshow",()=>{
   if(!autoEnabled){autoEnabled=true;void startAuto();}
  });
  window.addEventListener("focus",()=>{
   if(document.visibilityState==="hidden")return;
   if(expiry&&Date.now()>expiry)
    markStale("WAIT — آخر لقطة تاريخية، وليست سعراً مباشراً.");
   if(autoEnabled&&!checkingViewer&&!pending&&Date.now()>=nextPollAt){
    if(viewerReady)void refreshSnapshot();
    else void startAuto();
   }
  });
 }
 setInterval(()=>{
  if(document.visibilityState==="hidden")return;
  if(state){
   if(Date.now()-state.at>MAX_STALE_MS)
    reset("WAIT — تجاوزت آخر بيانات عشر دقائق؛ تم مسحها.");
   else if(Date.now()>expiry)
    markStale("WAIT — الشموع المعروضة تاريخية؛ يجري التحديث تلقائياً.");
  }
  if(autoEnabled&&!checkingViewer&&!pending&&Date.now()>=nextPollAt){
   if(viewerReady)void refreshSnapshot();
   else void startAuto();
  }
  updateAutoLabel();
 },5000);
 reset("WAIT — فحص تلقائي عند فتح الشاشة بجلسة مشاهدة خاصة صالحة.");
})();
