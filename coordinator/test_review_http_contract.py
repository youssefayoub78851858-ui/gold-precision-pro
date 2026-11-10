"""HTTP compatibility tests for the review server using only a local mock broker."""
import datetime
import json
import os
import pathlib
import secrets
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent
REPO = ROOT.parent
NOW = 1794301205000  # 2026-11-10 09:00:05 UTC
TOKEN = secrets.token_urlsafe(40)
FRAMES = {"15min": 900000, "1h": 3600000, "4h": 14400000}
LEGACY_CANDLE_KEYS = {"symbol", "interval", "source", "values"}
LEGACY_ANALYZE_KEYS = {"symbol", "marketStatus", "dataStatus", "signal", "agreement",
                       "indicators", "experimentalV2", "warning"}
LEGACY_INDICATOR_KEYS = {"candleTime", "close", "ema20", "ema50", "rsi14", "trend"}
LEGACY_BACKTEST_KEYS = {"trades", "wins", "losses", "netProfitableTrades", "winRate",
                        "profitFactor", "totalR", "estimatedPnL", "estimatedPnLIsHypothetical",
                        "tradesDetail", "openAtEnd", "auditNotes"}


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def fixture(frame, now=NOW, count=180):
    duration = FRAMES[frame]
    latest = now // duration * duration
    values = []
    for i in range(count):
        stamp = latest - i * duration
        price = 4200 + i * 0.1
        values.append({
            "datetime": datetime.datetime.fromtimestamp(stamp / 1000, datetime.timezone.utc)
                .strftime("%Y-%m-%d %H:%M:%S"),
            "open": price, "high": price + 1, "low": price - 1, "close": price + 0.05,
        })
    return {"symbol": "XAU/USD", "meta": {"interval": frame}, "values": values}


class MockBroker:
    def __init__(self, directory, mode="ok"):
        sys.path.insert(0, str(ROOT))
        from broker import Broker, serve
        self.mode = mode
        self.calls = []
        self.clock = NOW
        def provider(frame, outputsize, end_date):
            self.calls.append((frame, outputsize, end_date))
            if self.mode == "error":
                raise RuntimeError("synthetic upstream failure")
            if self.mode == "timeout":
                time.sleep(0.35)
            size = 30 if self.mode == "short" else 180
            return fixture(frame, self.clock, size)
        self.broker = Broker(pathlib.Path(directory) / "quota.sqlite3", provider,
                             clock=lambda: self.clock)
        self.broker.session_open = lambda _now: True
        self.token = TOKEN
        self.server = serve(self.broker, 0, "127.0.0.1", self.token)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)


class ReviewHTTPContract(unittest.TestCase):
    def start_app(self, broker_url=None, broker_token=None, fetch_timeout_ms=None):
        port = free_port()
        temporary = tempfile.TemporaryDirectory()
        preload = pathlib.Path(temporary.name) / "offline-transport.cjs"
        preload.write_text('''
const NativeDate = Date;
const fixed = Number(process.env.TEST_NOW);
global.Date = class extends NativeDate {
  constructor(...args) { super(...(args.length ? args : [fixed])); }
  static now() { return fixed; }
};
if (process.env.TEST_FETCH_TIMEOUT_MS) {
  const nativeTimeout = AbortSignal.timeout.bind(AbortSignal);
  AbortSignal.timeout = () => nativeTimeout(Number(process.env.TEST_FETCH_TIMEOUT_MS));
}
const originalFetch = global.fetch;
global.fetch = (input, init) => {
  const target = new URL(typeof input === "string" ? input : (input.href || input.url));
  const allowed = new URL(process.env.MARKET_DATA_BROKER_URL).host;
  if (target.host !== allowed || target.pathname !== "/time_series")
    return Promise.reject(new Error("Blocked non-broker network request"));
  return originalFetch(input, init);
};
''', encoding="utf-8")
        env = {k: v for k, v in os.environ.items()
               if k not in {"TWELVE_DATA_API_KEY", "NODE_OPTIONS", "DEMO_MODE"}}
        env.update(PORT=str(port), NODE_OPTIONS="--require=" + str(preload), TEST_NOW=str(NOW))
        if broker_url:
            env["MARKET_DATA_BROKER_URL"] = broker_url
        else:
            env.pop("MARKET_DATA_BROKER_URL", None)
        if broker_token:
            env["BROKER_TOKEN"] = broker_token
        else:
            env.pop("BROKER_TOKEN", None)
        if fetch_timeout_ms:
            env["TEST_FETCH_TIMEOUT_MS"] = str(fetch_timeout_ms)
        else:
            env.pop("TEST_FETCH_TIMEOUT_MS", None)
        process = subprocess.Popen(["node", str(REPO / "server.js")], env=env,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        base = f"http://127.0.0.1:{port}"
        for _ in range(100):
            if process.poll() is not None:
                error = process.communicate()[1].decode(errors="replace")
                temporary.cleanup()
                raise RuntimeError("Review server exited: " + error)
            try:
                urllib.request.urlopen(base + "/health", timeout=.2).close()
                return process, base, temporary
            except OSError:
                time.sleep(.03)
        process.terminate()
        process.communicate(timeout=3)
        temporary.cleanup()
        raise RuntimeError("Review server readiness timeout")

    @staticmethod
    def stop_app(context):
        process, _base, temporary = context
        process.terminate()
        try:
            process.communicate(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate(timeout=3)
        temporary.cleanup()

    @staticmethod
    def request(base, path, method="GET", body=None, timeout=3):
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(base + path, data=data, method=method,
            headers={"Content-Type": "application/json"} if data is not None else {})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            return error.code, json.load(error)

    def test_native_live_and_analysis_paths_use_broker_and_keep_legacy_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            broker = MockBroker(directory)
            app = self.start_app(broker.url, broker.token)
            try:
                for frame in FRAMES:
                    status, body = self.request(app[1], f"/api/candles?interval={frame}")
                    self.assertEqual(status, 200, (body, broker.calls))
                    self.assertEqual(set(body), LEGACY_CANDLE_KEYS)
                    self.assertEqual(body["symbol"], "XAU/USD")
                    self.assertEqual(body["interval"], frame)
                    self.assertEqual(body["source"], "Twelve Data")
                self.assertEqual(len(broker.calls), 3)
                self.assertTrue(all(call[1] == 2000 for call in broker.calls))

                status, body = self.request(app[1], "/api/analyze")
                self.assertEqual(status, 200, (body, broker.calls))
                self.assertEqual(set(body), LEGACY_ANALYZE_KEYS)
                self.assertEqual(set(body["indicators"]), set(FRAMES))
                self.assertTrue(all(set(item) == LEGACY_INDICATOR_KEYS for item in body["indicators"].values()))
                self.assertIn(body["signal"], {"BUY", "SELL", "WAIT"})
                self.assertTrue(all(call[1] == 2000 for call in broker.calls))
                # The broker has a shared frame key; analysis reuses the candles fetched above.
                self.assertEqual(len(broker.calls), 3)
            finally:
                self.stop_app(app)
                broker.close()

    def test_historical_periods_for_each_native_frame_keep_legacy_shape(self):
        for frame in FRAMES:
            with self.subTest(frame=frame), tempfile.TemporaryDirectory() as directory:
                broker = MockBroker(directory)
                app = self.start_app(broker.url, broker.token)
                try:
                    for period, expected_end in (("august", "2026-08-31"), ("older", "2026-09-30")):
                        status, body = self.request(app[1], f"/api/candles?interval={frame}&period={period}")
                        self.assertEqual(status, 200)
                        self.assertEqual(set(body), LEGACY_CANDLE_KEYS)
                        self.assertEqual(body["interval"], frame)
                        self.assertEqual(broker.calls[-1], (frame, 2000, expected_end))
                    self.assertEqual(len(broker.calls), 2)
                finally:
                    self.stop_app(app)
                    broker.close()

    def test_unconfigured_broker_matches_legacy_503_shapes(self):
        app = self.start_app()
        try:
            status, candles = self.request(app[1], "/api/candles?interval=15min")
            self.assertEqual((status, candles), (503, {"error": "API key not configured"}))
            status, analysis = self.request(app[1], "/api/analyze")
            self.assertEqual((status, analysis), (503, {"error": "Data API not configured"}))
        finally:
            self.stop_app(app)

    def test_provider_failure_is_clear_and_never_returns_an_analysis_signal(self):
        with tempfile.TemporaryDirectory() as directory:
            broker = MockBroker(directory, mode="error")
            app = self.start_app(broker.url, broker.token)
            try:
                status, candles = self.request(app[1], "/api/candles?interval=15min")
                self.assertEqual(status, 502)
                self.assertEqual(set(candles), {"error", "detail"})
                self.assertEqual(candles["error"], "Market data unavailable")
                status, analysis = self.request(app[1], "/api/analyze")
                self.assertEqual(status, 502)
                self.assertEqual(analysis, {"error": "Market data unavailable", "interval": "15min"})
                self.assertNotIn("signal", analysis)
                status, v3 = self.request(app[1], "/api/v3/research")
                self.assertEqual(status, 503)
                self.assertEqual(v3["signal"], "WAIT")
                self.assertFalse(v3["executable"])
            finally:
                self.stop_app(app)
                broker.close()

    def test_timeout_and_incomplete_bars_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            broker = MockBroker(directory, mode="timeout")
            app = self.start_app(broker.url, broker.token, fetch_timeout_ms=60)
            try:
                status, body = self.request(app[1], "/api/candles?interval=15min", timeout=2)
                self.assertEqual(status, 502)
                self.assertEqual(body, {"error": "Market data request failed"})
            finally:
                self.stop_app(app)
                broker.close()
        with tempfile.TemporaryDirectory() as directory:
            broker = MockBroker(directory, mode="short")
            app = self.start_app(broker.url, broker.token)
            try:
                status, body = self.request(app[1], "/api/analyze")
                self.assertEqual(status, 502)
                self.assertEqual(set(body), {"error", "frame", "count", "invalidPrices"})
                self.assertEqual(body["error"], "Insufficient candles")
                self.assertNotIn("signal", body)
            finally:
                self.stop_app(app)
                broker.close()

    def test_backtest_status_and_json_shape_match_legacy_route(self):
        app = self.start_app()
        try:
            data = {"candles": [
                {"open": 100, "high": 101, "low": 99, "close": 100},
                {"open": 100, "high": 105, "low": 99.5, "close": 104},
                {"open": 104, "high": 106, "low": 103, "close": 105},
            ], "signals": [{"index": 0, "side": "BUY", "stop": 99}]}
            status, result = self.request(app[1], "/api/backtest", "POST", data)
            self.assertEqual(status, 200)
            self.assertEqual(set(result), LEGACY_BACKTEST_KEYS)
            self.assertEqual(result["trades"], 1)
            self.assertEqual(result["wins"], 1)
            status, error = self.request(app[1], "/api/backtest", "POST", {})
            self.assertEqual((status, error), (400, {"error": "Invalid backtest input"}))
            status, error = self.request(app[1], "/api/backtest", "GET")
            self.assertEqual((status, error), (405, {"error": "POST required"}))
        finally:
            self.stop_app(app)


if __name__ == "__main__":
    unittest.main()
