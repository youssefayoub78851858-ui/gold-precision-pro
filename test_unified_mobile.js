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
a(doc.includes('WAIT'));
console.log('PASS unified mobile: chart, trade, journal and research in /ultimate, no iframe or duplicate IDs');
