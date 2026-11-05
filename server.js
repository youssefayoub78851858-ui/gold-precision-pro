
const http = require("http");

const PORT = process.env.PORT || 3000;
const API_KEY = process.env.TWELVE_DATA_API_KEY;

const cache = new Map();
const intervals = new Set(["15min", "1h", "4h"]);

function send(res, status, data) {
  res.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Access-Control-Allow-Origin":
      "https://youssefayoub78851858-ui.github.io",
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type"
  });
  res.end(JSON.stringify(data));
}

const server = http.createServer(async (req, res) => {
  if (req.method === "OPTIONS") {
    return send(res, 200, {});
  }

  if (req.method !== "GET") {
    return send(res, 405, { error: "Method not allowed" });
  }

  const url = new URL(req.url, "http://localhost");

  if (url.pathname === "/" || url.pathname === "/health") {
    return send(res, 200, {
      system: "Gold Precision Pro AI",
      status: "online",
      apiKeyConfigured: Boolean(API_KEY),
      trading: "disabled"
    });
  }

  if (url.pathname === "/api/candles") {
    const interval = url.searchParams.get("interval") || "15min";

    if (!intervals.has(interval)) {
      return send(res, 400, { error: "Invalid interval" });
    }

    if (!API_KEY) {
      return send(res, 503, { error: "API key not configured" });
    }

    const saved = cache.get(interval);
    if (saved && Date.now() - saved.time < 60000) {
      return send(res, 200, saved.data);
    }

    try {
      const endpoint = new URL("https://api.twelvedata.com/time_series");
      endpoint.searchParams.set("symbol", "XAU/USD");
      endpoint.searchParams.set("interval", interval);
      endpoint.searchParams.set("outputsize", "30");
      endpoint.searchParams.set("apikey", API_KEY);

      const response = await fetch(endpoint, {
        signal: AbortSignal.timeout(12000)
      });

      const result = await response.json();

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
        values: result.values
      };

      cache.set(interval, { time: Date.now(), data });
      return send(res, 200, data);
    } catch (error) {
      return send(res, 502, { error: "Market data request failed" });
    }
  }

  return send(res, 404, { error: "Not found" });
});

server.listen(PORT, "0.0.0.0");
