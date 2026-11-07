"use strict";

// Gold Precision Pro - Audited historical backtest.
// Candles: oldest first. Research only, no live orders.
function backtest(candles, signals, options = {}) {
  const rr = options.rr ?? 2;
  const spread = options.spread ?? 0.40;
  const risk = options.risk ?? 1;

  if (!Array.isArray(candles) || !Array.isArray(signals)) {
    throw new Error("Candles and signals must be arrays");
  }
  if (!(Number.isFinite(rr) && rr > 0 &&
        Number.isFinite(spread) && spread >= 0 &&
        Number.isFinite(risk) && risk > 0)) {
    throw new Error("Invalid test settings");
  }

  const orderedSignals = [...signals]
    .filter(s => s && Number.isInteger(s.index))
    .sort((a, b) => a.index - b.index);
  const trades = [];
  let lastExitIndex = -1;
  let openAtEnd = 0;

  for (const s of orderedSignals) {
    if (s.index < lastExitIndex) continue;
    if (s.side !== "BUY" && s.side !== "SELL") continue;
    if (s.index < 0 || s.index >= candles.length - 1) continue;

    const entryIndex = s.index + 1;
    const entry = Number(candles[entryIndex].open);
    const stop = Number(s.stop);
    const distance = Math.abs(entry - stop);

    if (!Number.isFinite(entry) ||
        !Number.isFinite(stop) || !(distance > 0)) continue;
    if (s.side === "BUY" && stop >= entry) continue;
    if (s.side === "SELL" && stop <= entry) continue;

    const target = s.side === "BUY"
      ? entry + distance * rr : entry - distance * rr;

    let closed = false;
    for (let i = entryIndex; i < candles.length; i++) {
      const bar = candles[i];
      const open = Number(bar.open);
      const high = Number(bar.high);
      const low = Number(bar.low);

      if (![open, high, low].every(Number.isFinite) ||
          low > high || open < low || open > high) {
        throw new Error("Invalid OHLC candle at index " + i);
      }

      let exitPrice = null;
      let result = null;

      if (i > entryIndex && s.side === "BUY" && open <= stop) {
        exitPrice = open;
        result = "LOSS";
      } else if (i > entryIndex && s.side === "SELL" && open >= stop) {
        exitPrice = open;
        result = "LOSS";
      } else if (i > entryIndex && s.side === "BUY" && open >= target) {
        exitPrice = target;
        result = "WIN";
      } else if (i > entryIndex && s.side === "SELL" && open <= target) {
        exitPrice = target;
        result = "WIN";
      } else {
        const hitSL = s.side === "BUY" ? low <= stop : high >= stop;
        const hitTP = s.side === "BUY" ? high >= target : low <= target;

        if (hitSL) {
          exitPrice = stop;
          result = "LOSS";
        } else if (hitTP) {
          exitPrice = target;
          result = "WIN";
        }
      }

      if (result !== null) {
        const grossR = (s.side === "BUY"
          ? exitPrice - entry : entry - exitPrice) / distance;
        const netR = grossR - spread / distance;
        trades.push({
          result, netR, grossR,
          entry, stop, target, exitPrice,
          signalIndex: s.index,
          entryIndex, exitIndex: i
        });
        lastExitIndex = i;
        closed = true;
        break;
      }
    }

    if (!closed) {
      openAtEnd = 1;
      break;
    }
  }

  const count = trades.length;
  const wins = trades.filter(t => t.result === "WIN").length;
  const losses = count - wins;
  const totalR = trades.reduce((sum, t) => sum + t.netR, 0);
  const profit = trades.reduce((sum, t) =>
    sum + Math.max(t.netR, 0), 0);
  const loss = trades.reduce((sum, t) =>
    sum + Math.max(-t.netR, 0), 0);

  return {
    trades: count,
    wins,
    losses,
    netProfitableTrades: trades.filter(t => t.netR > 0).length,
    winRate: count ? +(wins / count * 100).toFixed(2) : 0,
    profitFactor: loss ? +(profit / loss).toFixed(2) : null,
    totalR: +totalR.toFixed(2),
    estimatedPnL: +(totalR * risk).toFixed(2),
    estimatedPnLIsHypothetical: true,
    tradesDetail: trades,
    openAtEnd,
    auditNotes: [
      "No overlapping positions.",
      "Adverse price gaps across stop loss are filled at candle open.",
      "Fixed spread is approximate; commissions and slippage are not modeled.",
      "Backtest results do not guarantee real trading profitability."
    ]
  };
}

module.exports = { backtest };
