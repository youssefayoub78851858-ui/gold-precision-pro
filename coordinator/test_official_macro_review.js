"use strict";
const assert=require("node:assert/strict");
const {parseFedPolicyRss,newYorkToUTC,parseBlsCalendar,getOfficialMacroReview,FED_URL,BLS_URL}=require("./official_macro_review");
const now=new Date("2026-11-11T14:30:00Z");
const rss=`<?xml version="1.0"?><rss version="2.0"><channel><title>FRB</title>
<item><title>Federal Reserve issues FOMC statement</title>
<link><![CDATA[https://www.federalreserve.gov/newsevents/pressreleases/monetary20261028a.htm]]></link>
<pubDate><![CDATA[Wed, 28 Oct 2026 18:00:00 GMT]]></pubDate></item>
<item><title>Minutes of the Federal Open Market Committee &amp; policy</title>
<link><![CDATA[https://www.federalreserve.gov/newsevents/pressreleases/monetary20261007a.htm]]></link>
<pubDate><![CDATA[Wed, 07 Oct 2026 18:00:00 GMT]]></pubDate></item>
</channel></rss>`;
const ics=`BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:ppi-1
DTSTART;TZID=US-Eastern:20261113T083000
SUMMARY:Producer Price Index
END:VEVENT
BEGIN:VEVENT
UID:jobs-1
DTSTART;TZID=US-Eastern:20261204T083000
SUMMARY:Employment Situation
END:VEVENT
BEGIN:VEVENT
UID:old-1
DTSTART;TZID=US-Eastern:20261110T083000
SUMMARY:Consumer Price Index
END:VEVENT
BEGIN:VEVENT
UID:noise-1
DTSTART;TZID=US-Eastern:20261117T110000
SUMMARY:Employee Recreation and Lunches
END:VEVENT
END:VCALENDAR`;
async function main(){
 const stories=parseFedPolicyRss(rss,now);
 assert.equal(stories.length,2);
 assert.match(stories[1].title,/& policy/);
 assert.equal(stories[0].publishedUTC,"2026-10-28T18:00:00.000Z");
 assert.equal(newYorkToUTC("20261113","083000"),"2026-11-13T13:30:00.000Z"); // EST
 assert.equal(newYorkToUTC("20260713","083000"),"2026-07-13T12:30:00.000Z"); // EDT
 const events=parseBlsCalendar(ics,now);
 assert.equal(events.length,2);
 assert.equal(events[0].kind,"PPI");
 assert.equal(events[1].kind,"JOBS");
 assert.equal(events[0].scheduledUTC,"2026-11-13T13:30:00.000Z");
 assert.equal(events[0].eventType,"SCHEDULED_NOT_RELEASED");
 assert.throws(()=>parseBlsCalendar("garbage",now),/BLS_FORMAT/);
 assert.throws(()=>parseFedPolicyRss("bad",now),/FED_FORMAT/);
 const requests=[];
 const fetchFn=async url=>{
   requests.push(url);
   if(url===FED_URL)return {ok:true,text:async()=>rss};
   if(url===BLS_URL)return {ok:true,text:async()=>ics};
   throw Error("No third-party network allowed");
 };
 const result=await getOfficialMacroReview({fetchFn,nowMs:now.getTime()});
 assert.equal(result.mode,"OFFICIAL_MACRO_REVIEW");
 assert.equal(result.signal,"WAIT");
 assert.equal(result.executable,false);
 assert.equal(result.liveData,false);
 assert.equal(result.automaticTrading,false);
 assert.equal(result.feeds.fed,"OFFICIAL_REFRESHED");
 assert.equal(result.feeds.bls,"OFFICIAL_REFRESHED");
 assert.equal(result.headlines.length,2);
 assert.equal(result.calendar.length,2);
 assert.equal(requests.length,2);
 const cached=await getOfficialMacroReview({nowMs:now.getTime()+1000,fetchFn:()=>{throw Error("Should be cached");}});
 assert.equal(cached.calendar.length,2);
 const offline=await getOfficialMacroReview({offline:true});
 assert.equal(offline.feeds.fed,"OFFLINE_TEST");
 assert.equal(offline.headlines.length,0);
 assert.equal(offline.executable,false);
 console.log("PASS: official macro RSS and ICS, daylight-saving, source-gating and no-trade contract");
}
main().catch(e=>{console.error(e);process.exitCode=1;});
