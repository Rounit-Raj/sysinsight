#!/usr/bin/env python3
"""SysInsight live detector.

Reads new rows from data/sysinsight.db, compares each second against a rolling
calm baseline, and writes alerts into the alerts table.
  - Four rules (CPU, RAM, disk write, network) -> HIGH alerts
  - Isolation Forest "unusual pattern" warning -> LOW alerts
One alert is written per event, not one per second.

Usage:
  python3 ml/live_detector.py                      # live mode
  python3 ml/live_detector.py --replay --dry-run   # test on old data, no writes
"""
import argparse
import math
import sqlite3
import statistics
import time
from collections import deque

import numpy as np
from sklearn.ensemble import IsolationForest

# k = robust standard deviations above baseline, floor = minimum margin
RULES = {
    "CPU spike":        {"k": 6.0, "floor": 15.0,  "unit": "%"},
    "RAM jump":         {"k": 6.0, "floor": 3.0,   "unit": "%"},
    "Disk write burst": {"k": 6.0, "floor": 5.0,   "unit": " MB/s"},
    "Network surge":    {"k": 6.0, "floor": 500.0, "unit": " KB/s"},
}
PATTERN = "Unusual pattern"
WINDOW = 600     # seconds of calm history kept per rule
SEED_ROWS = 300  # calm rows read at startup in live mode
WARMUP = 60      # rows needed before a rule starts judging
CLEAR = 10       # calm seconds needed to end an event
ABSORB = 300     # seconds of constant alert before it becomes the new normal

# Isolation Forest settings
IF_MIN = 120      # calm rows needed before the forest starts judging
IF_REFIT = 300    # refit the forest on the rolling baseline every N seconds
IF_QUANTILE = 0.5 # a second is "odd" if it scores in the worst 0.5% of the baseline
IF_CONSEC = 3     # odd seconds in a row needed before warning

COLS = ("SELECT s.id, s.timestamp, s.cpu_percent, s.ram_percent, "
        "i.disk_write_mb_s, i.net_rx_kb_s + i.net_tx_kb_s, s.load_avg_1min "
        "FROM samples s LEFT JOIN io i ON i.timestamp = s.timestamp ")
Q_NEW = COLS + "WHERE s.id > ? ORDER BY s.id"
Q_SEED = COLS + "ORDER BY s.id DESC LIMIT ?"


class UnusualPattern:
    """Isolation Forest trained on the rolling calm baseline."""

    def __init__(self):
        self.base = deque(maxlen=WINDOW)
        self.model = None
        self.thresh = None
        self.since_fit = 0
        self.flagged = 0
        self.calm = 0
        self.active = False
        self.run = []

    @staticmethod
    def features(row):
        cpu, ram, disk, net, load = row[2], row[3], row[4], row[5], row[6]
        if None in (cpu, ram, disk, net, load):
            return None
        return [cpu, ram, load, math.log1p(max(disk, 0)), math.log1p(max(net, 0))]

    def seed(self, row):
        f = self.features(row)
        if f:
            self.base.append(f)

    def fit(self):
        X = np.array(self.base)
        self.model = IsolationForest(n_estimators=100, random_state=42).fit(X)
        self.thresh = np.percentile(self.model.score_samples(X), IF_QUANTILE)
        self.since_fit = 0

    def step(self, row, rules_active):
        """Return a warning message when a new unusual-pattern event starts."""
        f = self.features(row)
        if f is None:
            return None
        self.since_fit += 1
        if (self.model is None or self.since_fit >= IF_REFIT) and len(self.base) >= IF_MIN:
            self.fit()
        if self.model is None:
            self.base.append(f)
            return None
        if rules_active:
            # a rule owns this moment: do not learn from it, do not warn
            self.flagged = 0
            self.run.clear()
            return None
        odd = float(self.model.score_samples([f])[0]) < self.thresh
        if not odd:
            self.base.append(f)
            self.flagged = 0
            self.run.clear()
            self.calm += 1
            if self.calm >= CLEAR:
                self.active = False
            return None
        self.calm = 0
        self.flagged += 1
        self.run.append(f)
        if len(self.run) >= ABSORB:
            self.base.extend(self.run)
            self.run.clear()
            self.active = False
            self.since_fit = IF_REFIT  # force a refit with the new normal
            return None
        if self.flagged >= IF_CONSEC and not self.active:
            self.active = True
            return (f"Unusual pattern: CPU {f[0]:.1f}%, RAM {f[1]:.1f}%, "
                    f"load {f[2]:.2f} (combination not seen in calm baseline)")
        return None


class Detector:
    def __init__(self, con, dry_run):
        self.con = con
        self.dry = dry_run
        self.win = {n: deque(maxlen=WINDOW) for n in RULES}
        self.run = {n: [] for n in RULES}
        self.active = {n: False for n in RULES}
        self.calm = {n: 0 for n in RULES}
        self.count = {n: 0 for n in [*RULES, PATTERN]}
        self.pat = UnusualPattern()

    @staticmethod
    def limit(window, k, floor):
        med = statistics.median(window)
        mad = statistics.median(abs(x - med) for x in window)
        return med, med + max(k * 1.4826 * mad, floor)

    def seed(self, row):
        for name, v in zip(RULES, row[2:]):
            if v is not None:
                self.win[name].append(v)
        self.pat.seed(row)

    def handle(self, row):
        ts = row[1]
        for name, v in zip(RULES, row[2:]):
            if v is None:
                continue
            w = self.win[name]
            if len(w) < WARMUP:
                w.append(v)
                continue
            cfg = RULES[name]
            med, lim = self.limit(w, cfg["k"], cfg["floor"])
            run = self.run[name]
            if v <= lim:
                w.append(v)
                run.clear()
                self.calm[name] += 1
                if self.calm[name] >= CLEAR:
                    self.active[name] = False
                continue
            self.calm[name] = 0
            run.append(v)
            if len(run) >= ABSORB:
                w.clear()
                w.extend(run)
                run.clear()
                self.active[name] = False
                continue
            if not self.active[name]:
                self.active[name] = True
                u = cfg["unit"]
                msg = f"{name}: {v:.1f}{u} (calm baseline {med:.1f}{u})"
                self.alert(ts, "HIGH", msg, name)
        msg = self.pat.step(row, any(self.active.values()))
        if msg:
            self.alert(ts, "LOW", msg, PATTERN)

    def alert(self, ts, severity, msg, name):
        self.count[name] += 1
        print(f"{ts}  {severity:<4}  {msg}")
        if not self.dry:
            self.con.execute(
                "INSERT INTO alerts (timestamp, severity, message) VALUES (?,?,?)",
                (ts, severity, msg))
            self.con.commit()

    def summary(self):
        print("\nAlerts written per rule:" if not self.dry else "\nAlerts found per rule (dry run):")
        for name, c in self.count.items():
            print(f"  {name}: {c}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/sysinsight.db")
    ap.add_argument("--replay", action="store_true", help="process all old rows once, then exit")
    ap.add_argument("--dry-run", action="store_true", help="print alerts, do not write them")
    args = ap.parse_args()

    con = sqlite3.connect(args.db, timeout=10)
    det = Detector(con, args.dry_run)
    last_id = 0
    if not args.replay:
        rows = con.execute(Q_SEED, (SEED_ROWS,)).fetchall()[::-1]
        for r in rows:
            det.seed(r)
        last_id = rows[-1][0] if rows else 0
        print(f"Watching {args.db} (baseline from last {len(rows)} rows). Ctrl+C to stop.")
    try:
        while True:
            for r in con.execute(Q_NEW, (last_id,)).fetchall():
                det.handle(r)
                last_id = r[0]
            if args.replay:
                break
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    det.summary()


if __name__ == "__main__":
    main()
