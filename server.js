const { backtest } = require("./backtest");
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

  if (url.pathname === "/api/analyze") {
    if (!API_KEY) {
      return send(res, 503, { error: "Data API not configured" });
    }

    const frames = ["15min", "1h", "4h"];
    const candles = {};

    try {
      for (const frame of frames) {
        const saved = cache.get(frame);
        if (saved && Date.now() - saved.time < 60000) {
          candles[frame] = saved.data.values;
          continue;
        }

        const endpoint = new URL("https://api.twelvedata.com/time_series");
        endpoint.searchParams.set("symbol", "XAU/USD");
        endpoint.searchParams.set("interval", frame);
        endpoint.searchParams.set("outputsize", "100");
        endpoint.searchParams.set("timezone", "UTC");
        endpoint.searchParams.set("apikey", API_KEY);

        const response = await fetch(endpoint, {
          signal: AbortSignal.timeout(12000)
        });
        const result = await response.json();

        if (!response.ok || result.status === "error" ||
            !Array.isArray(result.values)) {
          return send(res, 502, {
            error: "Market data unavailable",
            interval: frame
          });
        }

        const data = {
          symbol: "XAU/USD",
          interval: frame,
          source: "Twelve Data",
          values: result.values
        };
        cache.set(frame, { time: Date.now(), data });
        candles[frame] = result.values;
      }

      function ema(values, period) {
        if (values.length < period) return null;
        let average = values.slice(0, period)
          .reduce((a, b) => a + b, 0) / period;
        const k = 2 / (period + 1);
        for (let i = period; i < values.length; i++) {
          average = values[i] * k + average * (1 - k);
        }
        return average;
      }

      function rsi(values, period = 14) {
        if (values.length <= period) return null;
        let gain = 0, loss = 0;
        for (let i = 1; i <= period; i++) {
          const diff = values[i] - values[i - 1];
          gain += Math.max(diff, 0);
          loss += Math.max(-diff, 0);
        }
        gain /= period;
        loss /= period;

        for (let i = period + 1; i < values.length; i++) {
          const diff = values[i] - values[i - 1];
          gain = (gain * (period - 1) + Math.max(diff, 0)) / period;
          loss = (loss * (period - 1) + Math.max(-diff, 0)) / period;
        }
        if (loss === 0) return gain === 0 ? 50 : 100;
        return 100 - 100 / (1 + gain / loss);
      }

      const indicators = {};
      let votes = 0;

      for (const frame of frames) {
        const ordered = [...candles[frame]].slice(1).reverse();
        const closes = ordered.map(c => Number(c.close));
        if (closes.length < 50 || closes.some(v => !Number.isFinite(v))) {
        return send(res, 502, { error: "Insufficient candles", frame, count: closes.length, invalidPrices: closes.filter(v => !Number.isFinite(v)).length });
        }

        const fast = ema(closes, 20);
        const slow = ema(closes, 50);
        const momentum = rsi(closes);
        const trend = fast > slow ? "UP" : fast < slow ? "DOWN" : "FLAT";

        indicators[frame] = {
          candleTime: ordered[ordered.length - 1].datetime,
          close: closes[closes.length - 1],
          ema20: Number(fast.toFixed(2)),
          ema50: Number(slow.toFixed(2)),
          rsi14: Number(momentum.toFixed(2)),
          trend
        };

        if (trend === "UP" && momentum > 50 && momentum < 70) votes++;
        if (trend === "DOWN" && momentum < 50 && momentum > 30) votes--;
      }

      const signal = votes === 3 ? "BUY" :
                     votes === -3 ? "SELL" : "WAIT";

      return send(res, 200, {
        symbol: "XAU/USD",
        signal,
        agreement: Math.abs(votes) + "/3",
        indicators,
        warning: "Experimental indicators, not a validated trade signal. No automatic trading."
      });

    } catch (error) {
      return send(res, 502, { error: "Analysis temporarily unavailable" });
    }
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
      const result = backtest(input);
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
