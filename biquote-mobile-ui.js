"use strict";
/* Real BiQuote review observations are NEVER wired into paper order controls. */
(function(){
 const $=id=>document.getElementById(id);
 const button=$("biquote-refresh"),secret=$("biquote-viewer-secret");
 if(!button||!secret)return;
 const fmt=n=>typeof n==="number"&&Number.isFinite(n)?n.toFixed(3):"—";
 const local=t=>{if(!t)return"غير متاح";
   try{return new Date(t).toLocaleString("ar-LB",{timeZone:"Asia/Beirut",year:"numeric",
       month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",second:"2-digit"});}
   catch{return"غير متاح";}
 };
 const label={UP:"صعود وصفي (EMA20 فوق EMA50)",DOWN:"هبوط وصفي (EMA20 تحت EMA50)",
   MIXED:"اتجاه مختلط"};
 // Completely separate from paper-terminal-core.js and its simulator.
 // No market data is written to storage or the paper-trade journal.
 let busy=false,activeFrame="M15",privateChart=null,privateStructure=null;
 const frameWidth={M15:900000,H1:3600000,H4:14400000};
 function validPrivateChart(input){
   if(!input||typeof input!=="object"||Array.isArray(input))return null;
   const result={};
   for(const tf of ["M15","H1","H4"]){
     const rows=input[tf];
     if(!Array.isArray(rows)||rows.length<2||rows.length>48)return null;
     let previous=-Infinity;
     const safe=[];
     for(const r of rows){
       if(!r||typeof r.time!=="string"||!/^20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,3})?Z$/.test(r.time))return null;
       const time=Date.parse(r.time);
       if(!Number.isFinite(time)||time<=previous||time%frameWidth[tf]!==0||
          time+frameWidth[tf]>Date.now())return null;
       previous=time;
       if(!["open","high","low","close"].every(k=>typeof r[k]==="number"&&Number.isFinite(r[k])&&r[k]>0))return null;
       if(r.high<Math.max(r.open,r.close,r.low)||r.low>Math.min(r.open,r.close,r.high))return null;
       safe.push({t:time,open:r.open,high:r.high,low:r.low,close:r.close});
     }
     result[tf]=safe;
   }
   return result;
 }

 // Derived observations from the authenticated response only; do not
 // calculate entry prices, orders, or BOS across unclassified session gaps.
 function validPrivateStructure(input,chart){
   if(!chart||!input||input.mode!=="PRIVATE_READONLY_TECHNICAL_OBSERVATIONS"||
      input.priceBasis!=="MID_WITH_POSSIBLE_BID_SEED"||
      input.signal!=="WAIT"||input.executable!==false||
      input.tradeEligible!==false||input.researchEligible!==false||
      input.paperOrdersAllowed!==false||!input.frames||
      input.sessionCalendarVerified!==false||
      input.upstreamRightsWarranted!==false||
      input.newsAndMacroIncluded!==false||input.orderFlowIncluded!==false)return null;
   const safe={};
   const whitelist=["BOS_UP","BOS_DOWN","SWEEP_HIGH","SWEEP_LOW","FVG_BULL","FVG_BEAR"];
   for(const tf of ["M15","H1","H4"]){
     const f=input.frames[tf];
     if(!f||f.signal!=="WAIT"||f.executable!==false||
        f.tradeEligible!==false||f.validForEntry!==false||
        f.sessionCalendarVerified!==false||
        f.priceBasis!=="MID_WITH_POSSIBLE_BID_SEED")return null;
     if(f.state==="INSUFFICIENT_VERIFIED_STRUCTURE"){
       safe[tf]={state:f.state,contiguousBars:Number.isInteger(f.contiguousBars)?f.contiguousBars:0};
       continue;
     }
     const partial=f.state==="PARTIAL_OBSERVATION_UNVERIFIED_SESSION";
     if(!(partial||f.state==="OBSERVATION_ONLY")||f.timeframe!==tf||
        !Number.isInteger(f.contiguousBars)||f.contiguousBars<7||
        (partial&&f.contiguousBars>=20)||
        (!partial&&f.contiguousBars<20)||
        !Number.isInteger(f.unclassifiedGapsInChart)||
        f.unclassifiedGapsInChart<0||
        f.lastClosedOpenUTC!==new Date(chart[tf].at(-1).t).toISOString())return null;
     if(!["lastClosed","recentRangeHigh20","recentRangeLow20"]
           .every(k=>typeof f[k]==="number"&&Number.isFinite(f[k])&&f[k]>0))return null;
     if(!Number.isInteger(f.recentRangeBars)||
        f.recentRangeBars!==Math.min(f.contiguousBars,20)||
        f.technicalCoverage!=="CONTIGUOUS_POST_GAP_ONLY"||
        f.unclassifiedGapsRemainBlocked!==true)return null;
     const positive=n=>typeof n==="number"&&Number.isFinite(n)&&n>0;
     if(f.contiguousBars<20?f.ema20!==null:!positive(f.ema20))return null;
     if(f.contiguousBars<15?f.atr14!==null:!positive(f.atr14))return null;
     if(f.recentRangeHigh20<f.recentRangeLow20||
        !["confirmedSwingHigh","confirmedSwingLow"].every(k=>f[k]===null||
          (typeof f[k]==="number"&&Number.isFinite(f[k])&&f[k]>0)))return null;
     if(!Array.isArray(f.lastClosedEvents)||f.lastClosedEvents.length>6||
        !f.lastClosedEvents.every(v=>whitelist.includes(v)))return null;
     const gap=f.referenceOnlyGapAudit;
     if(!gap||gap.brokerCalendarVerified!==false||gap.sessionCalendarVerified!==false||
        gap.bridgeBarsAllowed!==false||gap.executable!==false||gap.signal!=="WAIT"||
        gap.timeframe!==tf||!Number.isInteger(gap.gapCount)||
        gap.gapCount!==f.unclassifiedGapsInChart||!Array.isArray(gap.examples)||
        gap.examples.length>8)return null;
     if(!gap.examples.every(g=>Number.isInteger(g.missingSlots)&&g.missingSlots>0&&
        /^(REFERENCE_PAUSE_CANDIDATE_NOT_BROKER_VERIFIED|MISSING_IN_REFERENCE_TRADING_HOURS|REFERENCE_RANGE_UNKNOWN)$/.test(g.label)))
       return null;
     safe[tf]={...f,lastClosedEvents:[...f.lastClosedEvents]};
   }
   return safe;
 }
 const eventNames={BOS_UP:"كسر قمة مؤكدة",BOS_DOWN:"كسر قاع مؤكد",
   SWEEP_HIGH:"سحب سيولة فوق قمة",SWEEP_LOW:"سحب سيولة تحت قاع",
   FVG_BULL:"FVG صاعد",FVG_BEAR:"FVG هابط"};
 function describeStructure(){
   const el=$("biquote-structure-summary");
   if(!el)return;
   const f=privateStructure?.[activeFrame];
   if(!f){el.textContent="WAIT — التحليل الهيكلي الخاص غير متاح من دون بيانات مغلقة مصرح بعرضها.";return;}
   if(f.state==="INSUFFICIENT_VERIFIED_STRUCTURE"){
     el.textContent="WAIT — أقل من 7 شموع مغلقة متصلة على "+activeFrame+
       " لتأكيد القمم والقيعان داخل الجلسة. لن نملأ الفجوات اصطناعياً.";
     return;
   }
   const level=n=>n===null?"غير مؤكدة":fmt(n);
   const seen=f.lastClosedEvents.map(x=>eventNames[x]).join("، ")||"لا حدث مؤكد بالشمعة الأخيرة";
   const reference=f.referenceOnlyGapAudit;
   const candidates=reference?.referencePauseCandidates||0;
   const missing=reference?.missingDuringReferenceTradingHours||0;
   const unknown=reference?.outsideReference||0;
   const gapExamples=(reference?.examples||[]).slice(-2).map(g=>
     g.previousBarUTC.slice(5,16).replace("T"," ")+" UTC → "+
     g.nextBarUTC.slice(5,16).replace("T"," ")+" UTC: "+
     (g.label==="REFERENCE_PAUSE_CANDIDATE_NOT_BROKER_VERIFIED"?
       "تشبه استراحة شائعة فقط، ليست مؤكدة":
       g.label==="MISSING_IN_REFERENCE_TRADING_HOURS"?
       "فجوة بوقت تداول مرجعي، تتطلب تدقيق":
       "لا يوجد جدول مرجعي كافٍ")
   ).join(" ؛ ");
   const partial=f.state==="PARTIAL_OBSERVATION_UNVERIFIED_SESSION";
   el.textContent=(partial?"WAIT — تحليل جزئي بعد آخر فجوة غير مصنّفة. ":"قراءة وصفية فقط. ")+
     "قراءة "+activeFrame+" — EMA20: "+(f.ema20===null?"غير متاح (<20 شمعة متصلة)":fmt(f.ema20))+
     " | ATR14: "+(f.atr14===null?"غير متاح (<15 شمعة متصلة)":fmt(f.atr14))+
     " | قمة نمطية مؤكدة بالشموع: "+level(f.confirmedSwingHigh)+
     " | قاع نمطي مؤكّد بالشموع: "+level(f.confirmedSwingLow)+
     " | نطاق آخر "+f.recentRangeBars+" شموع متصلة: "+fmt(f.recentRangeLow20)+"–"+fmt(f.recentRangeHigh20)+
     " | "+seen+" | عدد الشموع المتصلة "+f.contiguousBars+
     " | فجوات غير مصنّفة "+f.unclassifiedGapsInChart+
     ". مرجع نوفمبر الزمني فقط: "+candidates+" شموع غائبة تشبه توقفاً شائعاً، "+
     missing+" غائبة خلال تداول مرجعي، "+unknown+" خارج المرجع. "+
     (gapExamples?" أمثلة أوقات الفجوات: "+gapExamples+". ":"")+
     "جدول جلسات وسيط BiQuote الأصلي غير موثّق، ولا نصل أي شموع عبر الفجوات. "+
     "مستويات MID ليست نقاط دخول أو وقف خسارة. القرار WAIT.";
 }
 function drawPrivateChart(){
   const canvas=$("biquote-live-canvas");
   if(!canvas)return;
   const ctx=canvas.getContext("2d");
   if(!ctx)return;
   const w=Math.max(260,canvas.clientWidth||320),h=canvas.clientHeight||285,
     dpr=Math.min(2,window.devicePixelRatio||1);
   canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);
   ctx.setTransform(dpr,0,0,dpr,0,0);
   ctx.fillStyle="#0b1a2a";ctx.fillRect(0,0,w,h);
   const rows=privateChart?.[activeFrame];
   if(!rows?.length){
     ctx.fillStyle="#b9cae0";ctx.font="14px system-ui";ctx.textAlign="center";
     ctx.fillText("لا توجد شموع حقيقية مصرح بعرضها",w/2,h/2);
     return;
   }
   let lo=Math.min(...rows.map(r=>r.low)),hi=Math.max(...rows.map(r=>r.high));
   const pad=Math.max(0.2,(hi-lo)*0.08);lo-=pad;hi+=pad;
   const left=14,right=68,top=16,bottom=34,plotWidth=w-left-right,plotHeight=h-top-bottom;
   const y=p=>top+(hi-p)/(hi-lo)*plotHeight;
   const first=rows[0].t-frameWidth[activeFrame]/2,
     last=rows.at(-1).t+frameWidth[activeFrame]/2;
   const x=t=>left+(t-first)/(last-first)*plotWidth;
   ctx.font="11px system-ui";ctx.textAlign="right";
   for(let i=0;i<=4;i++){
     const value=lo+(hi-lo)*i/4,Y=y(value);
     ctx.strokeStyle="#32455e";ctx.fillStyle="#acbed7";
     ctx.beginPath();ctx.moveTo(left,Y);ctx.lineTo(w-right+3,Y);ctx.stroke();
     ctx.fillText(value.toFixed(2),w-4,Y+4);
   }
   const candleWidth=Math.max(2,Math.min(10,plotWidth/rows.length*0.58));
   for(const r of rows){
     const center=x(r.t),up=r.close>=r.open;
     ctx.fillStyle=up?"#44cfb0":"#ea8292";ctx.strokeStyle=ctx.fillStyle;
     ctx.beginPath();ctx.moveTo(center,y(r.high));ctx.lineTo(center,y(r.low));ctx.stroke();
     ctx.fillRect(center-candleWidth/2,Math.min(y(r.open),y(r.close)),
       candleWidth,Math.max(1,Math.abs(y(r.open)-y(r.close))));
   }
   // Show only AUTHENTICATED, time-aligned, confirmed research levels.
   // These are overlays, not entry/SL/TP recommendations.
   const f=privateStructure?.[activeFrame];
   if(f?.state==="OBSERVATION_ONLY"||
      f?.state==="PARTIAL_OBSERVATION_UNVERIFIED_SESSION"){
     for(const [n,color] of [[f.confirmedSwingHigh,"#d8b967"],
                            [f.confirmedSwingLow,"#8aace0"],[f.ema20,"#a69be2"]]){
       if(typeof n==="number"&&n>=lo&&n<=hi){
         ctx.strokeStyle=color;ctx.beginPath();
         ctx.moveTo(left,y(n));ctx.lineTo(w-right+3,y(n));ctx.stroke();
       }
     }
   }
   ctx.fillStyle="#a9bfd7";ctx.font="11px system-ui";
   ctx.textAlign="left";ctx.fillText(new Date(rows[0].t).toISOString().slice(5,16).replace("T"," "),left,h-11);
   ctx.textAlign="right";ctx.fillText(new Date(rows.at(-1).t).toISOString().slice(5,16).replace("T"," "),w-right,h-11);
 }
 function setPrivateChart(value,status){
   privateChart=value;
   const caption=$("biquote-live-caption");
   if(caption)caption.textContent=status;
   drawPrivateChart();
   describeStructure();
 }
 for(const tab of document.querySelectorAll("button[data-biq-frame]"))
   tab.addEventListener("click",()=>{
     const tf=tab.dataset.biqFrame;
     if(!Object.prototype.hasOwnProperty.call(frameWidth,tf))return;
     activeFrame=tf;
     for(const b of document.querySelectorAll("button[data-biq-frame]"))
       b.setAttribute("aria-pressed",String(b.dataset.biqFrame===tf));
     drawPrivateChart();
     describeStructure();
   });
 window.addEventListener("resize",drawPrivateChart,{passive:true});
 function reset(){
  for(const id of ["biquote-private-quote","biquote-private-spread","biquote-observed",
    "biquote-m15","biquote-h1","biquote-h4","biquote-overlap"])
   $(id).textContent="غير متاح";
  privateStructure=null;
  setPrivateChart(null,"WAIT — بيانات الشارت الحقيقي غير متاحة أو منتهية الصلاحية. لا تُعرض شموع قديمة.");
 }
 async function refresh(){
  if(busy)return;
  busy=true;button.disabled=true;
  $("biquote-status").textContent="جارٍ فحص بيانات BiQuote المباشرة للقراءة فقط...";
  const viewer=secret.value.trim();
  const headers={Accept:"application/json"};
  if(viewer&&/^[A-Za-z0-9_-]{32,128}$/.test(viewer))headers.Authorization="Bearer "+viewer;
  try{
   const response=await fetch("/api/v3/ultimate/biquote-observation",{
      method:"GET",headers,redirect:"error",credentials:"omit",
      cache:"no-store",signal:AbortSignal.timeout(35000)});
   if(!response.ok){
     const failure=await response.json().catch(()=>null);
     if(failure&&failure.signal==="WAIT"&&failure.executable===false&&
        failure.researchEligible===false&&failure.rawQuoteShown===false&&
        failure.status==="WAIT_BIQUOTE_DATA_UNAVAILABLE"){
       const reason=Array.isArray(failure.blockerCodes)?failure.blockerCodes[0]:"";
       const messages={
         PROVIDER_REPORTED_CLOSED:"WAIT — BiQuote أفاد أن سوق الذهب مغلق؛ لا تحليل حي أو صفقة",
         CLOSED_CANDLE_STALE:"WAIT — الشموع المغلقة قديمة رغم وصول سعر؛ التحليل متوقف",
         QUOTE_STALE_OR_UNVERIFIED:"WAIT — آخر سعر غير حديث أو غير مؤكد",
         PUBLIC_HTTP_UNAVAILABLE:"WAIT — تعذّر الاتصال بأحد مصادر BiQuote العامة"
       };
       reset();
       $("biquote-status").textContent=messages[reason]||
         "WAIT — البيانات غير مكتملة أو غير صالحة للتحليل";
       return;
     }
     throw Error("فشل وصول المصدر أو البيانات غير صالحة (HTTP "+response.status+")");
   }
   const data=await response.json();
   if(data.signal!=="WAIT"||data.executable!==false||
      data.researchEligible!==false||data.tradePlanExecutable!==false||
      data.paperOrdersAllowed!==false||data.orderEndpointsCalled!==false||
      !["OBSERVED_READONLY_UNVERIFIED","WAIT_CROSS_FRAME_GAPS"].includes(data.status)||
      !data.frameSummary||!data.crossFrameComparisons||
      !["M15","H1","H4"].every(tf=>data.frameSummary[tf]&&
        Number.isInteger(data.frameSummary[tf].closedCount)&&
        data.frameSummary[tf].closedCount>=50))
     throw Error("رد غير آمن أو بيانات غير مؤهلة للعرض");
   $("biquote-status").textContent=data.status==="WAIT_CROSS_FRAME_GAPS"
      ?"WAIT — أسعار BiQuote وصلت، لكن فحص الشموع كشف فجوات أو اختلافات غير محسومة"
      :"BiQuote XAUUSD — عيّنة حقيقية فُحصت، القرار WAIT (لا أوامر)";
   $("biquote-observed").textContent=local(data.observedUTC)+
      " بيروت | عمر آخر سعر عند الفحص: "+fmt(data.quoteAgeSeconds)+" ثانية";
   if(data.rawQuoteShown===true&&
      Number.isFinite(data.bid)&&Number.isFinite(data.ask)&&data.ask>=data.bid){
     $("biquote-private-quote").textContent=fmt(data.bid)+" / "+fmt(data.ask);
     $("biquote-private-spread").textContent=fmt(data.ask-data.bid)+" دولار/أونصة";
   }else{
     $("biquote-private-quote").textContent="محجوب: أدخل رمز المشاهدة الخاص";
     $("biquote-private-spread").textContent="محجوب حتى التحقق من الرمز";
   }
   const acceptedChart=data.rawQuoteShown===true&&data.privateChartReadOnly===true&&
     data.privateChartDataBasis==="MID_WITH_POSSIBLE_BID_SEED"
       ?validPrivateChart(data.privateChart):null;
   privateStructure=acceptedChart?validPrivateStructure(data.privateStructure,acceptedChart):null;
   if(acceptedChart)setPrivateChart(acceptedChart,
     "شموع BiQuote مغلقة — عرض خاص READ-ONLY، MID وربما بذرة BID. "+
     (data.status==="WAIT_CROSS_FRAME_GAPS"?
       "بعض مجموعات H4 فيها تغطية M15 غير مكتملة، لا صفقات.":"مطابقة الأطر لا تثبت الترخيص أو الربحية."));
   else{
     privateStructure=null;
     setPrivateChart(null,
       "لا يوجد رمز مشاهدة صالح لعرض الشموع الخام. الاتجاهات الوصفية فقط ظاهرة للعامة.");
   }
   for(const tf of ["M15","H1","H4"]){
    const f=data.frameSummary[tf];
    $("biquote-"+tf.toLowerCase()).textContent=
      (label[f.descriptiveTrend]||"غير محسوم")+
      " | "+f.closedCount+" شمعة مغلقة | آخر إغلاق "+local(f.lastClosedUTC)+
      " | فجوات غير مصنّفة "+f.unclassifiedCalendarGaps;
   }
   const a=data.crossFrameComparisons.H1,b=data.crossFrameComparisons.H4;
   if(!a||!b||!Number.isInteger(a.completeMatches)||!Number.isInteger(b.completeMatches))
     throw Error("مقارنة الشموع ناقصة");
   $("biquote-overlap").textContent=
     "مطابقة H1: "+a.completeMatches+" | اختلاف "+a.completeMismatches+
     " | تغطية M15 ناقصة "+a.incompleteM15Groups+
     " — مطابقة H4: "+b.completeMatches+" | اختلاف "+b.completeMismatches+
     " | تغطية M15 ناقصة "+b.incompleteM15Groups+
     ". الفجوات ليست مصنفة كإغلاق سوق رسمي.";
  }catch(_err){
    reset();
    $("biquote-status").textContent="WAIT — لم تثبت صلاحية البيانات المباشرة. أعد الفحص لاحقاً.";
  }finally{busy=false;button.disabled=false;}
 }
 drawPrivateChart();
 button.addEventListener("click",refresh);
 window.addEventListener("pageshow",refresh);
 setInterval(()=>{if(!document.hidden&&!busy)refresh();},120000);
})();
