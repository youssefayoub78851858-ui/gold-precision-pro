"use strict";

const { backtestFrames } = require("./backtest");
const { analyze } = require("./strategy");
const { plan: v3Plan } = require("../v3_trade_plan");
const { checkFrame: checkV3Frame } = require("../v3_multitimeframe");
const http = require("http");

const PORT = process.env.PORT || 3000;
const BROKER_CONFIGURED = Boolean(process.env.MARKET_DATA_BROKER_URL &&
  process.env.BROKER_TOKEN && process.env.BROKER_TOKEN.length >= 32);
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
  if (!BROKER_CONFIGURED) throw new Error("Shared data broker not configured");
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
  if (result.meta?.interval && result.meta.interval !== frame) throw new Error("Wrong broker timeframe");
  if (result.symbol && result.symbol !== "XAU/USD") throw new Error("Wrong broker symbol");
  let previous = Infinity;
  for (const c of result.values) {
    const t = timestamp(c.datetime);
    const [o,h,l,v] = [c.open,c.high,c.low,c.close].map(Number);
    if (!Number.isFinite(t) || t >= previous || t > Date.now() ||
        ![o,h,l,v].every(x => Number.isFinite(x) && x > 0) ||
        l > Math.min(o,v) || h < Math.max(o,v)) throw new Error("Invalid broker OHLC/time/order");
    previous = t;
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
      serverTimeUTC: new Date().toISOString(), apiKeyConfigured: BROKER_CONFIGURED,
      signalEngine: "Gold Precision Pro V2", trading: "disabled"
    });
  }

  if (url.pathname === "/api/candles") {
    const interval = url.searchParams.get("interval") || "15min";
    const period = url.searchParams.get("period");
    const endDate = period === "older" ? "2026-09-30" : period === "august" ? "2026-08-31" : null;
    if (!intervals.has(interval)) return send(res, 400, { error: "Invalid interval" });
    if (!BROKER_CONFIGURED) return send(res, 503, { error: "API key not configured" });
    const cacheKey = "history:" + interval + ":" + (endDate || "latest");
    const saved = cache.get(cacheKey);
    if (saved && Date.now() - saved.time < 60000 && (endDate || saved.bucket === Math.floor(Date.now() / (FRAME_MINUTES[interval] * 60000)))) return send(res, 200, saved.data);
    try {
      const values = await fetchCandles(interval, "2000", endDate);
      const data = { symbol: "XAU/USD", interval, source: "Twelve Data", values };
      cache.set(cacheKey, { time: Date.now(), data, bucket: Math.floor(Date.now() / (FRAME_MINUTES[interval] * 60000)) });
      return send(res, 200, data);
    } catch (error) {
      return send(res, 502, { error: "Market data unavailable", detail: error.message });
    }
  }

  if (url.pathname === "/api/analyze") {
    if (!BROKER_CONFIGURED) return send(res, 503, { error: "Data API not configured" });
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
    // Transport/data admission only; V3 planning rules remain unchanged.
    const now = Date.now();
    const base = {engine:"V3", symbol:"XAU/USD", signal:"WAIT", executable:false,
      observedUTC:new Date(now).toISOString()};
    if (!marketIsOpen()) return send(res, 200, {...base,
      reason:"Market closed", dataStatus:"MARKET_CLOSED"});
    const closed = {}, candles = {};
    try {
      for (const [interval, minutes] of Object.entries(FRAME_MINUTES)) {
        const saved = cache.get("live:" + interval);
        let values;
        if (saved && now - saved.time < 60000 &&
            saved.bucket === Math.floor(now / (minutes * 60000))) values = saved.values;
        else {
          values = await fetchCandles(interval);
          cache.set("live:" + interval, {time:now, values,
            bucket:Math.floor(now / (minutes * 60000))});
        }
        if (values.some(c => !Number.isFinite(timestamp(c.datetime)) || timestamp(c.datetime) > now))
          throw new Error("Invalid broker timestamps");
        // Keep native order: reversed newest-first bars must be strictly ascending.
        closed[interval] = values.filter(c => timestamp(c.datetime) + minutes * 60000 <= now).slice().reverse();
        const latest = closed[interval].at(-1);
        candles[interval] = latest ? {
          openUTC:new Date(timestamp(latest.datetime)).toISOString(),
          closeUTC:new Date(timestamp(latest.datetime) + minutes * 60000).toISOString(),
          close:Number(latest.close),
          ageAfterCloseSeconds:(now - timestamp(latest.datetime) - minutes * 60000)/1000
        } : null;
      }
      const timing = require('../timing').admit(closed, now, {marketOpen:true});
      if (!timing.accepted) return send(res, 200, {...base, candles,
        dataStatus:"STALE", reason:timing.reason, blockedFrame:timing.frame || null});
      const frames = Object.fromEntries(Object.entries(timing.frames).map(([interval, values]) => [
        interval === "15min" ? "M15" : interval === "1h" ? "H1" : "H4",
        values.map(c => ({datetime:new Date(timestamp(c.datetime)).toISOString(),
          open:Number(c.open), high:Number(c.high), low:Number(c.low), close:Number(c.close)}))
      ]));
      for (const [name, minutes] of Object.entries({M15:15,H1:60,H4:240})) {
        const validity = checkV3Frame(frames[name], minutes, now);
        if (!validity.ok) return send(res, 200, {...base, candles,
          dataStatus:"INVALID", reason:name + ": " + validity.reason});
      }
      const result = v3Plan(frames, new Date(now).toISOString(), {spread:NaN});
      return send(res, 200, {...base, ...result, candles, dataStatus:"FRESH",
        signal:"WAIT", executable:false,
        warning:"Research only. Broker spread, news, costs and position sizing unverified."});
    } catch (error) {
      return send(res, 503, {...base, dataStatus:"UNAVAILABLE",
        reason:"Broker unavailable or invalid candles; no verified analysis"});
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
