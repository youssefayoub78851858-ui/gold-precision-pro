"""Transactional offline Ultimate paper account. Never submits orders or fetches data."""
import argparse
import datetime as dt
import hashlib
import json
import math
import pathlib
import sqlite3
import subprocess

UTC = dt.timezone.utc
BAR_MS = 900000
DEFAULTS = dict(initialBalance=10000, riskFraction=.005, dailyLossFraction=.02,
                valuePerPoint=100, lotStep=.01, minLot=.01, maxLot=10,
                spread=.4, slippage=.1, commissionPerLot=7)


def timestamp(value):
    parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None or parsed.utcoffset() != dt.timedelta(0):
        raise ValueError('UTC timestamp required')
    return int(parsed.timestamp() * 1000)


def iso(value):
    return dt.datetime.fromtimestamp(value / 1000, UTC).isoformat().replace('+00:00', 'Z')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def validate_bar(bar):
    opened = timestamp(bar['datetime'])
    if opened % BAR_MS:
        raise ValueError('M15 alignment required')
    o, h, l, c = [bar[k] for k in ('open', 'high', 'low', 'close')]
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v > 0 for v in (o, h, l, c)) or not l <= min(o, c) <= max(o, c) <= h:
        raise ValueError('Invalid OHLC')
    return opened


class PaperAccount:
    def __init__(self, database, config=None):
        self.db = sqlite3.connect(database, timeout=30, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS account(id INTEGER PRIMARY KEY CHECK(id=1), config TEXT NOT NULL, balance REAL NOT NULL, peak REAL NOT NULL, killed INTEGER NOT NULL DEFAULT 0, last_ms INTEGER);
          CREATE TABLE IF NOT EXISTS observations(open_ms INTEGER PRIMARY KEY, digest TEXT NOT NULL, payload TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS positions(id INTEGER PRIMARY KEY, side TEXT NOT NULL, entry REAL NOT NULL, stop REAL NOT NULL, target REAL NOT NULL, lots REAL NOT NULL, risk REAL NOT NULL, opened TEXT NOT NULL);
          CREATE UNIQUE INDEX IF NOT EXISTS one_position ON positions((1));
          CREATE TABLE IF NOT EXISTS pending(id INTEGER PRIMARY KEY CHECK(id=1), side TEXT NOT NULL, stop REAL NOT NULL, target REAL NOT NULL, expected_ms INTEGER NOT NULL);
          CREATE TABLE IF NOT EXISTS trades(id INTEGER PRIMARY KEY, side TEXT NOT NULL, entry REAL NOT NULL, exit REAL NOT NULL, stop REAL NOT NULL, target REAL NOT NULL, lots REAL NOT NULL, gross REAL NOT NULL, commission REAL NOT NULL, net REAL NOT NULL, risk REAL NOT NULL, opened TEXT NOT NULL, closed TEXT NOT NULL, reason TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, time_utc TEXT NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL);
        ''')
        row = self.db.execute('SELECT * FROM account').fetchone()
        if row is None:
            cfg = {**DEFAULTS, **(config or {})}
            self.validate_config(cfg)
            self.db.execute('INSERT OR IGNORE INTO account(id,config,balance,peak) VALUES(1,?,?,?)', (canonical(cfg), cfg['initialBalance'], cfg['initialBalance']))
        self.config = json.loads(self.db.execute('SELECT config FROM account').fetchone()[0])
        if config is not None and {**DEFAULTS, **config} != self.config:
            self.db.close()
            raise ValueError('Account configuration is immutable; use a separate database')

    @staticmethod
    def validate_config(cfg):
        if set(cfg) != set(DEFAULTS) or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in cfg.values()):
            raise ValueError('Invalid account configuration')
        if not (cfg['initialBalance'] > 0 and 0 < cfg['riskFraction'] <= .005 and 0 < cfg['dailyLossFraction'] <= .02 and cfg['valuePerPoint'] > 0 and 0 < cfg['lotStep'] <= cfg['minLot'] <= cfg['maxLot'] and min(cfg['spread'], cfg['slippage'], cfg['commissionPerLot']) >= 0):
            raise ValueError('Risk configuration outside ceilings')

    def close(self):
        self.db.close()

    def event(self, time, kind, payload):
        self.db.execute('INSERT INTO events(time_utc,kind,payload) VALUES(?,?,?)', (iso(time), kind, canonical(payload)))

    def loss(self, time):
        day = iso(time)[:10]
        return self.db.execute('SELECT COALESCE(SUM(-net),0) FROM trades WHERE net<0 AND substr(closed,1,10)=?', (day,)).fetchone()[0]

    def risk_state(self, time):
        row = self.db.execute('SELECT * FROM account').fetchone()
        c = self.config
        return {k: c[k] for k in ('riskFraction', 'dailyLossFraction', 'valuePerPoint', 'lotStep', 'minLot', 'maxLot', 'commissionPerLot', 'slippage')} | dict(equity=row['balance'], dailyLoss=self.loss(time), killSwitch=bool(row['killed']), activeTrades=self.db.execute('SELECT COUNT(*) FROM positions').fetchone()[0])

    def kill(self, enabled=True):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            self.db.execute('UPDATE account SET killed=? WHERE id=1', (int(enabled),))
            if enabled:
                self.db.execute('DELETE FROM pending')
            last = self.db.execute('SELECT last_ms FROM account').fetchone()[0]
            self.event(int(dt.datetime.now(UTC).timestamp() * 1000), 'KILL_SWITCH', {'enabled': bool(enabled), 'lastObservationUTC': iso(last + BAR_MS) if last is not None else None})
            self.db.execute('COMMIT')
        except Exception:
            self.db.execute('ROLLBACK')
            raise

    def step(self, bar, snapshot=None, evaluator=None):
        opened = validate_bar(bar)
        if snapshot is not None and timestamp(snapshot['asOfUTC']) != opened + BAR_MS:
            raise ValueError('Snapshot must match this closed bar')
        if snapshot is not None and evaluator is None and snapshot.get('frames', {}).get('M15', [None])[-1] != bar:
            raise ValueError('Snapshot M15 close must match processed bar')
        payload = canonical({'bar': bar, 'snapshot': snapshot})
        digest = hashlib.sha256(payload.encode()).hexdigest()
        self.db.execute('BEGIN IMMEDIATE')
        try:
            prior = self.db.execute('SELECT digest FROM observations WHERE open_ms=?', (opened,)).fetchone()
            if prior:
                if prior[0] != digest:
                    raise ValueError('Conflicting replay at same timestamp')
                self.db.execute('COMMIT')
                return {'duplicate': True}
            account = self.db.execute('SELECT * FROM account').fetchone()
            if account['last_ms'] is not None and opened <= account['last_ms']:
                raise ValueError('Out-of-order observation')
            self.db.execute('INSERT INTO observations VALUES(?,?,?)', (opened, digest, payload))
            pending = self.db.execute('SELECT * FROM pending').fetchone()
            if pending:
                self.db.execute('DELETE FROM pending')
                if pending['expected_ms'] == opened:
                    self.enter(pending, bar, opened)
                else:
                    self.event(opened, 'CANCEL', {'reason': 'Missing next entry bar'})
            position = self.db.execute('SELECT * FROM positions').fetchone()
            if position:
                self.exit_if_hit(position, bar, opened)
            if snapshot is not None:
                supplied = {**snapshot, 'spread': self.config['spread'], 'risk': self.risk_state(opened + BAR_MS)}
                decision = (evaluator or evaluate)(supplied)
                if decision.get('executable') is not False or decision.get('signal') != 'WAIT':
                    raise ValueError('Paper input must remain non-executable research')
                self.event(opened + BAR_MS, 'DECISION', decision)
                if decision.get('researchCandidate') in ('BUY', 'SELL') and decision.get('risk', {}).get('ok') is True and not self.db.execute('SELECT 1 FROM positions').fetchone() and not self.risk_state(opened + BAR_MS)['killSwitch']:
                    p = decision['tradePlan']
                    stop, target = p['stop'], p['target']
                    if not all(isinstance(v, (int, float)) and math.isfinite(v) and v > 0 for v in (stop, target)):
                        raise ValueError('Invalid pending geometry')
                    self.db.execute('INSERT INTO pending VALUES(1,?,?,?,?)', (decision['researchCandidate'], stop, target, opened + BAR_MS))
            self.db.execute('UPDATE account SET last_ms=? WHERE id=1', (opened,))
            self.db.execute('COMMIT')
            return self.summary()
        except Exception:
            self.db.execute('ROLLBACK')
            raise

    def enter(self, pending, bar, opened):
        c, state = self.config, self.risk_state(opened)
        if state['killSwitch'] or state['activeTrades'] or state['equity'] <= 0:
            self.event(opened, 'REJECT_ENTRY', {'reason': 'Account locked or position active'})
            return
        sign = 1 if pending['side'] == 'BUY' else -1
        entry = bar['open'] + (c['spread'] if sign == 1 else 0) + sign * c['slippage']
        stop, target = pending['stop'], pending['target']
        if sign * (entry - stop) <= 0 or sign * (target - entry) <= 0:
            self.event(opened, 'REJECT_ENTRY', {'reason': 'Gap invalidated geometry'})
            return
        remaining = state['equity'] * c['dailyLossFraction'] - state['dailyLoss']
        budget = min(state['equity'] * c['riskFraction'], remaining)
        per_lot = (abs(entry - stop) + c['slippage']) * c['valuePerPoint'] + c['commissionPerLot']
        lots = math.floor(min(c['maxLot'], max(0, budget) / per_lot) / c['lotStep']) * c['lotStep']
        if lots < c['minLot'] or lots * per_lot > budget:
            self.event(opened, 'REJECT_ENTRY', {'reason': 'Risk budget below minimum lot'})
            return
        self.db.execute('INSERT INTO positions(side,entry,stop,target,lots,risk,opened) VALUES(?,?,?,?,?,?,?)', (pending['side'], entry, stop, target, lots, lots * per_lot, iso(opened)))
        self.event(opened, 'PAPER_ENTRY', dict(side=pending['side'], entry=entry, stop=stop, target=target, lots=lots, risk=lots * per_lot))

    def exit_if_hit(self, p, bar, opened):
        c = self.config
        sign = 1 if p['side'] == 'BUY' else -1
        # Input OHLC is BID. SELL positions exit at ASK, including the spread.
        adjustment = c['spread'] if sign == -1 else 0
        o, h, l = (bar[k] + adjustment for k in ('open', 'high', 'low'))
        stop_hit = l <= p['stop'] if sign == 1 else h >= p['stop']
        target_hit = h >= p['target'] if sign == 1 else l <= p['target']
        if (o <= p['stop'] if sign == 1 else o >= p['stop']):
            price, reason = o, 'GAP_STOP'
        elif (o >= p['target'] if sign == 1 else o <= p['target']):
            price, reason = p['target'], 'GAP_TARGET'
        elif stop_hit:
            price, reason = p['stop'], 'STOP_FIRST' if target_hit else 'STOP'
        elif target_hit:
            price, reason = p['target'], 'TARGET'
        else:
            return
        exit_price = price - sign * c['slippage']
        gross = sign * (exit_price - p['entry']) * p['lots'] * c['valuePerPoint']
        commission = c['commissionPerLot'] * p['lots']
        net = gross - commission
        closed = iso(opened + BAR_MS)
        self.db.execute('INSERT INTO trades(side,entry,exit,stop,target,lots,gross,commission,net,risk,opened,closed,reason) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)', (p['side'], p['entry'], exit_price, p['stop'], p['target'], p['lots'], gross, commission, net, p['risk'], p['opened'], closed, reason))
        self.db.execute('UPDATE account SET balance=balance+?,peak=MAX(peak,balance+?) WHERE id=1', (net, net))
        self.db.execute('DELETE FROM positions')
        self.event(opened + BAR_MS, 'PAPER_EXIT', dict(net=net, price=exit_price, reason=reason))

    def summary(self):
        a = dict(self.db.execute('SELECT balance,peak,killed,last_ms FROM account').fetchone())
        origins = sorted({json.loads(row[0])['bar'].get('dataOrigin', 'UNVERIFIED') for row in self.db.execute('SELECT payload FROM observations')})
        return dict(mode='OFFLINE_PAPER', executable=False, config=self.config, dataOrigin=', '.join(origins) or 'NO_DATA', account=a,
                    position=[dict(r) for r in self.db.execute('SELECT * FROM positions')],
                    pending=[dict(r) for r in self.db.execute('SELECT * FROM pending')],
                    trades=[dict(r) for r in self.db.execute('SELECT * FROM trades')])


def evaluate(snapshot):
    result = subprocess.run(['node', '-e', "const fs=require('fs');console.log(JSON.stringify(require(process.argv[1]).evaluate(JSON.parse(fs.readFileSync(0,'utf8')))))", str(pathlib.Path(__file__).with_name('v3_ultimate.js'))], input=canonical(snapshot), text=True, capture_output=True, check=True)
    return json.loads(result.stdout)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database')
    parser.add_argument('--replay', help='Offline JSON array of {bar,snapshot} observations')
    parser.add_argument('--kill', action='store_true')
    args = parser.parse_args()
    account = PaperAccount(args.database)
    try:
        if args.kill:
            account.kill()
        if args.replay:
            for observation in json.loads(pathlib.Path(args.replay).read_text()):
                account.step(**observation)
        print(json.dumps(account.summary(), indent=2))
    finally:
        account.close()
