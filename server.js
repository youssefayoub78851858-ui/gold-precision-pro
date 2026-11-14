const { backtest } = require("./backtest");
const { analyze, ema, rsi } = require("./strategy");
const http = require("http");
const fs = require("fs");
const path = require("path");
const PORT = process.env.PORT || 3000;
const DEMO_MODE = process.env.DEMO_MODE === "standby";
const v2Api = DEMO_MODE ? null : require("./coordinator/service/server");
const BROKER_URL = process.env.MARKET_DATA_BROKER_URL;
const BROKER_TOKEN = process.env.BROKER_TOKEN || "";
const API_KEY = Boolean(BROKER_URL && BROKER_TOKEN.length >= 32);
const FRAME_MS = {"15min":900000,"1h":3600000,"4h":14400000};

const cache = new Map();
const intervals = new Set(["15min", "1h", "4h"]);

async function requestBrokerCandles(interval, outputsize, endDate = null) {
  const endpoint = new URL("/time_series", BROKER_URL);
  endpoint.searchParams.set("symbol", "XAU/USD");
  endpoint.searchParams.set("interval", interval);
  endpoint.searchParams.set("outputsize", String(outputsize));
  endpoint.searchParams.set("timezone", "UTC");
  if (endDate) endpoint.searchParams.set("end_date", endDate);
  const response = await fetch(endpoint, {
    signal: AbortSignal.timeout(12000),
    headers: { Authorization: "Bearer " + BROKER_TOKEN }
  });
  const result = await response.json();
  return { response, result };
}

function send(res, status, data) {
  res.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Access-Control-Allow-Origin":
      "https://youssefayoub78851858-ui.github.io",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type"
  });
  res.end(JSON.stringify(data));
}

const server = http.createServer(async (req, res) => {
  if (req.method === "OPTIONS") {
    return send(res, 200, {});
  }

  // Gated viewer bridge for public REVIEW DEMO only; NEVER broker admin routes.
  if(req.url.split("?")[0]==="/private-monitor"){
   if(req.method!=="GET")return send(res,405,{error:"GET only"});
   if(!DEMO_MODE)return send(res,404,{error:"Not found"});
   res.writeHead(200,{"Content-Type":"text/html; charset=utf-8",
    "Cache-Control":"no-store","Referrer-Policy":"no-referrer",
    "X-Content-Type-Options":"nosniff",
    "Content-Security-Policy":"default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'"});
   return res.end(fs.readFileSync(path.join(__dirname,"private-monitor.html")));
  }
  if(req.url.split("?")[0]==="/api/v3/monitor/status"){
   if(req.method!=="GET")return send(res,405,{error:"GET only"});
   const result=await require("./coordinator/review_monitor_proxy").relay(req.headers.authorization,{
    approved:DEMO_MODE&&process.env.PRIVATE_MONITOR_PROXY_APPROVED==="1"
   });
   res.writeHead(result.httpStatus,{"Content-Type":"application/json; charset=utf-8",
    "Cache-Control":"no-store","Referrer-Policy":"no-referrer","X-Content-Type-Options":"nosniff"});
   return res.end(JSON.stringify(result.body));
  }

  // Public REVIEW-DEMO FXCM readiness: facts only; no market or private-coordinator connection.
  if(req.url.split("?")[0]==="/api/v3/ultimate/fxcm-readiness"){
    if(req.method!=="GET")return send(res,405,{error:"GET only",signal:"WAIT",executable:false});
    if(!DEMO_MODE)return send(res,503,{status:"STANDBY_ONLY",signal:"WAIT",executable:false});
    const result=require("./coordinator/fxcm_public_readiness").readOnlyStatus();
    if(result.mode!=="OFFLINE_PREPARATION_ONLY"||result.signal!=="WAIT"||
       result.executable!==false||result.researchEligible!==false||
       result.paperOrdersAllowed!==false||result.sourceRequestsMade!==0||
       result.livePricesAvailable!==false||result.licenseVerified!==false)
      return send(res,503,{status:"FXCM_REVIEW_STATUS_REJECTED",signal:"WAIT",executable:false});
    return send(res,200,result);
  }

  // Read-only metadata about historic XAUUSD candle feasibility and legal prerequisites.
  // Never calls Dukascopy, stores OHLC or opens live trading.
  if (req.url.split("?")[0] === "/api/v3/ultimate/candle-source-readiness") {
    if (req.method !== "GET") return send(res,405,{error:"GET only"});
    try{
      const info=require("./coordinator/candle_source_readiness").inspectCandleSource();
      if(info.signal!=="WAIT"||info.executable!==false||
         info.automaticPollingEnabled!==false||
         info.publicOhlcDistributionEnabled!==false)throw Error("Unsafe source permission gate");
      return send(res,200,info);
    }catch(_err){
      return send(res,503,{signal:"WAIT",executable:false,
        error:"Candle-source permission status unverified or unavailable"});
    }
  }

  // Free independent indicative gold quote — DISPLAY ONLY, never passed to candle/signal engines.
  if (req.url.split("?")[0] === "/api/v3/ultimate/gold-spot-reference") {
    if (req.method !== "GET") return send(res,405,{error:"GET only"});
    try {
      const result=await require("./coordinator/gold_spot_reference").getGoldSpotReference({
        offline:process.env.GOLD_SPOT_REFERENCE_DISABLED==="1"
      });
      if(result.executable!==false||result.signal!=="WAIT"||
         result.readyForUltimateTrading!==false||result.realOHLC!==false||
         Object.values(result.frames).some(x=>x.readyForTrading!==false))
        throw Error("Unsafe spot research contract");
      return send(res,200,result);
    }catch(error){
      return send(res,503,{error:"Spot reference temporarily unavailable",
        signal:"WAIT",executable:false,readyForUltimateTrading:false});
    }
  }

  // Public official context status only; network is disabled by default.
  // This never promotes government headlines or daily yields into a trade vote.
  if (req.url.split("?")[0] === "/api/v3/ultimate/official-context-stage") {
    if (req.method !== "GET") return send(res,405,{error:"GET only"});
    try {
      const stage=await require("./coordinator/official_context_stage").collectOfficialContext({
        offline:process.env.OFFICIAL_CONTEXT_NETWORK_APPROVED!=="1"
      });
      if(stage.signal!=="WAIT"||stage.executable!==false||
         stage.researchEligible!==false||stage.geopoliticalWorldNewsCoverage!==false||
         stage.completeUsdCalendarCoverage!==false||stage.dxyAvailable!==false||
         stage.gcOrderFlowAvailable!==false||
         Object.values(stage.ultimateLayerAdmission||{}).some(Boolean))
        throw Error("Unsafe official partial context contract");
      return send(res,200,stage);
    } catch (error) {
      return send(res,503,{status:"OFFICIAL_CONTEXT_UNAVAILABLE",signal:"WAIT",
        executable:false,researchEligible:false,
        geopoliticalWorldNewsCoverage:false,completeUsdCalendarCoverage:false});
    }
  }

  // Government news/calendar metadata ONLY. No trading signal or market-data subscription.
  if (req.url.split("?")[0] === "/api/v3/ultimate/official-macro") {
    if (req.method !== "GET") return send(res,405,{error:"GET only"});
    try{
      const result=await require("./coordinator/official_macro_review").getOfficialMacroReview({
        offline:process.env.OFFICIAL_MACRO_DISABLED==="1"
      });
      if(result.executable!==false||result.signal!=="WAIT"||result.liveData!==false)
        throw Error("Unsafe macro research contract");
      return send(res,200,result);
    }catch(error){
      return send(res,503,{error:"Official macro reference unavailable",signal:"WAIT",
        executable:false,liveData:false});
    }
  }

  // Public official daily reference, strictly separated from five-minute trading gates.
  // No outbound provider calls, no broker credentials, no trade decisions.
  if (req.url.split("?")[0] === "/api/v3/ultimate/free-context") {
    if (req.method !== "GET") return send(res,405,{error:"GET only"});
    try {
      const data=await require("./coordinator/h15_official_rss").readAutoDailyContext({
        offline:process.env.H15_OFFICIAL_RSS_DISABLED==="1"
      });
      if(data.executable!==false||data.signal!=="WAIT"||
         data.liveData!==false||data.readyForFiveMinuteGate!==false)
        throw Error("Unsafe official context contract");
      return send(res,200,data);
    } catch (error) {
      return send(res,503,{error:"Official daily context unavailable",
        signal:"WAIT",executable:false,readyForFiveMinuteGate:false});
    }
  }

  // Read-only view of existing derived research; never serves raw vendor candles.
  if (req.url.split("?")[0] === "/api/v3/ultimate/recorded-review") {
    if (req.method !== "GET") return send(res, 405, {error:"GET only"});
    try {
      const resultsDir=path.join(__dirname,"research","results");
      const comparison=JSON.parse(fs.readFileSync(path.join(resultsDir,"ultimate-v2-archive-comparison.json"),"utf8"));
      const walkforward=JSON.parse(fs.readFileSync(path.join(resultsDir,"ultimate-walkforward.json"),"utf8"));
      if (comparison.executable!==false || comparison.networkEnabled!==false ||
          walkforward.executable!==false || walkforward.statisticallyValidated!==false ||
          comparison.observedM15Decisions!==4884) throw Error("Unexpected stored report contract");
      const base=walkforward.scenarios.find(s=>s.name==="base");
      if (!base || !Array.isArray(base.windows)) throw Error("Missing historical comparison");
      return send(res,200,{
        mode:"STORED_RECORDED_RESEARCH", signal:"WAIT", executable:false,
        liveData:false, providerRequests:0, trading:"disabled",
        note:"Read-only precomputed historical research, not current prices or independent profit validation.",
        provenance:"Existing September/October 2026 archived BID research; provider authenticity and publication rights not independently verified.",
        countM15:comparison.observedM15Decisions,
        priceReady:comparison.dataCoverage.XAUUSD.readyObservations,
        priceCoveragePct:comparison.dataCoverage.XAUUSD.coveragePct,
        allLayersTogetherPct:comparison.jointCoveragePct,
        missingLayers:["DXY","US02Y","US10Y","GC","orderFlow","calendar","headlines"],
        researchCases:comparison.directionalResearchCases.map(c=>({
          asOfUTC:c.asOfUTC, technicalLabel:c.technicalLabel,
          executable:false, blockers:c.v2Blockers
        })),
        v2Windows:base.windows.filter(w=>["train","validation","test"].includes(w.window)).map(w=>({
          window:w.window,startUTC:w.startUTC,endUTC:w.endUTC,
          trades:w.v2.trades,netPnL:w.v2.netPnL,winRate:w.v2.winRate,
          ultimateTrades:w.ultimate.trades
        })),
        warning:"V2 and Ultimate were studied on prior development archives; neither is validated for live trading."
      });
    }catch(error){return send(res,500,{error:"Stored historical review unavailable"});}
  }

  if (req.url.split("?")[0] === "/api/v3/ultimate") {
    if (req.method !== "POST") return send(res,405,{error:"POST offline evidence JSON required"});
    const chunks=[];let size=0;
    try {
      for await (const chunk of req) {
        size+=chunk.length;
        if(size>1024*1024) return send(res,413,{error:"Evidence exceeds 1 MiB"});
        chunks.push(chunk);
      }
      return send(res,200,require("./coordinator/v3_ultimate").evaluate(JSON.parse(Buffer.concat(chunks).toString("utf8"))));
    } catch(error) { return send(res,400,{error:"Invalid offline evidence: "+error.message}); }
  }
  // Separately versioned Ultimate r2 snapshot review. This endpoint never fetches data.
  if (req.url.split("?")[0] === "/api/v3/ultimate/r2") {
    if (req.method !== "POST") return send(res,405,{error:"POST offline r2 evidence JSON required"});
    const chunks=[];let size=0;
    try {
      for await (const chunk of req) {
        size+=chunk.length;
        if(size>1024*1024) return send(res,413,{error:"Evidence exceeds 1 MiB"});
        chunks.push(chunk);
      }
      const result=require("./coordinator/ultimate_v2").evaluate(JSON.parse(Buffer.concat(chunks).toString("utf8")));
      if(result.version!==2||result.contractVersion!=="ultimate-context-events-v2"||
         result.signal!=="WAIT"||result.executable!==false||result.networkEnabled!==false)
        throw Error("Ultimate r2 safety contract failed");
      return send(res,200,{...result,diagnostics:require("./coordinator/ultimate_diagnostics").diagnostics(JSON.parse(Buffer.concat(chunks).toString("utf8")),result)});
    } catch(error) { return send(res,400,{error:"Invalid offline r2 evidence: "+error.message}); }
  }
  if (req.method === "GET" && req.url.split("?")[0] === "/ultimate") {
    res.writeHead(200,{"Content-Type":"text/html; charset=utf-8","Cache-Control":"no-store"});
    return res.end(fs.readFileSync(path.join(__dirname,"ultimate.html")));
  }

  if (
  req.method !== "GET" &&
  !(req.method === "POST" && req.url.split("?")[0] === "/api/backtest")
) {
  return send(res, 405, { error: "Method not allowed" });
}

  const url = new URL(req.url, "http://localhost");

  if (url.pathname === "/review" || url.pathname === "/review-ui.js" ||
      (DEMO_MODE && url.pathname === "/")) {
    const isScript = url.pathname === "/review-ui.js";
    const file = isScript ? "review-ui.js" : DEMO_MODE && url.pathname === "/" ? "ultimate.html" : "index.html";
    res.writeHead(200, {"Content-Type": isScript ? "application/javascript; charset=utf-8" : "text/html; charset=utf-8", "Cache-Control": "no-store"});
    return res.end(fs.readFileSync(path.join(__dirname, file)));
  }

  if (url.pathname === "/" || url.pathname === "/health") {
    return send(res, 200, {
      system: "Gold Precision Pro AI",
      status: "online",
      serverTimeUTC: new Date().toISOString(),
      mode: DEMO_MODE ? "DEMO_STANDBY" : "REVIEW",
      providerAccess: DEMO_MODE ? false : Boolean(API_KEY),
      trading: "disabled"
    });
  }

  if (url.pathname === "/api/candles") {
    const interval = url.searchParams.get("interval") || "15min";
    const period = url.searchParams.get("period");
const endDate = period === "older" ? "2026-09-30" :
  period === "august" ? "2026-08-31" : null;

    if (!intervals.has(interval)) {
      return send(res, 400, { error: "Invalid interval" });
    }

    if (!API_KEY) {
      return send(res, 503, { error: "API key not configured" });
    }

    const saved = cache.get("history:" + interval + ":" + (endDate || "latest"));
    if (saved && Date.now() - saved.time < 60000 && (endDate || saved.bucket === Math.floor(Date.now()/FRAME_MS[interval]))) {
      return send(res, 200, saved.data);
    }

    try {
      const { response, result } = await requestBrokerCandles(interval, 2000, endDate);

      if (!response.ok || result.status === "error" || !result.values) {
        return send(res, 502, {
          error: "Market data unavailable",
          detail: result.message || "Provider returned no candles"
        });
      }

      const data = {
        symbol: "XAU/USD",
        interval,
        source: "Twelve Data",
        values: result.values.filter(c => {
  const d = new Date(c.datetime.replace(" ", "T") + "Z");
  if (Number.isNaN(d.getTime())) return false;

  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    weekday: "short",
    hour: "2-digit",
    hourCycle: "h23"
  }).formatToParts(d);

  const day = parts.find(p => p.type === "weekday").value;
  const hour = Number(parts.find(p => p.type === "hour").value);

  return day !== "Sat" &&
    !(day === "Sun" && hour < 18) &&
    !(day === "Fri" && hour >= 17) &&
    hour !== 17;
})
      };

      cache.set("history:" + interval + ":" + (endDate || "latest"), { time: Date.now(), data, bucket: Math.floor(Date.now()/FRAME_MS[interval]) });
      return send(res, 200, data);
    } catch (error) {
      return send(res, 502, { error: "Market data request failed" });
    }
  }

  if (url.pathname === "/api/analyze") {
    if (!API_KEY) return send(res, 503, { error: "Data API not configured" });
    const frames = ["15min", "1h", "4h"];
    const candles = {};
    try {
      for (const frame of frames) {
        const saved = cache.get("live:" + frame);
        if (saved && Date.now() - saved.time < 60000 &&
            saved.bucket === Math.floor(Date.now() / FRAME_MS[frame])) {
          candles[frame] = saved.data.values;
          continue;
        }
        const { response, result } = await requestBrokerCandles(frame, 500);
        if (!response.ok || result.status === "error" || !Array.isArray(result.values)) {
          return send(res, 502, { error: "Market data unavailable", interval: frame });
        }
        const data = {
          symbol: "XAU/USD",
          interval: frame,
          source: "Twelve Data",
          values: result.values.filter(c => {
            const d = new Date(c.datetime.replace(" ", "T") + "Z");
            if (Number.isNaN(d.getTime())) return false;
            const parts = new Intl.DateTimeFormat("en-US", {
              timeZone: "America/New_York", weekday: "short", hour: "2-digit", hourCycle: "h23"
            }).formatToParts(d);
            const day = parts.find(p => p.type === "weekday").value;
            const hour = Number(parts.find(p => p.type === "hour").value);
            return day !== "Sat" && !(day === "Sun" && hour < 18) &&
              !(day === "Fri" && hour >= 17) && hour !== 17;
          })
        };
        cache.set("live:" + frame, { time: Date.now(), data, bucket: Math.floor(Date.now() / FRAME_MS[frame]) });
        candles[frame] = data.values;
      }

      const indicators = {};
      let votes = 0;
      for (const frame of frames) {
        const ordered = [...candles[frame]].slice(1).reverse();
        const closes = ordered.map(c => Number(c.close));
        if (closes.length < 50 || closes.some(v => !Number.isFinite(v))) {
          return send(res, 502, {
            error: "Insufficient candles", frame, count: closes.length,
            invalidPrices: closes.filter(v => !Number.isFinite(v)).length
          });
        }
        const ema20 = ema(closes, 20), ema50 = ema(closes, 50), rsi14 = rsi(closes);
        const trend = ema20 > ema50 ? "UP" : ema20 < ema50 ? "DOWN" : "FLAT";
        indicators[frame] = {
          candleTime: ordered[ordered.length - 1].datetime,
          close: closes[closes.length - 1],
          ema20: Number(ema20.toFixed(2)),
          ema50: Number(ema50.toFixed(2)),
          rsi14: Number(rsi14.toFixed(2)),
          trend
        };
        if (trend === "UP" && rsi14 > 50 && rsi14 < 70) votes++;
        if (trend === "DOWN" && rsi14 < 50 && rsi14 > 30) votes--;
      }

      const now = Date.now();
      const limits = { "15min": 30, "1h": 90, "4h": 300 };
      const parts = new Intl.DateTimeFormat("en-US", {
        timeZone: "America/New_York", weekday: "short", hour: "2-digit", hourCycle: "h23"
      }).formatToParts(new Date(now));
      const day = parts.find(p => p.type === "weekday").value;
      const hour = Number(parts.find(p => p.type === "hour").value);
      const marketOpen = day !== "Sat" && !(day === "Sun" && hour < 18) &&
        !(day === "Fri" && hour >= 17) && hour !== 17;
      const dataFresh = marketOpen && frames.every(frame => {
        const latest = candles[frame]?.[0];
        if (!latest?.datetime) return false;
        const age = (now - Date.parse(latest.datetime.replace(" ", "T") + "Z")) / 60000;
        return Number.isFinite(age) && age >= 0 && age <= limits[frame];
      });
      const marketStatus = marketOpen ? "OPEN" : "CLOSED";
      const dataStatus = !marketOpen ? "MARKET_CLOSED" : dataFresh ? "FRESH" : "STALE";
      const signal = !dataFresh ? "WAIT" : votes === 3 ? "BUY" : votes === -3 ? "SELL" : "WAIT";
      const experimentalV2 = analyze(
        Object.fromEntries(frames.map(f => [f, [...candles[f]].slice(1).reverse()])),
        { dataFresh }
      );
      return send(res, 200, {
        symbol: "XAU/USD", marketStatus, dataStatus, signal,
        agreement: Math.abs(votes) + "/3", indicators, experimentalV2,
        warning: "Experimental indicators, not a validated trade signal. No automatic trading."
      });
    } catch (error) {
      return send(res, 502, { error: "Analysis temporarily unavailable" });
    }
  }

  // The V3 research route uses the same shared-broker transport through the coordinator module.
  if (url.pathname === "/api/v3/research") {
    if (DEMO_MODE && url.pathname === "/api/v3/research") {
      return send(res, 200, {
        engine: "V3",
        symbol: "XAU/USD",
        signal: "WAIT",
        executable: false,
        dataStatus: "STANDBY",
        reason: "نسخة عرض تجريبية: مزود البيانات غير موصول ولا تُعرض أسعار افتراضية.",
        observedUTC: new Date().toISOString()
      });
    }
    if (DEMO_MODE) return send(res, 503, {error:"Analysis unavailable in offline demo mode"});
    v2Api.emit("request", req, res);
    return;
  }

if (url.pathname === "/api/backtest") {
  if (req.method !== "POST") {
    return send(res, 405, {
      error: "POST required"
    });
  }

  let body = "";
  req.on("data", chunk => {
    body += chunk;
    if (body.length > 1000000) req.destroy();
  });

  req.on("end", () => {
    try {
      const input = JSON.parse(body);
      const result = backtest(input.candles, input.signals, input.options || {});
      return send(res, 200, result);
    } catch (error) {
      return send(res, 400, {
        error: "Invalid backtest input"
      });
    }
  });
  return;
}

  
  return send(res, 404, { error: "Not found" });
});

server.listen(PORT, "0.0.0.0");
