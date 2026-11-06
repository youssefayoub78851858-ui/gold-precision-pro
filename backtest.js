
"use strict";

// Gold Precision Pro - Historical Backtest
// Input: oldest candle first.
// No live trading or orders.

function backtest(candles, signals, options = {}) {
  const rr = options.rr ?? 2;
  const spread = options.spread ?? 0.40;
  const risk = options.risk ?? 1;

  if (!Array.isArray(candles) || !Array.isArray(signals)) {
    throw new Error("Candles and signals must be arrays");
  }
  if (!(rr > 0 && spread >= 0 && risk > 0)) {
    throw new Error("Invalid test settings");
  }

  let wins = 0, losses = 0, totalR = 0; let lastExitIndex = -1;
  const trades = [];

  for (const s of signals) { if (s.index < lastExitIndex) continue;
    if (!["BUY", "SELL"].includes(s.side)) continue;
    if (!Number.isInteger(s.index) ||
        s.index < 0 || s.index >= candles.length - 1) continue;

    const entry = Number(candles[s.index + 1].open);
    const stop = Number(s.stop);
    const distance = Math.abs(entry - stop);

    if (!Number.isFinite(entry) ||
        !Number.isFinite(stop) || distance <= 0) continue;
    if (s.side === "BUY" && stop >= entry) continue;
    if (s.side === "SELL" && stop <= entry) continue;

    const target = s.side === "BUY"
      ? entry + distance * rr
      : entry - distance * rr;

    for (let i = s.index + 1; i < candles.length; i++) {
      const high = Number(candles[i].high);
      const low = Number(candles[i].low);
      if (!Number.isFinite(high) || !Number.isFinite(low)) break;

      const hitSL = s.side === "BUY" ? low <= stop : high >= stop;
      const hitTP = s.side === "BUY" ? high >= target : low <= target;

      if (hitSL || hitTP) {
        // Conservative: stop wins when both touched in one candle.
        const result = hitSL ? "LOSS" : "WIN";
        const netR = (hitSL ? -1 : rr) - spread / distance;
        if (result === "WIN") wins++;
        else losses++;
        totalR += netR;
        trades.push({ result, netR, entry, stop, target, exitIndex: i });
        lastExitIndex = i; break;
      }
    }
  }

  const count = trades.length;
  return {
    trades: count,
    wins,
    losses,
    winRate: count ? +(wins / count * 100).toFixed(2) : 0,
    profitFactor: (() => {
      const profit = trades.reduce((a, t) => a + Math.max(t.netR, 0), 0);
      const loss = trades.reduce((a, t) => a + Math.max(-t.netR, 0), 0);
      return loss ? +(profit / loss).toFixed(2) : null;
    })(),
    totalR: +totalR.toFixed(2),
    estimatedPnL: +(totalR * risk).toFixed(2),
    tradesDetail: trades
  };
}

module.exports = { backtest };
                                 
