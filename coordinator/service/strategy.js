"use strict";

// Gold Precision Pro V2 signal engine. Inputs are CLOSED candles, oldest first.
// This module is shared by live analysis and historical signal generation.
const FRAME_MINUTES = { "15min": 15, "1h": 60, "4h": 240 };

function ema(values, period) {
  if (!Array.isArray(values) || values.length < period) return null;
  let value = values.slice(0, period).reduce((a, b) => a + b, 0) / period;
  const alpha = 2 / (period + 1);
  for (let i = period; i < values.length; i++) {
    value = alpha * values[i] + (1 - alpha) * value;
  }
  return value;
}

function rsi(values, period = 14) {
  if (!Array.isArray(values) || values.length <= period) return null;
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
  if (!Array.isArray(candles) || candles.length < period + 1) return null;
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

function parseCandles(input, minimum = 60) {
  if (!Array.isArray(input) || input.length < minimum) return null;
  const candles = input.map(c => ({
    open: Number(c.open), high: Number(c.high), low: Number(c.low),
    close: Number(c.close), datetime: c.datetime
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
  if (options.dataFresh !== true && options.historical !== true)
    return wait("Freshness not verified");

  const analysis = {};
  for (const frame of Object.keys(FRAME_MINUTES)) {
    const candles = parseCandles(frames[frame]);
    if (!candles) return wait("Invalid or insufficient " + frame + " candles");
    const closes = candles.map(c => c.close);
    const fast = ema(closes, 20), slow = ema(closes, 50);
    const momentum = rsi(closes), volatility = atr(candles);
    if (![fast, slow, momentum, volatility].every(Number.isFinite) || volatility <= 0)
      return wait("Invalid indicators for " + frame);
    const direction = fast > slow && momentum > 50 && momentum < 70 ? "BUY" :
      fast < slow && momentum < 50 && momentum > 30 ? "SELL" : "WAIT";
    analysis[frame] = {
      direction, ema20: fast, ema50: slow, rsi14: momentum,
      atr14: volatility, close: closes[closes.length - 1]
    };
  }

  const sides = [analysis["4h"].direction, analysis["1h"].direction,
    analysis["15min"].direction];
  if (sides.includes("WAIT") || new Set(sides).size !== 1)
    return { ...wait("Timeframes disagree"), analysis };

  const signal = sides[0];
  const entryReference = analysis["15min"].close;
  const stopDistance = 1.5 * analysis["15min"].atr14;
  const sign = signal === "BUY" ? 1 : -1;
  return {
    signal,
    executable: false,
    entryReference,
    stopReference: entryReference - sign * stopDistance,
    target1Reference: entryReference + sign * stopDistance,
    target2Reference: entryReference + sign * 2 * stopDistance,
    analysis,
    warning: "Research signal only. Confirm live broker price, spread and news before any trade."
  };
}

function candleTimestamp(candle) {
  if (!candle || typeof candle.datetime !== "string") return NaN;
  const value = candle.datetime.includes("T")
    ? candle.datetime : candle.datetime.replace(" ", "T") + "Z";
  return Date.parse(value);
}

function orderedFrame(input, frame) {
  const duration = FRAME_MINUTES[frame];
  if (!duration || !Array.isArray(input)) throw new Error("Invalid " + frame + " candles");
  const output = input.map(c => ({ ...c, _time: candleTimestamp(c) }))
    .filter(c => Number.isFinite(c._time))
    .sort((a, b) => a._time - b._time);
  if (output.length < 60) throw new Error("Insufficient " + frame + " candles");
  for (let i = 1; i < output.length; i++) {
    if (output[i]._time <= output[i - 1]._time)
      throw new Error("Duplicate or unordered " + frame + " timestamps");
  }
  return { durationMs: duration * 60000, candles: output };
}

// At each M15 close, use only H1/H4 candles whose close time has passed.
// A signal at index i enters on M15 index i+1 in the backtester.
function generateHistoricalSignals(frames) {
  if (!frames || typeof frames !== "object") throw new Error("Missing candle frames");
  const ordered = Object.fromEntries(Object.keys(FRAME_MINUTES)
    .map(frame => [frame, orderedFrame(frames[frame], frame)]));
  const m15 = ordered["15min"].candles;
  const positions = { "15min": -1, "1h": -1, "4h": -1 };
  const signals = [];

  for (let i = 0; i < m15.length - 1; i++) {
    const decisionTime = m15[i]._time + ordered["15min"].durationMs;
    const snapshot = {};
    for (const frame of Object.keys(FRAME_MINUTES)) {
      const source = ordered[frame];
      while (positions[frame] + 1 < source.candles.length &&
          source.candles[positions[frame] + 1]._time + source.durationMs <= decisionTime) {
        positions[frame]++;
      }
      snapshot[frame] = source.candles.slice(0, positions[frame] + 1)
        .map(({ _time, ...candle }) => candle);
    }

    const decision = analyze(snapshot, { historical: true });
    if (decision.signal === "BUY" || decision.signal === "SELL") {
      signals.push({
        index: i,
        side: decision.signal,
        stop: decision.stopReference,
        target: decision.target2Reference
      });
    }
  }
  return signals;
}

module.exports = { analyze, ema, rsi, atr, parseCandles, generateHistoricalSignals };
