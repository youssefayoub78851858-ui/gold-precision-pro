"use strict";
/**
 * Private BiQuote display session for the review web service ONLY.
 * It does not authenticate broker, paper trading, or any other endpoint.
 * Server-only HMAC key, no viewer token in cookies, logs, or persistent JS storage.
 */
const crypto=require("node:crypto");
const COOKIE="__Host-gpp_biquote_viewer_v1";
const TTL_SECONDS=7*24*60*60;
const REVIEW_ORIGIN="https://gold-precision-v3-review-demo.onrender.com";
const KEY_NAME="GPP_BIQUOTE_VIEWER_SESSION_KEY";
const WAIT=Object.freeze({signal:"WAIT",executable:false,tradeEligible:false,
 paperOrdersAllowed:false,researchEligible:false});
function key(){
 const value=process.env[KEY_NAME];
 // No fallback to a random per-restart key or the broker/viewer secret.
 // Without a configured strong session signing key the feature stays off.
 if(typeof value!=="string"||! /^[A-Za-z0-9_-]{48,128}$/.test(value))return null;
 return Buffer.from(value,"utf8");
}
function mac(payload,k){
 return crypto.createHmac("sha256",k).update("gpp-biquote-review-only-v1:"+payload).digest("base64url");
}
function stamp(now){
 return Math.floor(now/1000);
}
function issue(now=Date.now()){
 const k=key();
 if(!k||!Number.isSafeInteger(now)||now<0)throw Error("SESSION_DISABLED");
 const issued=stamp(now),expiry=issued+TTL_SECONDS;
 const nonce=crypto.randomBytes(18).toString("base64url");
 const payload="v1."+issued+"."+expiry+"."+nonce;
 return {cookie:payload+"."+mac(payload,k),expiresUTC:new Date(expiry*1000).toISOString()};
}
function verify(cookie,now=Date.now()){
 const k=key();
 if(!k||typeof cookie!=="string"||cookie.length>300||!Number.isSafeInteger(now))return false;
 const parts=cookie.split(".");
 if(parts.length!==5||parts[0]!=="v1"||
    !/^[0-9]{10}$/.test(parts[1])||!/^[0-9]{10}$/.test(parts[2])||
    !/^[a-zA-Z0-9_-]{24}$/.test(parts[3])||
    !/^[a-zA-Z0-9_-]{43}$/.test(parts[4]))return false;
 const issued=Number(parts[1]),expiry=Number(parts[2]),current=stamp(now);
 if(expiry-issued!==TTL_SECONDS||issued>current+30||expiry<=current)return false;
 const payload=parts.slice(0,4).join("."),given=Buffer.from(parts[4],"base64url");
 const expected=Buffer.from(mac(payload,k),"base64url");
 return given.length===expected.length&&crypto.timingSafeEqual(given,expected);
}
function extract(header){
 if(typeof header!=="string"||header.length>8192)return null;
 const values=header.split(";").map(x=>x.trim());
 const exact=values.filter(x=>x.startsWith(COOKIE+"="));
 if(exact.length!==1)return null;
 return exact[0].slice(COOKIE.length+1);
}
function authenticated(headers,now=Date.now()){
 const h=headers||{};
 if(h["sec-fetch-site"]&&h["sec-fetch-site"]!=="same-origin"&&
    h["sec-fetch-site"]!=="none")return false;
 return verify(extract(h.cookie),now);
}
function sameOrigin(headers){
 const h=headers||{};
 return h.origin===REVIEW_ORIGIN &&
   (!h["sec-fetch-site"]||h["sec-fetch-site"]==="same-origin");
}
function setCookie(signed){
 if(typeof signed!=="string"||signed.length>300)throw Error("SESSION_INVALID");
 return COOKIE+"="+signed+"; Path=/; Max-Age="+TTL_SECONDS+
  "; Expires="+new Date(Date.now()+TTL_SECONDS*1000).toUTCString()+
  "; Secure; HttpOnly; SameSite=Strict";
}
function clearCookie(){
 return COOKIE+"=; Path=/; Max-Age=0; Expires=Thu, 01 Jan 1970 00:00:00 GMT; Secure; HttpOnly; SameSite=Strict";
}
module.exports={COOKIE,TTL_SECONDS,KEY_NAME,REVIEW_ORIGIN,WAIT,
 issue,verify,extract,authenticated,sameOrigin,setCookie,clearCookie};
