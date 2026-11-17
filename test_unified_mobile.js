'use strict';
const a=require('node:assert/strict'),fs=require('node:fs');
const doc=fs.readFileSync('ultimate.html','utf8'),legacy=fs.readFileSync('paper-terminal.html','utf8');
a(doc.includes('id="unified-mobile-trading"'));a(doc.includes('data-mode="REVIEW_PAPER_ONLY"'));
a(doc.includes('id="biquote-viewer-guide"'),"Mobile viewer control must be visible above private chart");
for(const id of ["gold-decision-center","gdc-title","gdc-decision","gdc-feed-status","gdc-observed","gdc-quote",
                 "gdc-h4","gdc-h1","gdc-m15","gdc-blocker"])
 a(doc.includes('id="'+id+'"'),"Missing owner-only mobile decision panel element: "+id);
a(doc.includes('data-approval="READ_ONLY_WAIT"'));
for(const id of ["gdc-source-proof","gdc-archive-proof","gdc-v3-proof","gdc-24h-audit","gdc-gates"])
 a(doc.includes('id="'+id+'"'),"Missing safe readiness gate: "+id);
a(doc.includes('href="/private-monitor#biquote-forward-panel"'),"Owner-only vault check must remain separate");
a(doc.includes('متطلبات المصادر: 0 / 9 مكتملة حسب سجل المتطلبات الثابت فقط'),"A 0/9 STATIC audit must not be labelled a realtime market status");
a(doc.includes('تعذّر التحقق؛ العدد غير معروف'),"Failed metadata check cannot default to fake readiness");
a(doc.includes('أرشيف BiQuote الخاص: غير مؤكد على الشاشة العامة'),"No fabricated forward-vault status");
a(doc.includes('مراقبة BiQuote المكتملة بتاريخ 17 نوفمبر 2026'),"Timestamped historical report, not current live feed");
a(doc.includes('691 استجابة كاملة و29 عينة ناقصة HTTP/JSON'),"Show 720-slot quality failures");
a(doc.includes('كلّها بين 22:03 و22:59 UTC'),"Failures are confined to dated vendor-declared reference break");
a(doc.includes('من دون تأكيد مستقل لجلسة الوسيط'),"Never certify independent broker calendar by timing coincidence");
a(doc.includes('صفر فحص جودة كامل ناجح'),"No fake qualification from zero price mismatches");
a(doc.includes('الأرشفة التلقائية محجوبة وقرار الصفقات WAIT'),"Source-quality veto stays visible");
for(const id of ["gdc-four-stage-batch","gdc-batch-data","gdc-batch-archive",
                 "gdc-batch-engine","gdc-batch-paper"])
 a(doc.includes('id="'+id+'"'),"Four-stage batch status not visible: "+id);
a(doc.includes('اختبار المسار البرمجي المتكامل نجح ببيانات اختبارية غير حقيقية'));
a(doc.includes('الوصلة جاهزة · التفعيل غير مثبت'));
a(doc.includes('التداول اليدوي التجريبي منفصل'));
a(doc.includes('إشاراته محجوبة'));
a(!doc.includes('الصفقات الحقيقية جاهزة'));

a(doc.includes('href="#biquote-live-chart-panel"'),"Mobile chart nav should open real read-only chart");
a(doc.includes('href="#paper-actions"'),"Paper controls clearly separate from real data");
a(doc.includes('خطة الصفقة — غير مفعّلة'));
a(doc.includes('<strong>—</strong>'),"No fabricated entry/SL/TP");
a(doc.indexOf('id="biquote-viewer-secret"')<doc.indexOf('id="biquote-live-canvas"'),
 "Show private viewer input before blank protected chart on mobile");
a(doc.indexOf('id="biquote-refresh"')<doc.indexOf('id="biquote-live-canvas"'),
 "Refresh control must precede protected chart");
a(!doc.includes('href="/paper-terminal"'));a(!/<iframe\b/i.test(doc));
for(const id of ['unified-trading-title','paper-overview','paper-chart','paper-analysis','paper-actions','paper-statistics','chart','paper-buy','paper-sell','paper-close','trade-rows','stat-net','stat-dd','stop-selftest','overview-system','overview-signal','macro-refresh'])
 a(doc.includes('id="'+id+'"'),'Missing merged component: '+id);
for(const src of ['/paper-terminal-core.js','/paper-terminal-ui.js'])a(doc.includes('src="'+src+'"'));
a(doc.indexOf('src="/paper-terminal-core.js"')<doc.indexOf('src="/paper-terminal-ui.js"'));
const ids=[...doc.matchAll(/\bid=["']([^"']+)["']/g)].map(x=>x[1]);
a.equal(new Set(ids).size,ids.length,'Duplicate DOM ID');
for(const id of [...legacy.matchAll(/\bid=["']([^"']+)["']/g)].map(x=>x[1]))a(ids.includes(id),'Legacy paper UI element absent: '+id);
a(/#unified-mobile-trading\s+button/.test(doc),'Paper buttons CSS not scoped');
a(/#unified-mobile-trading\s+#chart/.test(doc),'Paper chart CSS not scoped');
for(const id of ['multi-source-readiness','multi-source-check','multi-source-state','multi-source-grid'])
 a(doc.includes('id="'+id+'"'),'Missing source inventory panel: '+id);
a(doc.includes('/api/v3/ultimate/multi-source-readiness'));
a(doc.includes('WAIT'));
for(const id of ['biquote-mobile-observation','biquote-private-quote','biquote-private-spread',
                  'biquote-status','biquote-observed','biquote-m15','biquote-h1','biquote-h4',
                  'biquote-structure-summary','biquote-mtf-readiness','biquote-observed-ema','biquote-vendor-session',
                  'biquote-overlap','biquote-viewer-secret','biquote-refresh'])
 a(doc.includes('id="'+id+'"'),'Missing read-only BiQuote UI: '+id);
a(doc.includes('src="/biquote-mobile-ui.js"'));
for(const id of ['biquote-live-chart-panel','biquote-live-canvas','biquote-live-caption'])
 a(doc.includes('id="'+id+'"'),'Missing PRIVATE BiQuote chart UI: '+id);
a(doc.includes('data-biq-frame="M15"')&&doc.includes('data-biq-frame="H1"')&&doc.includes('data-biq-frame="H4"'));
a(doc.includes('شارت محاكاة ورقية XAUUSD'),'Paper replay chart must be unmistakably labelled');
a(doc.includes('شموع MID من BiQuote'),'Actual closed MID source must be labelled');

const server=fs.readFileSync('server.js','utf8');
a(server.includes('paperPath==="/paper-terminal" || paperPath==="/paper-terminal.html"'));
a(server.includes('"/api/v3/ultimate/biquote-observation"'));
a(server.includes('"/biquote-mobile-ui.js":"biquote-mobile-ui.js"'));
const script=fs.readFileSync('biquote-mobile-ui.js','utf8');
a(script.includes('signal!=="WAIT"'));
a(!script.includes('localStorage')&&!script.includes('sessionStorage'));
a(!script.includes('paper-buy')&&!script.includes('paper-sell'));
a(script.includes('data.rawQuoteShown===true&&data.privateChartReadOnly===true'));
a(script.includes('validPrivateChart(data.privateChart)'));
a(script.includes('setPrivateChart(null,'));
a(!script.includes('window.GoldPaperCore')&&!script.includes('C.open('),
 'BiQuote live chart must never reach paper core trade execution');
a(script.includes('privateChart=null,privateStructure=null,privateMtf=null'));
a(script.includes('validateMtf(data.privateStructure.multiFrame,privateStructure)'));
a(script.includes('displayMtf()'));
a(script.includes('validateReferenceEma(data.privateStructure.referenceEmaResearch,acceptedChart)'));
a(script.includes('displayReferenceEma()'));
a(script.includes('validateVendorSchedule(data.privateStructure.vendorDeclaredSession,acceptedChart)'));
a(script.includes('displayVendorSchedule()'));
a(script.includes('decisionCenterObserved(data,acceptedChart)'));
a(script.includes('decisionCenterReset()'));
a(!script.includes('document.cookie'));
a(!script.includes('window.GoldPaperCore'));
a(script.includes('validPrivateStructure(data.privateStructure,acceptedChart)'));
a(script.includes('f.contiguousBars<7'));
a(script.includes('PARTIAL_OBSERVATION_UNVERIFIED_SESSION'));
a(script.includes('unclassifiedGapsRemainBlocked'));
a(!script.includes('window.GoldPaperCore'));


console.log('PASS unified mobile: chart, trade, journal and research in /ultimate, no iframe or duplicate IDs');
