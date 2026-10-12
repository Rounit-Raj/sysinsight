import csv, re, sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta

SCALES = ["1.0", "0.5", "0.3", "0.2", "0.1"]
RUN3 = ["data/labels_run3_std.csv", "data/labels_run3_rep1_std.csv"]
OTHER = ["data/labels_run1.csv", "data/labels_run2.csv", "data/labels_net_run.csv"]
KIND = {"cpu": "CPU spike", "ram": "RAM jump", "disk": "Disk write burst", "net": "Network surge"}
PAD = timedelta(seconds=10)

def ts(x, date="2026-10-11"):
    x = x.strip()
    if re.fullmatch(r"\d{1,2}:\d{2}:\d{2}", x):
        x = f"{date} {x}"
    return datetime.strptime(x.replace("T", " ")[:19], "%Y-%m-%d %H:%M:%S")

def load(path, allow_time_only):
    rows = []
    with open(path) as f:
        for r in csv.DictReader(f):
            if not allow_time_only and re.fullmatch(r"\d{1,2}:\d{2}:\d{2}", r["start"].strip()):
                print(f"skipped {path} (time-only timestamps)")
                return []
            rows.append((ts(r["start"]), ts(r["end"]), r["label"], r["kind"]))
    return rows

run3 = [e for p in RUN3 for e in load(p, True)]
spans = [(s, e) for s, e, _, _ in run3]
for p in OTHER:
    spans += [(s, e) for s, e, _, _ in load(p, False)]

pat = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)\s+(HIGH|LOW)\s+([^:]+)")
out = []
def say(t=""):
    print(t); out.append(t)

for sc in SCALES:
    alerts = []
    for line in open(f"docs/results/replay_floor_{sc}.txt"):
        m = pat.match(line)
        if m:
            alerts.append((ts(m.group(1)), m.group(2), m.group(3).strip()))
    say(f"=== floor scale {sc} ({len(alerts)} alerts total) ===")
    det = defaultdict(lambda: [0, 0])
    gap_alerts, gap_secs = Counter(), 0
    for s, e, label, kind in run3:
        inwin = [a for a in alerts if s <= a[0] <= e + PAD]
        if kind == "normal":
            gap_secs += int((e - s).total_seconds())
            for a in inwin:
                gap_alerts[a[2]] += 1
        else:
            det[label][1] += 1
            if any(a[2] == KIND.get(kind) for a in inwin):
                det[label][0] += 1
    for label, (d, n) in det.items():
        say(f"  {label:<12} detected {d}/{n}")
    say(f"  normal gaps ({gap_secs}s): {sum(gap_alerts.values())} alerts {dict(gap_alerts)}")
    outside = Counter(a[2] for a in alerts
                      if not any(s - PAD <= a[0] <= e + PAD for s, e in spans))
    say(f"  outside all labelled spans: {sum(outside.values())} alerts {dict(outside)}")
    say()

open("docs/results/floor_sweep_event_check.txt", "w").write("\n".join(out) + "\n")
