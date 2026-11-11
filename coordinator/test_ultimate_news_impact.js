'use strict';
const assert=require('node:assert/strict');
const {assessLayer}=require('./ultimate_v2_contracts');
const {classifyHeadline,reviewHeadlines}=require('./ultimate_news_impact');

const asOf='2026-11-10T12:00:00Z';
const feed={schemaVersion:2,role:'OBSERVED_NEWS',mode:'recorded',source:'Official Fed RSS (offline fixture)',
 availabilityEvidence:'fixture:known-at-snapshot',instrument:'GOLD_USD_NEWS',observedUTC:asOf,availableUTC:asOf,
 scope:'USD_GOLD_MATERIAL_NEWS',continuityVerified:true,coverageStartUTC:'2026-11-10T11:00:00Z',
 coverageEndUTC:asOf,coverageEvidenceReference:'fixture:coverage-window',
 rights:{status:'VERIFIED_INTERNAL_RESEARCH',algorithmicResearchAuthorized:true,evidenceReference:'fixture:rights'},
 events:[{id:'fed-1',impact:'medium',publishedUTC:'2026-11-10T11:50:00Z',availableUTC:'2026-11-10T11:51:00Z',
  title:'Fed signals dovish rate cut'}]};
const layer=assessLayer('headlines',feed,asOf);
assert.equal(layer.status,'READY');
const report=reviewHeadlines(feed,asOf,layer);
assert.equal(report.status,'RESEARCH_ONLY');
assert.equal(report.items[0].category,'DOVISH_MONETARY');
assert.equal(report.items[0].goldPressure,'UPWARD_PRESSURE');
assert.equal(report.items[0].confidence,'LOW');
assert.equal(report.directionalVote,false);assert.equal(report.executable,false);assert.equal(report.signal,'WAIT');

const fixture=(id,title,publishedUTC='2026-11-10T11:55:00Z',availableUTC='2026-11-10T11:56:00Z')=>
 ({id,title,publishedUTC,availableUTC});
assert.equal(classifyHeadline(fixture('war-1','Border attack escalates conflict'),feed,asOf).goldPressure,'UPWARD_PRESSURE');
assert.equal(classifyHeadline(fixture('cpi-1','Inflation rises in CPI release'),feed,asOf).goldPressure,'UNDETERMINED');
assert.equal(classifyHeadline(fixture('mix-1','Ceasefire agreement after missile attack'),feed,asOf).goldPressure,'UNDETERMINED');
assert.equal(classifyHeadline(fixture('unknown-1','Regional officials meet today'),feed,asOf).category,'UNKNOWN');
assert.equal(classifyHeadline(fixture('old-1','Fed rate hike','2026-11-10T11:00:00Z','2026-11-10T11:01:00Z'),feed,asOf).status,'STALE');
assert.equal(classifyHeadline(fixture('future-1','Fed rate hike','2026-11-10T12:01:00Z','2026-11-10T12:02:00Z'),feed,asOf).status,'BLOCKED_PROVENANCE');
assert.equal(classifyHeadline(fixture('no-source','Fed rate hike'),{},asOf).status,'BLOCKED_PROVENANCE');
assert.equal(reviewHeadlines(feed,asOf,{status:'UNAVAILABLE'}).status,'BLOCKED_SOURCE');
const duplicate={...feed,events:[feed.events[0],feed.events[0]]};
assert.equal(reviewHeadlines(duplicate,asOf,layer).status,'BLOCKED_DUPLICATE');
console.log('Ultimate rule-based news impact: provenance, as-of, stale, ambiguity and no-vote tests passed');
