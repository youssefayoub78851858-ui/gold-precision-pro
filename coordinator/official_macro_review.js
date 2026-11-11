"use strict";
// Official macro schedule + monetary-policy headlines for RESEARCH DISPLAY ONLY.
// Does not feed trading gates, infer surprises/sentiment or access brokers.
const FED_URL="https://www.federalreserve.gov/feeds/press_monetary.xml";
const BLS_URL="https://www.bls.gov/schedule/news_release/bls.ics";
let memo=null, expires=0, inflight=null;
function unescapeXml(s){
 return String(s||"").replace(/^<!\[CDATA\[|\]\]>$/g,"").replace(/&#(x[0-9a-f]+|\d+);|&(amp|quot|apos|lt|gt);/gi,(all,num,ent)=>{
  if(num){const hex=num[0].toLowerCase()==="x";const n=Number.parseInt(hex?num.slice(1):num,hex?16:10);
   return n>=32&&n<=0x10ffff?String.fromCodePoint(n):"";}
  return {amp:"&",quot:'"',apos:"'",lt:"<",gt:">"}[ent.toLowerCase()]||"";
 }).trim();
}
function inner(xml,key){
 const m=xml.match(new RegExp("<"+key+"(?:\\s[^>]*)?>([\\s\\S]*?)<\\/"+key+">","i"));
 return m?unescapeXml(m[1]):"";
}
function parseFedPolicyRss(xml,now=new Date()){
 if(typeof xml!=="string"||xml.length>250000||!xml.includes("<rss"))throw Error("FED_FORMAT");
 const items=[...xml.matchAll(/<item(?:\s[^>]*)?>([\s\S]*?)<\/item>/gi)].slice(0,40);
 if(!items.length)throw Error("FED_NO_ITEMS");
 const nowMs=now.getTime(),seen=new Set(),out=[];
 for(const m of items){
  const title=inner(m[1],"title").replace(/\s+/g," ").slice(0,190);
  const link=inner(m[1],"link");
  const rawDate=inner(m[1],"pubDate"),time=Date.parse(rawDate);
  if(!title||!Number.isFinite(time)||time>nowMs+300000||nowMs-time>120*86400000)continue;
  let url;try{url=new URL(link);}catch{continue;}
  if(url.protocol!=="https:"||url.hostname!=="www.federalreserve.gov"||
     !url.pathname.startsWith("/newsevents/pressreleases/"))continue;
  if(seen.has(url.href))continue; seen.add(url.href);
  out.push({title,url:url.href,publishedUTC:new Date(time).toISOString(),source:"Federal Reserve",eventType:"RELEASED_POLICY_HEADLINE"});
 }
 out.sort((a,b)=>b.publishedUTC.localeCompare(a.publishedUTC));
 if(!out.length)throw Error("FED_NO_VALID_RELEASE");
 return out.slice(0,6);
}
function newYorkToUTC(ymd,hms){
 if(!/^\d{8}$/.test(ymd)||!/^\d{6}$/.test(hms))throw Error("BLS_TIME");
 const year=Number(ymd.slice(0,4)),month=Number(ymd.slice(4,6)),day=Number(ymd.slice(6,8)),
  hh=Number(hms.slice(0,2)),mm=Number(hms.slice(2,4)),ss=Number(hms.slice(4,6));
 if(year<2020||year>2035||month<1||month>12||hh>23||mm>59||ss>59)throw Error("BLS_TIME");
 const midday=new Date(Date.UTC(year,month-1,day,16,0,0));
 const tn=new Intl.DateTimeFormat("en-US",{timeZone:"America/New_York",timeZoneName:"shortOffset"}).formatToParts(midday).find(p=>p.type==="timeZoneName")?.value;
 const m=tn?.match(/^GMT([+-])(\d{1,2})(?::(\d{2}))?$/);
 if(!m)throw Error("BLS_TZ");
 const offset=(m[1]==="-"?-1:1)*(Number(m[2])*60+Number(m[3]||0));
 const naive=Date.UTC(year,month-1,day,hh,mm,ss);
 const utc=new Date(naive-offset*60000);
 // Reject calendar overflow/invalid dates.
 const parts=new Intl.DateTimeFormat("en-CA",{timeZone:"America/New_York",year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",hourCycle:"h23",minute:"2-digit",second:"2-digit"}).formatToParts(utc);
 const obj=Object.fromEntries(parts.map(x=>[x.type,x.value]));
 if(Number(obj.year)!==year||Number(obj.month)!==month||Number(obj.day)!==day||
    Number(obj.hour)!==hh||Number(obj.minute)!==mm||Number(obj.second)!==ss)throw Error("BLS_TZ_MISMATCH");
 return utc.toISOString();
}
function eventKind(name){
 if(/consumer price index/i.test(name))return "CPI";
 if(/producer price index/i.test(name))return "PPI";
 if(/employment situation/i.test(name))return "JOBS";
 if(/job openings and labor turnover/i.test(name))return "JOLTS";
 if(/employment cost index/i.test(name))return "ECI";
 if(/import and export price/i.test(name))return "IMPORT_EXPORT";
 if(/productivity and costs/i.test(name))return "PRODUCTIVITY";
 if(/real earnings/i.test(name))return "REAL_EARNINGS";
 return null;
}
function parseBlsCalendar(ics,now=new Date()){
 if(typeof ics!=="string"||ics.length>500000||!ics.includes("BEGIN:VCALENDAR"))throw Error("BLS_FORMAT");
 const unfolded=ics.replace(/\r?\n[ \t]/g,"").replace(/\r/g,"");
 const blocks=unfolded.split("BEGIN:VEVENT").slice(1);
 if(!blocks.length||blocks.length>3000)throw Error("BLS_NO_EVENTS");
 const events=[],seen=new Set(),base=now.getTime(),end=base+30*86400000;
 for(const block of blocks){
  const content=block.split("END:VEVENT")[0];
  const fields=content.split("\n");
  const pick=key=>{const line=fields.find(x=>x.startsWith(key));return line?line.slice(line.indexOf(":")+1).trim():"";};
  const summary=pick("SUMMARY:").replace(/\\([,;\\n])/g,"$1").slice(0,160);
  const kind=eventKind(summary);
  if(!kind)continue;
  const start=fields.find(x=>x.startsWith("DTSTART"));
  if(!start||!/^DTSTART;TZID=(?:US-Eastern|America\/New_York):\d{8}T\d{6}$/.test(start))continue;
  const value=start.slice(start.indexOf(":")+1);
  let utc;try{utc=newYorkToUTC(value.slice(0,8),value.slice(9));}catch{continue;}
  const timestamp=Date.parse(utc);
  if(timestamp<base||timestamp>end)continue;
  const uid=pick("UID:")||kind+utc;
  if(seen.has(uid))continue;seen.add(uid);
  events.push({title:summary,kind,scheduledUTC:utc,localTimezone:"America/New_York",source:"U.S. Bureau of Labor Statistics",eventType:"SCHEDULED_NOT_RELEASED"});
 }
 events.sort((a,b)=>a.scheduledUTC.localeCompare(b.scheduledUTC));
 return events.slice(0,12);
}
async function getOfficialMacroReview({fetchFn=fetch,nowMs=Date.now(),offline=false}={}){
 if(offline)return {mode:"OFFICIAL_MACRO_REVIEW",signal:"WAIT",executable:false,trading:"disabled",liveData:false,
  feeds:{fed:"OFFLINE_TEST",bls:"OFFLINE_TEST"},headlines:[],calendar:[],note:"Offline tests: no provider requests",updatedUTC:null};
 if(memo&&nowMs<expires)return memo;
 if(inflight)return inflight;
 inflight=(async()=>{
  const config=[
   {id:"fed",url:FED_URL,max:250000,parser:(body)=>parseFedPolicyRss(body,new Date(nowMs))},
   {id:"bls",url:BLS_URL,max:500000,parser:(body)=>parseBlsCalendar(body,new Date(nowMs))}
  ];
  const results=await Promise.all(config.map(async c=>{
   try{
    const response=await fetchFn(c.url,{signal:AbortSignal.timeout(8500),
     headers:{Accept:c.id==="fed"?"application/rss+xml,text/xml":"text/calendar","User-Agent":"GoldPrecisionPro-Research-Review/1.0"}});
    if(!response.ok)throw Error("HTTP_"+response.status);
    const body=await response.text();
    if(body.length>c.max)throw Error("OVERSIZE");
    return {status:"OFFICIAL_REFRESHED",items:c.parser(body)};
   }catch(e){const code=String(e.message||"").slice(0,40);
    console.warn("Official macro source unavailable: "+c.id+" "+(code.startsWith("HTTP_")?"HTTP_ERROR":"PARSER_OR_NETWORK_ERROR"));
    return {status:"UNAVAILABLE",items:[]};
   }
  }));
  // Missing sources never magically become verified events. No trading authority.
  const value={mode:"OFFICIAL_MACRO_REVIEW",signal:"WAIT",executable:false,trading:"disabled",liveData:false,
   researchOnly:true,automaticTrading:false,firstAvailabilityVerified:false,
   marketDataRequests:0,marketPrice:null,macroSentiment:null,
   checkedUTC:new Date(nowMs).toISOString(),
   feeds:{fed:results[0].status,bls:results[1].status},
   headlines:results[0].items,calendar:results[1].items,
   fedSource:FED_URL,blsSource:BLS_URL,
   note:"Fed RSS and BLS calendar are public release metadata, not evidence of market surprise, actual-vs-consensus, or an intraday trading signal."
  };
  memo=value;expires=nowMs+(results.every(x=>x.status==="OFFICIAL_REFRESHED")?30:5)*60000;
  return value;
 })();
 try{return await inflight;}finally{inflight=null;}
}
module.exports={FED_URL,BLS_URL,parseFedPolicyRss,newYorkToUTC,parseBlsCalendar,getOfficialMacroReview};
