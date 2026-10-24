import re
import sys
import pandas as pd

alerts_file, labels_file = sys.argv[1], sys.argv[2]
pat = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+(\w+)\s+(.*)$")

alerts = []
for line in open(alerts_file):
    m = pat.match(line)
    if m:
        text = m.group(3).lower()
        if "unusual" in text:
            k = "ml"
        elif "cpu" in text:
            k = "cpu"
        elif "ram" in text:
            k = "ram"
        elif "disk" in text:
            k = "disk"
        elif "network" in text or "net" in text:
            k = "net"
        else:
            k = "other"
        alerts.append((pd.Timestamp(m.group(1)), k, m.group(3)))

lab = pd.read_csv(labels_file)
lab["start"] = pd.to_datetime(lab["start"])
lab["end"] = pd.to_datetime(lab["end"])
grace = pd.Timedelta(seconds=5)

print(f"alerts parsed: {len(alerts)}   labels: {labels_file}")
print(f"{'label':<12}{'kind':<8}{'subtle':<8}{'matching':<10}{'any':<6}{'ml':<4}")
caught = 0
events = 0
for _, r in lab.iterrows():
    inside = [a for a in alerts if r["start"] <= a[0] <= r["end"] + grace]
    if r["kind"] == "normal":
        print(f"{r['label']:<12}{'normal':<8}{'':<8}{'':<10}{len(inside):<6}{'':<4}  <- alerts in calm window")
        continue
    events += 1
    match = [a for a in inside if a[1] == r["kind"]]
    ml = [a for a in inside if a[1] == "ml"]
    caught += 1 if match else 0
    print(f"{r['label']:<12}{r['kind']:<8}{str(r['subtle']):<8}{len(match):<10}{len(inside):<6}{len(ml):<4}")

span_start, span_end = lab["start"].min(), lab["end"].max()
in_span = [a for a in alerts if span_start <= a[0] <= span_end + grace]
print(f"\nevents caught by their matching rule: {caught}/{events}")
print(f"all alerts inside the run span {span_start} to {span_end}: {len(in_span)}")
