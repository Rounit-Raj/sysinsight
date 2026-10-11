from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
BASE = ["cpu_percent", "ram_percent", "load_avg_1min"]
IO = ["disk_read_mb_s", "disk_write_mb_s", "net_rx_kb_s", "net_tx_kb_s"]
RUNS = {"run3": "labels_run3_std.csv", "rep1": "labels_run3_rep1_std.csv"}
ALL_LABELS = ["labels_run1.csv", "labels_run2.csv", "labels_net_run.csv",
              "labels_run3_std.csv", "labels_run3_rep1_std.csv"]
BASELINE_MIN = 45
EDGE_S = 3
CALM_MARGIN_S = 30
FLOORS = {"cpu_percent": 5.0, "ram_percent": 2.0, "disk_write_mb_s_log": 0.5,
          "net_rx_kb_s_log": 0.5, "net_tx_kb_s_log": 0.5}


def load_labels(name):
    lab = pd.read_csv(DATA / name)
    lab["start"] = pd.to_datetime(lab["start"])
    lab["end"] = pd.to_datetime(lab["end"])
    return lab


readings = pd.read_csv(DATA / "readings.csv").drop_duplicates("timestamp")
io = pd.read_csv(DATA / "io.csv").drop_duplicates("timestamp")
readings["timestamp"] = pd.to_datetime(readings["timestamp"])
io["timestamp"] = pd.to_datetime(io["timestamp"])
df = readings.merge(io, on="timestamp").sort_values("timestamp").reset_index(drop=True)
IOL = []
for c in IO:
    df[c + "_log"] = np.log1p(df[c])
    IOL.append(c + "_log")

# Mark every second near any labelled anomaly (all runs) as not calm
calm_ok = pd.Series(True, index=df.index)
cm = pd.Timedelta(seconds=CALM_MARGIN_S)
for name in ALL_LABELS:
    if not (DATA / name).exists():
        print(f"warning: {name} not found, skipped")
        continue
    lab = load_labels(name)
    for _, r in lab[lab["label"] != "normal"].iterrows():
        calm_ok &= ~((df["timestamp"] >= r["start"] - cm) & (df["timestamp"] <= r["end"] + cm))


def max_run(a):
    best = cur = 0
    for v in a:
        cur = cur + 1 if v else 0
        best = max(best, cur)
    return best


print("* = detected (3+ consecutive flagged seconds). Numbers = % of the event's seconds flagged.")
print("rulesN = four rules (CPU, RAM, disk write, network) with threshold T=N; IF = Isolation Forest alone; hybN = rules OR IF.\n")

for run, fname in RUNS.items():
    lab = load_labels(fname)
    w0, w1 = lab["start"].min(), lab["end"].max()
    base = df[calm_ok & (df["timestamp"] < w0) &
              (df["timestamp"] >= w0 - pd.Timedelta(minutes=BASELINE_MIN))].copy()
    test = df[(df["timestamp"] >= w0) & (df["timestamp"] <= w1)].copy().reset_index(drop=True)
    print(f"=== {run} ({fname}) window {w0} -> {w1}")
    print(f"baseline rows: {len(base)} | test rows before trimming: {len(test)} "
          f"(window is {int((w1 - w0).total_seconds())} s)")
    if len(base) < 300 or len(test) < 100:
        print("not enough data in readings.csv/io.csv for this window, skipped\n")
        continue

    test["event"] = -1
    for idx, r in lab.iterrows():
        if r["label"] != "normal":
            m = (test["timestamp"] >= r["start"]) & (test["timestamp"] < r["end"])
            test.loc[m, "event"] = idx
    margin = pd.Timedelta(seconds=EDGE_S)
    edge = pd.Series(False, index=test.index)
    for _, r in lab.iterrows():
        edge |= ((test["timestamp"] - r["start"]).abs() <= margin)
        edge |= ((test["timestamp"] - r["end"]).abs() <= margin)
    test = test[~edge].reset_index(drop=True)
    normal = (test["event"] == -1).values
    print(f"test rows after trimming: {len(test)} (normal: {normal.sum()})\n")

    def rule_flag(T):
        flag = np.zeros(len(test), dtype=bool)
        for col, floor in FLOORS.items():
            med = base[col].median()
            mad = 1.4826 * (base[col] - med).abs().median()
            flag |= ((test[col] - med) / max(mad, floor) > T).values
        return flag

    forest = IsolationForest(n_estimators=200, contamination=0.01, random_state=42)
    forest.fit(base[BASE + IOL])
    if_pred = (forest.predict(test[BASE + IOL]) == -1)

    dets = {}
    for T in (4, 6, 8):
        dets[f"rules{T}"] = rule_flag(T)
    dets["IF"] = if_pred
    for T in (4, 6, 8):
        dets[f"hyb{T}"] = rule_flag(T) | if_pred

    print(f"{'event':<12}{'kind':<6}" + "".join(f"{n:>11}" for n in dets))
    for idx, r in lab[lab["label"] != "normal"].iterrows():
        m = (test["event"] == idx).values
        if m.sum() == 0:
            continue
        cells = ""
        for pred in dets.values():
            rec = pred[m].mean() * 100
            star = "*" if max_run(pred[m]) >= 3 else " "
            cells += f"{rec:>9.0f}%{star}"
        print(f"{r['label']:<12}{r['kind']:<6}{cells}")
    cells = "".join(f"{pred[normal].mean() * 100:>9.1f}% " for pred in dets.values())
    print(f"{'false alarms':<18}{cells}\n")
