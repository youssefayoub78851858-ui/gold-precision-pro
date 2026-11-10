const { backtest } = require("./backtest");
const { analyze } = require("./strategy");
const http = require("http");
const fs = require("fs");
const path = require("path");
const PORT = process.env.PORT || 3000;
const DEMO_MODE = process.env.DEMO_MODE === "standby";
const v2Api = DEMO_MODE ? null : require("./coordinator/service/server");
const API_KEY = Boolean(process.env.MARKET_DATA_BROKER_URL);
if (!DEMO_MODE && (!API_KEY || !process.env.BROKER_TOKEN || process.env.BROKER_TOKEN.length < 32)) throw new Error("Shared data broker and strong token required");
const FRAME_MS = {"15min":900000,"1h":3600000,"4h":14400000};

const cache = new Map();
const intervals = new Set(["15min", "1h", "4h"]);

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
      const endpoint = new URL("/time_series", process.env.MARKET_DATA_BROKER_URL);
      endpoint.searchParams.set("symbol", "XAU/USD");
      endpoint.searchParams.set("interval", interval);
      endpoint.searchParams.set("outputsize", "2000");
      endpoint.searchParams.set("timezone", "UTC");
      if (endDate) endpoint.searchParams.set("end_date", endDate);

      const response = await fetch(endpoint, {
        signal: AbortSignal.timeout(12000),
        headers: { Authorization: "Bearer " + process.env.BROKER_TOKEN }
      });

      const result = await response.json();

      if (!response.ok || result.status === "error" || !result.values) {
        return send(res, 502, {
          error: "Market data unavailable",
          detail: result.message || "Provider returned no candles",
          retryAtMS: result.retryAtMS ?? null
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

  // Reuse the frozen V2 API and the already validated timing policy.
  if (url.pathname === "/api/analyze" || url.pathname === "/api/v3/research") {
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
