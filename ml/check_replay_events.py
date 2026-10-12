import re
import pandas as pd

ALERTS = "docs/results/replay_alerts_20261011.txt"
LABELS = ["data/labels_run3_std.csv", "data/labels_run3_rep1_std.csv"]
SLACK = pd.Timedelta(seconds=10)  # alerts may land just after an event ends
KEYS = {"cpu": "CPU spike", "ram": "RAM jump",
        "disk": "Disk write", "net": "Network surge"}

pat = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+(\w+)\s+(.*)$")
alerts = []
with open(ALERTS) as f:
    for line in f:
        m = pat.match(line.strip())
        if m:
            alerts.append((pd.Timestamp(m.group(1)), m.group(2),
                           m.group(3).split(":")[0]))
print(f"parsed alerts: {len(alerts)}")

used = set()
for path in LABELS:
    lab = pd.read_csv(path)
    lab["start"] = pd.to_datetime(lab["start"])
    lab["end"] = pd.to_datetime(lab["end"])
    print(f"\n=== {path} ===")
    hit_subtle = any_subtle = n_subtle = 0
    normal_alerts = 0
    for _, r in lab.iterrows():
        inside = [(i, a) for i, a in enumerate(alerts)
                  if r["start"] <= a[0] <= r["end"] + SLACK]
        used.update(i for i, _ in inside)
        types = {}
        for _, a in inside:
            types[a[2]] = types.get(a[2], 0) + 1
        if r["kind"] == "normal":
            normal_alerts += len(inside)
            print(f"  NORMAL  {r['start'].time()}-{r['end'].time()}  "
                  f"alerts: {len(inside)} {types}")
            continue
        key = KEYS.get(r["kind"], "")
        match = sum(1 for _, a in inside if a[2].startswith(key))
        n_subtle += 1
        hit_subtle += match > 0
        any_subtle += len(inside) > 0
        print(f"  {r['label']:<11} kind={r['kind']:<4} "
              f"{r['start'].time()}-{r['end'].time()}  "
              f"matching rule alerts: {match}  all alerts: {len(inside)} {types}")
    print(f"  -> events detected by the matching rule: {hit_subtle}/{n_subtle}; "
          f"by any alert: {any_subtle}/{n_subtle}; "
          f"alerts in normal gaps: {normal_alerts}")

print(f"\nalerts outside every labelled window: {len(alerts) - len(used)} "
      f"(unlabelled activity, not necessarily false alarms)")
