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

  if (
  req.method !== "GET" &&
  !(req.method === "POST" && req.url.split("?")[0] === "/api/backtest")
) {
  return send(res, 405, { error: "Method not allowed" });
}

  const url = new URL(req.url, "http://localhost");

  if (url.pathname === "/review" || url.pathname === "/review-ui.js" ||
      (DEMO_MODE && url.pathname === "/")) {
    const html = url.pathname !== "/review-ui.js";
    res.writeHead(200, {"Content-Type": html ? "text/html; charset=utf-8" : "application/javascript; charset=utf-8", "Cache-Control": "no-store"});
    return res.end(fs.readFileSync(path.join(__dirname, html ? "index.html" : "review-ui.js")));
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
