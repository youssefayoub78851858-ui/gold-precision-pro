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
 let busy=false,activeFrame="M15",privateChart=null,privateStructure=null,privateMtf=null,privateReferenceEma=null,privateVendorSchedule=null;
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

 function validateMtf(input,structure){
   if(!structure||!input||input.mode!=="PRIVATE_READONLY_MTF_READINESS"||
      input.state!=="NO_TRADE_RESEARCH_ONLY"||input.signal!=="WAIT"||
      input.executable!==false||input.tradeEligible!==false||
      input.researchEligible!==false||input.paperOrdersAllowed!==false||
      input.validForEntry!==false||input.sessionCalendarVerified!==false||
      input.underlyingBrokerRightsVerified!==false||
      input.orderFlowIntegrated!==false||input.macroAndNewsIntegrated!==false||
      !["UNVERIFIED","OHLC_MISMATCH","PARTIAL_M15_CONSTITUENTS","MATCHED_COMPARED_WINDOWS_ONLY"]
        .includes(input.quality)||
      !["NOT_ASSESSABLE","OBSERVATION_ALL_ABOVE_EMA20",
        "OBSERVATION_ALL_BELOW_EMA20","OBSERVATION_MIXED_OR_AT_EMA20"]
        .includes(input.alignment)||
      !input.frameSummaries||!Array.isArray(input.blockerCodes)||
      input.blockerCodes.length<5||input.blockerCodes.length>12||
      !input.blockerCodes.every(x=>typeof x==="string"&&
        /^[A-Z0-9_]{8,90}$/.test(x)))return null;
   const accepted={};
   for(const tf of ["H4","H1","M15"]){
     const f=input.frameSummaries[tf],raw=structure[tf];
     if(!f||!raw||f.timeframe!==tf||
        !["FULL_CONTIGUOUS_TECHNICAL","PARTIAL_POST_GAP","INSUFFICIENT_OR_INVALID"]
          .includes(f.coverage)||
        !["ABOVE_EMA20","BELOW_EMA20","AT_EMA20","UNDETERMINED"].includes(f.direction)||
        !Number.isInteger(f.contiguousBars)||f.contiguousBars!==raw.contiguousBars||
        f.sessionCalendarVerified!==false||f.tradeEligible!==false||
        f.executable!==false)return null;
     if(f.coverage==="FULL_CONTIGUOUS_TECHNICAL" &&
       (f.contiguousBars<20||f.ema20Available!==true||
        f.direction==="UNDETERMINED"))return null;
     if(f.coverage!=="FULL_CONTIGUOUS_TECHNICAL" &&
       (f.ema20Available!==false||f.direction!=="UNDETERMINED"))return null;
     accepted[tf]={...f};
   }
   if(Object.values(accepted).some(x=>x.coverage!=="FULL_CONTIGUOUS_TECHNICAL") &&
      input.alignment!=="NOT_ASSESSABLE")return null;
   return {frames:accepted,alignment:input.alignment,quality:input.quality,
     blockerCodes:[...input.blockerCodes]};
 }
 function displayMtf(){
   const el=$("biquote-mtf-readiness");
   if(!el)return;
   if(!privateMtf){
     el.textContent="WAIT — التقييم الموحد محجوب حتى تأكيد الشموع ورمز المشاهدة الخاص.";
     return;
   }
   const tfName={H4:"H4 (الاتجاه الأكبر)",H1:"H1 (الساعة)",M15:"M15 (التوقيت)"};
   const name={ABOVE_EMA20:"السعر فوق EMA20 (وصفي)",
     BELOW_EMA20:"السعر تحت EMA20 (وصفي)",AT_EMA20:"السعر يلامس EMA20",
     UNDETERMINED:"غير محسوم (EMA20 غير متاح)"};
   const parts=["التقييم الموحد — WAIT، لا صفقات"];
   for(const tf of ["H4","H1","M15"]){
     const f=privateMtf.frames[tf];
     parts.push(tfName[tf]+": "+name[f.direction]+
       " | شموع متصلة "+f.contiguousBars+
       " | "+(f.coverage==="FULL_CONTIGUOUS_TECHNICAL"?"قراءة كاملة للفاصل":
         f.coverage==="PARTIAL_POST_GAP"?"تحليل جزئي بعد فجوة":"بيانات غير كافية"));
   }
   const quality={OHLC_MISMATCH:"اختلاف OHLC بين الفواصل",
     PARTIAL_M15_CONSTITUENTS:"تغطية M15 ناقصة لبعض شموع H4/H1",
     MATCHED_COMPARED_WINDOWS_ONLY:"المقاطع المتداخلة التي قورنت متطابقة فقط",
     UNVERIFIED:"لم يثبت تطابق الفواصل"};
   parts.push("التوافق الفني: "+(privateMtf.alignment==="NOT_ASSESSABLE"?
     "غير قابل للتقييم بسبب نقص بيانات الفواصل":
     privateMtf.alignment==="OBSERVATION_ALL_ABOVE_EMA20"?
       "الفواصل الثلاثة فوق EMA20 وصفياً":
       privateMtf.alignment==="OBSERVATION_ALL_BELOW_EMA20"?
       "الفواصل الثلاثة تحت EMA20 وصفياً":"قراءة مختلطة"));
   parts.push("سلامة تغطية الشموع: "+quality[privateMtf.quality]);
   parts.push("ما يزال ينقص: إثبات جلسات وحقوق وسيط MT5، بيانات BID/ASK تاريخية، "+
     "الأخبار وDXY والسندات وGC/Order Flow، واختبار ربحية مستقل. لا دخول أو SL أو TP.");
   el.textContent=parts.join("\n");
 }

 function validateReferenceEma(input,chart){
   if(!chart||!input||input.mode!=="PRIVATE_MID_OBSERVED_EMA_REFERENCE_ONLY"||
      input.signal!=="WAIT"||input.executable!==false||
      input.tradeEligible!==false||input.researchEligible!==false||
      input.paperOrdersAllowed!==false||input.validForEntry!==false||
      input.brokerSessionVerified!==false||input.upstreamRightsVerified!==false||
      input.decisionReady!==false||
      input.alignmentForTrading!=="NOT_ASSESSABLE"||!input.frames)return null;
   const accepted={};
   for(const tf of ["H4","H1","M15"]){
     const f=input.frames[tf];
     if(!f||f.signal!=="WAIT"||f.executable!==false||
        f.tradeEligible!==false||f.validForEntry!==false||
        f.brokerSessionVerified!==false||f.upstreamRightsVerified!==false||
        f.observationOnly!==true||f.gapsAssumedClosed!==false)return null;
     if(f.status==="NOT_ASSESSABLE"){
       if(f.ema20!==null||f.relation!=="NOT_ASSESSABLE")return null;
       accepted[tf]={status:"NOT_ASSESSABLE"};continue;
     }
     if(f.status!=="REFERENCE_PAUSE_CANDIDATE_ONLY"||
        f.basis!=="OBSERVED_CLOSED_MID_POSSIBLE_BID_SEED"||
        f.notForTrading!==true||f.observedBars!==chart[tf].length||
        f.lastObservedOpenUTC!==new Date(chart[tf].at(-1).t).toISOString()||
        f.reason!=="REFERENCE_CALENDAR_NOT_UNDERLYING_BROKER_VERIFIED"||
        !["ABOVE_REFERENCE_EMA20","BELOW_REFERENCE_EMA20","AT_REFERENCE_EMA20"].includes(f.relation)||
        ![f.ema20,f.lastClose].every(n=>typeof n==="number"&&Number.isFinite(n)&&n>0)||
        !Number.isInteger(f.referencePauseCandidateSlots)||f.referencePauseCandidateSlots<1||
        f.missingDuringReferenceTradingHours!==0||f.missingOutsideReference!==0)return null;
     accepted[tf]={status:f.status,ema20:f.ema20,
       relation:f.relation,slots:f.referencePauseCandidateSlots};
   }
   return accepted;
 }
 function displayReferenceEma(){
   const el=$("biquote-observed-ema");
   if(!el)return;
   if(!privateReferenceEma){
     el.textContent="WAIT — القراءة البحثية محجوبة دون بيانات مغلقة ورمز خاص صالح.";
     return;
   }
   const names={ABOVE_REFERENCE_EMA20:"السعر فوق المتوسط البحثي",
     BELOW_REFERENCE_EMA20:"السعر تحت المتوسط البحثي",
     AT_REFERENCE_EMA20:"السعر عند المتوسط البحثي"};
   const lines=["EMA20 من شموع مرصودة فعلياً عبر استراحات مرجعية فقط — ليس توصية"];
   for(const tf of ["H4","H1","M15"]){
     const f=privateReferenceEma[tf];
     lines.push(tf+": "+(f.status==="REFERENCE_PAUSE_CANDIDATE_ONLY"?
       "EMA20: "+fmt(f.ema20)+" | "+names[f.relation]+
       " | "+f.slots+" فترات غائبة تشبه توقفاً عادياً، غير مؤكدة"
       :"غير قابل للاحتساب بأمان من المرجع المتاح"));
   }
   lines.push("قرار التداول WAIT. لا إثبات لجدول جلسات الوسيط أو ترخيص البيانات، ولا تستخدم هذه القراءة لإشارات BUY/SELL أو مستويات SL/TP.");
   el.textContent=lines.join("\n");
 }

 function validateVendorSchedule(v,chart){
   if(!chart||!v||v.mode!=="BIQUOTE_VENDOR_DECLARED_SESSION_EVIDENCE_ONLY"||
      v.sourceRecord!=="BIQUOTE_SUPPORT_REPLY_2026_11_16"||
      v.providerSaysPrivateRenderResearchAllowed!==true||
      v.originalBrokerIdentified!==false||
      v.originalBrokerUpstreamRightsWarranted!==false||
      v.brokerIndependentScheduleVerified!==false||
      v.dstChangesIndependentlyVerified!==false||
      v.allowsGapBridging!==false||v.canIssueTradePlan!==false||
      v.signal!=="WAIT"||v.executable!==false||v.tradeEligible!==false||
      !v.frames)return null;
   const frames={};
   for(const tf of ["M15","H1","H4"]){
     const f=v.frames[tf];
     if(!f||f.timeframe!==tf||f.signal!=="WAIT"||
        f.executable!==false||f.tradeEligible!==false||
        f.allowsGapBridging!==false||
        f.brokerIndependentScheduleVerified!==false||
        f.status!=="NOT_INDEPENDENTLY_VERIFIED"||
        f.error!==undefined||!Array.isArray(f.examples)||f.examples.length>8||
        !["gapGroups","missingSlots","providerDeclaredPauseSlots",
          "missingDuringProviderTradingSlots","outsideDeclaredDateWindowSlots"]
          .every(k=>Number.isSafeInteger(f[k])&&f[k]>=0)||
        f.providerDeclaredPauseSlots+f.missingDuringProviderTradingSlots+
          f.outsideDeclaredDateWindowSlots!==f.missingSlots||
        f.gapGroups>chart[tf].length-1)return null;
     frames[tf]={
       gaps:f.gapGroups,missing:f.missingSlots,
       pause:f.providerDeclaredPauseSlots,
       open:f.missingDuringProviderTradingSlots,
       unknown:f.outsideDeclaredDateWindowSlots
     };
   }
   return frames;
 }
 function displayVendorSchedule(){
   const el=$("biquote-vendor-session");
   if(!el)return;
   if(!privateVendorSchedule){
     el.textContent="WAIT — فحص جلسات BiQuote الخاص غير متاح بلا بيانات حديثة ورمز مشاهدة صالح.";
     return;
   }
   const lines=["BiQuote أكدت في 16 نوفمبر 2026: الأحد 23:00 إلى الجمعة 22:00 UTC، "+
     "مع استراحة يومية 22:00–23:00 UTC. المواعيد قد تتحرك ساعة عند التوقيت الصيفي."];
   for(const tf of ["H4","H1","M15"]){
     const f=privateVendorSchedule[tf];
     lines.push(tf+": "+f.gaps+" مجموعات فجوات / "+f.missing+
       " فترات غائبة. تقع "+f.pause+" ضمن إغلاق أعلنت عنه BiQuote؛ "+
       f.open+" خلال وقت تداول معلن؛ "+f.unknown+" خارج نافذة التدقيق المحدودة.");
   }
   lines.push("الإذن الخاص: BiQuote سمحت بالبحث والتخزين والتداول الورقي على Render. "+
     "لكنها لم تضمن حقوق وسيط MT5 الأصلي، ولم تقدّم جدول عطلات أو تغيّر التوقيت بشكل مستقل. "+
     "هذا تدقيق احتمالي، لا يملأ شموعاً ولا يفعّل صفقات. القرار WAIT.");
   el.textContent=lines.join("\n");
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
   displayMtf();
   displayReferenceEma();
   displayVendorSchedule();
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
  privateStructure=null;privateMtf=null;privateReferenceEma=null;privateVendorSchedule=null;
  setPrivateChart(null,"WAIT — بيانات الشارت الحقيقي غير متاحة أو منتهية الصلاحية. لا تُعرض شموع قديمة.");
 }
 async function refresh(){
  if(busy)return;
  busy=true;button.disabled=true;
  $("biquote-status").textContent="جارٍ فحص بيانات BiQuote المباشرة للقراءة فقط...";
  const sessionState=$("biquote-viewer-session-state");
  try{
   // Only the one-time POST carries the secret. The chart GET uses an
   // HttpOnly, Secure, SameSite=Strict session cookie. Never browser storage.
   const viewer=secret.value.trim();
   if(viewer){
     if(!/^[A-Za-z0-9_-]{32,128}$/.test(viewer)){
       sessionState.textContent="رمز المشاهدة غير صالح. انسخ القيمة الكاملة من Render.";
       reset();
       return;
     }
     const authorized=await fetch("/api/v3/ultimate/biquote-viewer-session",{
       method:"POST",headers:{Authorization:"Bearer "+viewer,Accept:"application/json"},
       credentials:"same-origin",redirect:"error",cache:"no-store",
       signal:AbortSignal.timeout(12000)});
     const reply=await authorized.json().catch(()=>null);
     if(!authorized.ok||reply?.status!=="VIEWER_SESSION_READY"||
        reply?.signal!=="WAIT"||reply?.executable!==false){
       sessionState.textContent="تعذّر إنشاء جلسة المشاهدة. تأكد من الرمز ووصول Coordinator.";
       reset();
       return;
     }
     secret.value="";
     sessionState.textContent="جلسة مشاهدة آمنة لمدة 7 أيام من تسجيل الدخول. لن تحتاج الرمز بكل زيارة.";
   }
   const response=await fetch("/api/v3/ultimate/biquote-observation",{
      method:"GET",headers:{Accept:"application/json"},redirect:"error",
      credentials:"same-origin",cache:"no-store",
      signal:AbortSignal.timeout(35000)});
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
     $("biquote-private-quote").textContent="محجوب: سجّل جلسة المشاهدة";
     $("biquote-private-spread").textContent="محجوب حتى تفعيل الجلسة";
     sessionState.textContent="ما في جلسة مفعّلة أو انتهت صلاحيتها. أدخل الرمز مرة جديدة.";
   }
   const acceptedChart=data.rawQuoteShown===true&&data.privateChartReadOnly===true&&
     data.privateChartDataBasis==="MID_WITH_POSSIBLE_BID_SEED"
       ?validPrivateChart(data.privateChart):null;
   privateStructure=acceptedChart?validPrivateStructure(data.privateStructure,acceptedChart):null;
   privateMtf=privateStructure?validateMtf(data.privateStructure.multiFrame,privateStructure):null;
   privateReferenceEma=privateStructure?
     validateReferenceEma(data.privateStructure.referenceEmaResearch,acceptedChart):null;
   privateVendorSchedule=privateStructure?
     validateVendorSchedule(data.privateStructure.vendorDeclaredSession,acceptedChart):null;
   if(acceptedChart)setPrivateChart(acceptedChart,
     "شموع BiQuote مغلقة — عرض خاص READ-ONLY، MID وربما بذرة BID. "+
     (data.status==="WAIT_CROSS_FRAME_GAPS"?
       "بعض مجموعات H4 فيها تغطية M15 غير مكتملة، لا صفقات.":"مطابقة الأطر لا تثبت الترخيص أو الربحية."));
   else{
     privateStructure=null;privateMtf=null;privateReferenceEma=null;privateVendorSchedule=null;
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
 const logout=$("biquote-viewer-logout");
 if(logout)logout.addEventListener("click",async()=>{
   if(busy)return;
   logout.disabled=true;
   try{
     const out=await fetch("/api/v3/ultimate/biquote-viewer-session",{
       method:"DELETE",headers:{Accept:"application/json"},
       credentials:"same-origin",redirect:"error",cache:"no-store",
       signal:AbortSignal.timeout(12000)});
     if(!out.ok)throw Error("LOGOUT_FAILED");
     secret.value="";
     reset();
     $("biquote-viewer-session-state").textContent=
       "تم تسجيل الخروج من جلسة المشاهدة على هذا الهاتف.";
   }catch{
     $("biquote-viewer-session-state").textContent=
       "تعذّر تسجيل الخروج. الجلسة قد تبقى فعّالة حتى يؤكد الخادم.";
   }finally{logout.disabled=false;}
 });
 drawPrivateChart();
 button.addEventListener("click",refresh);
 window.addEventListener("pageshow",refresh);
 setInterval(()=>{if(!document.hidden&&!busy)refresh();},120000);
})();
