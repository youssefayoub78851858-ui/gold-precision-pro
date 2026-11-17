'use strict';
const a=require('node:assert/strict'),fs=require('node:fs');
const doc=fs.readFileSync('ultimate.html','utf8'),legacy=fs.readFileSync('paper-terminal.html','utf8');
a(doc.includes('id="unified-mobile-trading"'));a(doc.includes('data-mode="REVIEW_PAPER_ONLY"'));
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
a(!script.includes('GoldPaperCore')&&!script.includes('paper-terminal-core'));
a(script.includes('privateChart=null'));


console.log('PASS unified mobile: chart, trade, journal and research in /ultimate, no iframe or duplicate IDs');
