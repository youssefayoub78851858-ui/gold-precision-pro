'use strict';
// Explainable headline tagging for research. It is a ruleset, not an AI model,
// news feed, market prediction, or trading vote.
const {time}=require('./ultimate_v2_contracts');

const DIRECTIONS=new Set(['UPWARD_PRESSURE','DOWNWARD_PRESSURE','UNDETERMINED']);
const RX={
  hawkish:/(hawkish|rate hike|higher rates|tighten(?:ing)?|restrictive|يرفع الفائدة|تشديد نقدي)/i,
  dovish:/(dovish|rate cut|lower rates|eas(?:ing|ier)|accommodative|خفض الفائدة|تيسير نقدي)/i,
  geopolitical:/(war|attack|missile|invasion|sanction|conflict|escalat|ضربة|حرب|صاروخ|غزو|عقوبات|تصعيد)/i,
  deescalation:/(ceasefire|peace deal|de.?escalat|truce|هدنة|وقف إطلاق النار|اتفاق سلام|خفض التصعيد)/i,
  inflation:/(inflation|CPI|PCE|consumer prices|التضخم|أسعار المستهلك)/i,
  macroRelease:/(jobs report|payrolls|GDP|ISM|employment|بيانات الوظائف|الناتج المحلي)/i
};
function classifyHeadline(event,feed,asOfUTC){
  const now=time(asOfUTC),published=time(event?.publishedUTC),available=time(event?.availableUTC);
  const base={id:event?.id??null,title:event?.title??null,source:feed?.source??null,
    publishedUTC:event?.publishedUTC??null,availableUTC:event?.availableUTC??null,
    signal:'WAIT',executable:false,directionalVote:false};
  if(!Number.isFinite(now)||!event||typeof event.title!=='string'||!event.title.trim()||
     !event.id||typeof feed?.source!=='string'||!feed.source.trim()||
     !Number.isFinite(published)||!Number.isFinite(available)||published>available||available>now)
    return {...base,status:'BLOCKED_PROVENANCE',category:'UNKNOWN',goldPressure:'UNDETERMINED',confidence:'NONE',reason:'Headline needs a unique id, source and UTC publication/availability times known by the snapshot'};
  if(now-published>30*60*1000)
    return {...base,status:'STALE',category:'UNKNOWN',goldPressure:'UNDETERMINED',confidence:'NONE',reason:'Headline is older than the 30-minute review window'};
  const title=event.title.normalize('NFKC').replace(/\s+/g,' ').trim();
  const tags=[];
  if(RX.hawkish.test(title))tags.push('HAWKISH_MONETARY');
  if(RX.dovish.test(title))tags.push('DOVISH_MONETARY');
  if(RX.geopolitical.test(title))tags.push('GEOPOLITICAL_RISK');
  if(RX.deescalation.test(title))tags.push('RISK_EASING');
  if(RX.inflation.test(title))tags.push('INFLATION_OR_PRICES');
  if(RX.macroRelease.test(title))tags.push('MACRO_RELEASE');
  if(tags.length===0)return {...base,status:'REVIEWED_UNCLASSIFIED',category:'UNKNOWN',goldPressure:'UNDETERMINED',confidence:'LOW',reason:'No rule matched; the system does not infer an effect from an unfamiliar headline'};
  const upward=tags.includes('DOVISH_MONETARY')||tags.includes('GEOPOLITICAL_RISK');
  const downward=tags.includes('HAWKISH_MONETARY')||tags.includes('RISK_EASING');
  const mixed=(upward&&downward)||tags.includes('INFLATION_OR_PRICES')||tags.includes('MACRO_RELEASE');
  let category,pressure,confidence='LOW';
  if(mixed||tags.includes('INFLATION_OR_PRICES')||tags.includes('MACRO_RELEASE')){
    category='MIXED_OR_DATA_DEPENDENT';pressure='UNDETERMINED';
  }else if(tags.includes('HAWKISH_MONETARY')){
    category='HAWKISH_MONETARY';pressure='DOWNWARD_PRESSURE';confidence='LOW';
  }else if(tags.includes('DOVISH_MONETARY')){
    category='DOVISH_MONETARY';pressure='UPWARD_PRESSURE';confidence='LOW';
  }else if(tags.includes('GEOPOLITICAL_RISK')){
    category='GEOPOLITICAL_RISK';pressure='UPWARD_PRESSURE';confidence='LOW';
  }else{
    category='RISK_EASING';pressure='DOWNWARD_PRESSURE';confidence='LOW';
  }
  return {...base,status:'RULE_TAGGED',category,goldPressure:pressure,confidence,tags,
    reason:'Keyword-based scenario only; actual gold response depends on expectations, price and other markets'};
}
function reviewHeadlines(feed,asOfUTC,layer){
  const empty={status:'BLOCKED_SOURCE',source:feed?.source??null,signal:'WAIT',executable:false,
    directionalVote:false,items:[],reason:layer?.reason||'A complete, admissible past-news feed is not available'};
  if(layer?.status!=='READY')return empty;
  if(!Array.isArray(feed?.events))return {...empty,status:'BLOCKED_SOURCE'};
  const ids=new Set(),items=[];
  for(const event of feed.events){
    if(ids.has(event?.id))return {...empty,status:'BLOCKED_DUPLICATE',reason:'Duplicate headline IDs are rejected'};
    ids.add(event?.id);items.push(classifyHeadline(event,feed,asOfUTC));
  }
  return {status:'RESEARCH_ONLY',source:feed.source,coverageStartUTC:feed.coverageStartUTC,
    coverageEndUTC:feed.coverageEndUTC,signal:'WAIT',executable:false,directionalVote:false,items,
    reason:'Source-gated, past-only rules review; no AI model or trading signal is used'};
}
module.exports={classifyHeadline,reviewHeadlines};
