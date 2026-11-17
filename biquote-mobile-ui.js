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
 let busy=false;
 function reset(){
  for(const id of ["biquote-private-quote","biquote-private-spread","biquote-observed",
    "biquote-m15","biquote-h1","biquote-h4","biquote-overlap"])
   $(id).textContent="غير متاح";
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
 button.addEventListener("click",refresh);
 window.addEventListener("pageshow",refresh);
 setInterval(()=>{if(!document.hidden&&!busy)refresh();},120000);
})();
