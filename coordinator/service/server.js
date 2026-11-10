"use strict";

const { backtestFrames } = require("./backtest");
const { analyze } = require("./strategy");
const { plan: v3Plan } = require("../v3_trade_plan");
const http = require("http");

const PORT = process.env.PORT || 3000;
const API_KEY = Boolean(process.env.MARKET_DATA_BROKER_URL);
if (!API_KEY || !process.env.BROKER_TOKEN || process.env.BROKER_TOKEN.length < 32) throw new Error("Shared market-data broker URL and strong token required");
const cache = new Map();
const intervals = new Set(["15min", "1h", "4h"]);
const FRAME_MINUTES = { "15min": 15, "1h": 60, "4h": 240 };
const MAX_BACKTEST_BYTES = 5_000_000;

function send(res, status, data) {
  res.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Access-Control-Allow-Origin": "https://youssefayoub78851858-ui.github.io",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type"
  });
  res.end(JSON.stringify(data));
}

function timestamp(datetime) {
  if (typeof datetime !== "string") return NaN;
  return Date.parse(datetime.includes("T") ? datetime : datetime.replace(" ", "T") + "Z");
}

function marketIsOpen(date = new Date()) {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York", weekday: "short", hour: "2-digit", hourCycle: "h23"
  }).formatToParts(date);
  const day = parts.find(part => part.type === "weekday").value;
  const hour = Number(parts.find(part => part.type === "hour").value);
  return day !== "Sat" && !(day === "Sun" && hour < 18) &&
    !(day === "Fri" && hour >= 17) && hour !== 17;
}

function removeClosedMarketCandles(values) {
  return values.filter(candle => {
    const time = timestamp(candle.datetime);
    if (!Number.isFinite(time)) return false;
    const parts = new Intl.DateTimeFormat("en-US", {
      timeZone: "America/New_York", weekday: "short", hour: "2-digit", hourCycle: "h23"
    }).formatToParts(new Date(time));
    const day = parts.find(part => part.type === "weekday").value;
    const hour = Number(parts.find(part => part.type === "hour").value);
    return day !== "Sat" && !(day === "Sun" && hour < 18) &&
      !(day === "Fri" && hour >= 17) && hour !== 17;
  });
}

async function fetchCandles(frame, outputsize = "500", endDate = null) {
  const endpoint = new URL("/time_series", process.env.MARKET_DATA_BROKER_URL);
  endpoint.searchParams.set("symbol", "XAU/USD");
  endpoint.searchParams.set("interval", frame);
  endpoint.searchParams.set("outputsize", outputsize);
  endpoint.searchParams.set("timezone", "UTC");
  if (endDate) endpoint.searchParams.set("end_date", endDate);
  const response = await fetch(endpoint, { signal: AbortSignal.timeout(12000), headers: { Authorization: "Bearer " + process.env.BROKER_TOKEN } });
  const result = await response.json();
  if (!response.ok || result.status === "error" || !Array.isArray(result.values)) {
    const failure = new Error(result.message || "Market data unavailable");
    failure.retryAtMS = result.retryAtMS;
    throw failure;
  }
  return removeClosedMarketCandles(result.values);
}

const server = http.createServer(async (req, res) => {
  if (req.method === "OPTIONS") return send(res, 200, {});
  const url = new URL(req.url, "http://localhost");
  const isBacktestPost = req.method === "POST" && url.pathname === "/api/backtest";
  if (req.method !== "GET" && !isBacktestPost) return send(res, 405, { error: "Method not allowed" });

  if (url.pathname === "/" || url.pathname === "/health") {
    return send(res, 200, {
      system: "Gold Precision Pro AI", status: "online",
      serverTimeUTC: new Date().toISOString(), apiKeyConfigured: Boolean(API_KEY),
      signalEngine: "Gold Precision Pro V2", trading: "disabled"
    });
  }

  if (url.pathname === "/api/candles") {
    const interval = url.searchParams.get("interval") || "15min";
    const period = url.searchParams.get("period");
    const endDate = period === "older" ? "2026-09-30" : period === "august" ? "2026-08-31" : null;
    if (!intervals.has(interval)) return send(res, 400, { error: "Invalid interval" });
    if (!API_KEY) return send(res, 503, { error: "API key not configured" });
    const cacheKey = "history:" + interval + ":" + (endDate || "latest");
    const saved = cache.get(cacheKey);
    if (saved && Date.now() - saved.time < 60000 && (endDate || saved.bucket === Math.floor(Date.now() / (FRAME_MINUTES[interval] * 60000)))) return send(res, 200, saved.data);
    try {
      const values = await fetchCandles(interval, "2000", endDate);
      const data = { symbol: "XAU/USD", interval, source: "Twelve Data", values };
      cache.set(cacheKey, { time: Date.now(), data, bucket: Math.floor(Date.now() / (FRAME_MINUTES[interval] * 60000)) });
      return send(res, 200, data);
    } catch (error) {
      return send(res, 502, { error: "Market data unavailable", detail: error.message, retryAtMS: error.retryAtMS || null });
    }
  }

  if (url.pathname === "/api/analyze") {
    if (!API_KEY) return send(res, 503, { error: "Data API not configured" });
    const frames = Object.keys(FRAME_MINUTES);
    const raw = {};
    try {
      for (const frame of frames) {
        const saved = cache.get("live:" + frame);
        if (saved && Date.now() - saved.time < 60000 && saved.bucket === Math.floor(Date.now() / (FRAME_MINUTES[frame] * 60000))) raw[frame] = saved.values;
        else {
          const values = await fetchCandles(frame);
          cache.set("live:" + frame, { time: Date.now(), values, bucket: Math.floor(Date.now() / (FRAME_MINUTES[frame] * 60000)) });
          raw[frame] = values;
        }
      }

      const now = Date.now();
      const closed = {};
      for (const frame of frames) {
        closed[frame] = raw[frame]
          .filter(candle => timestamp(candle.datetime) + FRAME_MINUTES[frame] * 60000 <= now)
          .slice().reverse();
      }
      const timing = require('../timing').admit(closed, now, {marketOpen:marketIsOpen()});
      const fresh = timing.accepted;
      const decision = analyze(fresh ? timing.frames : closed, { dataFresh: fresh });
      const indicators = decision.analysis || {};
      return send(res, 200, {
        symbol: "XAU/USD",
        marketStatus: marketIsOpen() ? "OPEN" : "CLOSED",
        dataStatus: !marketIsOpen() ? "MARKET_CLOSED" : fresh ? "FRESH" : "STALE",
        signal: decision.signal,
        agreement: frames.filter(frame => indicators[frame]?.direction === decision.signal).length + "/3",
        indicators,
        analysis: decision,
        engine: "Gold Precision Pro V2",
        warning: "Research signal only. No automatic trading."
      });
    } catch (error) {
      return send(res, 502, { error: "Analysis temporarily unavailable" });
    }
  }

  if (url.pathname === "/api/v3/research") {
    // Research only. Reuses the existing broker, with no direct provider access.
    // Fail closed if any timeframe is missing, stale, or not fully closed.
    if (!marketIsOpen()) return send(res, 200, {
      engine: "V3", signal: "WAIT", executable: false,
      reason: "Market closed", dataStatus: "MARKET_CLOSED"
    });
    const now = Date.now();
    const frames = {};
    try {
      for (const [interval, minutes] of Object.entries(FRAME_MINUTES)) {
        const key = "live:" + interval;
        const saved = cache.get(key);
        let values;
        if (saved && now - saved.time < 60000 &&
            saved.bucket === Math.floor(now / (minutes * 60000))) {
          values = saved.values;
        } else {
          values = await fetchCandles(interval);
          cache.set(key, {time: now, values,
            bucket: Math.floor(now / (minutes * 60000))});
        }
        const name = interval === "15min" ? "M15" : interval === "1h" ? "H1" : "H4";
        frames[name] = values
          .filter(c => Number.isFinite(timestamp(c.datetime)))
          .map(c => ({datetime: new Date(timestamp(c.datetime)).toISOString(),
            open: Number(c.open), high: Number(c.high),
            low: Number(c.low), close: Number(c.close)}))
          .filter(c =>
            Date.parse(c.datetime) + minutes * 60000 <= now)
          .sort((a,b) => Date.parse(a.datetime)-Date.parse(b.datetime));
      }
      const result = v3Plan(frames, new Date(now).toISOString(), {
        spread: NaN
      });
      return send(res, 200, {
        engine: "V3", symbol: "XAU/USD", dataStatus: "BROKER_RESEARCH",
        ...result, signal: "WAIT", executable: false,
        warning: "Research only. No broker spread, news gate, or live trading."
      });
    } catch (error) {
      return send(res, 503, {engine:"V3", signal:"WAIT",
        executable:false, dataStatus:"UNAVAILABLE",
        error:"V3 research data unavailable"});
    }
  }

  if (url.pathname === "/api/backtest") {
    let body = "";
    let oversized = false;
    req.on("data", chunk => {
      if (oversized) return;
      body += chunk;
      if (Buffer.byteLength(body) > MAX_BACKTEST_BYTES) {
        oversized = true;
        body = "";
      }
    });
    req.on("end", () => {
      if (oversized) return send(res, 413, { error: "Backtest input exceeds size limit" });
      try {
        const input = JSON.parse(body);
        const result = backtestFrames(input.frames, input.options || {});
        return send(res, 200, result);
      } catch (error) {
        return send(res, 400, { error: "Invalid backtest input", detail: error.message, retryAtMS: error.retryAtMS || null });
      }
    });
    return;
  }

  return send(res, 404, { error: "Not found" });
});

module.exports = server;
if (require.main === module) server.listen(PORT, "127.0.0.1");
