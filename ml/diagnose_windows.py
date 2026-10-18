#!/usr/bin/env python3
"""Why are subtle events not alerted? Replays the rule logic and reports,
per labelled subtle window, value vs limit. Usage: diagnose_windows.py [floor_scale]"""
import csv
import sqlite3
import sys
from collections import deque

import live_detector as ld

SCALE = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
LABELS = ["data/labels_run3_std.csv", "data/labels_run3_rep1_std.csv"]
KIND_RULE = {"cpu": "CPU spike", "ram": "RAM jump", "disk": "Disk write burst"}

wins = []
for path in LABELS:
    with open(path) as f:
        for r in csv.DictReader(f):
            if r["subtle"] == "yes" and r["kind"] in KIND_RULE:
                wins.append((path.split("/")[-1], r["label"], r["start"], r["end"], KIND_RULE[r["kind"]]))

con = sqlite3.connect("data/sysinsight.db")
rows = con.execute(ld.Q_NEW, (0,)).fetchall()
names = list(ld.RULES)
win = {n: deque(maxlen=ld.WINDOW) for n in names}
run = {n: [] for n in names}
active = {n: False for n in names}
calm = {n: 0 for n in names}
rec = [[] for _ in wins]

for row in rows:
    ts = row[1]
    for name, v in zip(names, row[2:]):
        if v is None:
            continue
        w = win[name]
        if len(w) < ld.WARMUP:
            w.append(v)
            continue
        cfg = ld.RULES[name]
        floor = cfg["floor"] * SCALE
        med, lim = ld.Detector.limit(w, cfg["k"], floor)
        for i, (_, _, s, e, rule) in enumerate(wins):
            if rule == name and s <= ts < e:
                rec[i].append((v, med, lim, lim - med, abs(lim - med - floor) < 1e-9, active[name]))
        if v <= lim:
            w.append(v)
            run[name].clear()
            calm[name] += 1
            if calm[name] >= ld.CLEAR:
                active[name] = False
            continue
        calm[name] = 0
        run[name].append(v)
        if len(run[name]) >= ld.ABSORB:
            w.clear()
            w.extend(run[name])
            run[name].clear()
            active[name] = False
            continue
        active[name] = True

print(f"floor scale {SCALE}")
for (fn, label, s, e, rule), r in zip(wins, rec):
    if not r:
        print(f"\n{fn} {label} {s}: NO ROWS")
        continue
    n = len(r)
    srt = lambda k: sorted(x[k] for x in r)[n // 2]
    over = [x[0] > x[2] for x in r]
    streak = best = 0
    for o in over:
        streak = streak + 1 if o else 0
        best = max(best, streak)
    would = sum(1 for x in r if x[0] > x[2] and not x[5])
    print(f"\n{fn} {label} {s} ({rule})")
    print(f"  secs={n}  value median={srt(0):.2f} max={max(x[0] for x in r):.2f}  baseline median={srt(1):.2f}")
    print(f"  shift (value-baseline) median={srt(0)-srt(1):.2f}  margin needed median={srt(3):.2f}  floor-bound={sum(x[4] for x in r)}/{n}")
    print(f"  secs over limit={sum(over)}  longest streak={best}  closest gap (limit-value) min={min(x[2]-x[0] for x in r):.2f}")
    print(f"  seconds already-active (suppressed)={sum(x[5] for x in r)}  alerts that would fire={would}")
