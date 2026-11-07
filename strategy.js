
"use strict";

// Gold Precision Pro Ultimate - research signal engine v1.
// Inputs: CLOSED candles, oldest first. Research only.
function ema(values, period) {
  if (values.length < period) return null;
  let value = values.slice(0, period).reduce((a, b) => a + b, 0) / period;
  const alpha = 2 / (period + 1);
  for (let i = period; i < values.length; i++) value = alpha * values[i] + (1 - alpha) * value;
  return value;
}

function rsi(values, period = 14) {
  if (values.length <= period) return null;
  let gain = 0, loss = 0;
  for (let i = 1; i <= period; i++) {
    const delta = values[i] - values[i - 1];
    gain += Math.max(0, delta);
    loss += Math.max(0, -delta);
  }
  gain /= period;
  loss /= period;
  for (let i = period + 1; i < values.length; i++) {
    const delta = values[i] - values[i - 1];
    gain = (gain * (period - 1) + Math.max(0, delta)) / period;
    loss = (loss * (period - 1) + Math.max(0, -delta)) / period;
  }
  return loss === 0 ? (gain === 0 ? 50 : 100) : 100 - 100 / (1 + gain / loss);
}

function atr(candles, period = 14) {
  if (candles.length < period + 1) return null;
  let sum = 0;
  for (let i = candles.length - period; i < candles.length; i++) {
    const current = candles[i];
    const previousClose = candles[i - 1].close;
    sum += Math.max(current.high - current.low,
      Math.abs(current.high - previousClose),
      Math.abs(current.low - previousClose));
  }
  return sum / period;
}

function parseCandles(input) {
  if (!Array.isArray(input) || input.length < 60) return null;
  const candles = input.map(c => ({
    open: Number(c.open), high: Number(c.high),
    low: Number(c.low), close: Number(c.close), datetime: c.datetime
  }));
  if (candles.some(c => ![c.open, c.high, c.low, c.close].every(Number.isFinite) ||
      c.low > c.high || c.open < c.low || c.open > c.high ||
      c.close < c.low || c.close > c.high)) return null;
  return candles;
}

function analyze(frames, options = {}) {
  const wait = reason => ({ signal: "WAIT", reason, executable: false });
  if (!frames || typeof frames !== "object") return wait("Missing candles");
  if (options.newsRisk === true) return wait("High-impact news risk");
  if (options.dataFresh !== true) return wait("Freshness not verified");
  const analysis = {};
  for (const frame of ["15min", "1h", "4h"]) {
    const candles = parseCandles(frames[frame]);
    if (!candles) return wait("Invalid or insufficient " + frame + " candles");
    const closes = candles.map(c => c.close);
    const fast = ema(closes, 20), slow = ema(closes, 50);
    const momentum = rsi(closes), volatility = atr(candles);
    if (![fast, slow, momentum, volatility].every(Number.isFinite) || volatility <= 0)
      return wait("Invalid indicators for " + frame);
    const direction = fast > slow && momentum > 50 && momentum < 70 ? "BUY" :
      fast < slow && momentum < 50 && momentum > 30 ? "SELL" : "WAIT";
    analysis[frame] = { direction, ema20: fast, ema50: slow,
      rsi14: momentum, atr14: volatility, close: closes[closes.length - 1] };
  }
  const sides = [analysis["4h"].direction, analysis["1h"].direction,
    analysis["15min"].direction];
  if (sides.includes("WAIT") || new Set(sides).size !== 1)
    return { ...wait("Timeframes disagree"), analysis };
  const signal = sides[0];
  const entryReference = analysis["15min"].close;
  const distance = 1.5 * analysis["15min"].atr14;
  const sign = signal === "BUY" ? 1 : -1;
  return {
    signal, executable: false,
    entryReference, stopReference: entryReference - sign * distance,
    target1Reference: entryReference + sign * distance,
    target2Reference: entryReference + sign * 2 * distance,
    analysis,
    warning: "Indicative levels only. Confirm live broker price, spread and news before any trade."
  };
}

module.exports = { analyze, ema, rsi, atr };
