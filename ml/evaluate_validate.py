import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import precision_score, recall_score, f1_score

BASE = ["cpu_percent", "ram_percent", "load_avg_1min"]
IO = ["disk_read_mb_s", "disk_write_mb_s", "net_rx_kb_s", "net_tx_kb_s"]

readings = pd.read_csv("../data/readings.csv").drop_duplicates("timestamp")
io = pd.read_csv("../data/io.csv").drop_duplicates("timestamp")
readings["timestamp"] = pd.to_datetime(readings["timestamp"])
io["timestamp"] = pd.to_datetime(io["timestamp"])
df = readings.merge(io, on="timestamp").sort_values("timestamp").reset_index(drop=True)

IOL = []
for c in IO:
    df[c + "_log"] = np.log1p(df[c])
    IOL.append(c + "_log")
FEATS = BASE + IOL

def load_labels(path):
    l = pd.read_csv(path)
    l["start"] = pd.to_datetime(l["start"])
    l["end"] = pd.to_datetime(l["end"])
    return l

def window(labels):
    t = df[(df["timestamp"] >= labels["start"].min()) & (df["timestamp"] <= labels["end"].max())].copy()
    t = t.reset_index(drop=True)
    t["label"] = "normal"
    for _, r in labels.iterrows():
        t.loc[(t["timestamp"] >= r["start"]) & (t["timestamp"] < r["end"]), "label"] = r["label"]
    margin = pd.Timedelta(seconds=3)
    edge = pd.Series(False, index=t.index)
    for _, r in labels.iterrows():
        edge |= (t["timestamp"] - r["start"]).abs() <= margin
        edge |= (t["timestamp"] - r["end"]).abs() <= margin
    t = t[~edge].reset_index(drop=True)
    t["is_anomaly"] = (t["label"] != "normal").astype(int)
    return t

lab1 = load_labels("../data/labels.csv")
lab2 = load_labels("../data/labels_run2.csv")
run1, run2 = window(lab1), window(lab2)

train_a = df[df["timestamp"] < lab1["start"].min()]
train_b = pd.concat([train_a, run1[run1["label"] == "normal"]])

def detect(train, test, T):
    model = IsolationForest(n_estimators=200, contamination=0.01, random_state=42)
    model.fit(train[FEATS])
    if_pred = (model.predict(test[FEATS]) == -1).astype(int)
    med = train["ram_percent"].median()
    mad = 1.4826 * (train["ram_percent"] - med).abs().median()
    ram_pred = (((test["ram_percent"] - med) / max(mad, 2.0)) > T).astype(int).values
    return if_pred, np.maximum(if_pred, ram_pred)

def report(name, test, pred):
    y = test["is_anomaly"].values
    normal = (test["label"] == "normal").values
    p = precision_score(y, pred, zero_division=0)
    r = recall_score(y, pred, zero_division=0)
    f = f1_score(y, pred, zero_division=0)
    c = "  ".join(f"{l.split('_')[0]}={pred[(test['label'] == l).values].mean() * 100:.0f}%"
                  for l in ["cpu_stress", "memory_stress", "disk_stress"])
    print(f"{name:<34} P={p:.2f} R={r:.2f} F1={f:.2f} false_alarms={pred[normal].mean() * 100:4.1f}%  caught: {c}")

print(f"Train A rows: {len(train_a)} | Train B rows: {len(train_b)}")
print(f"Run 1 test rows: {len(run1)} | Run 2 test rows: {len(run2)}\n")

for tname, train in (("A", train_a), ("B", train_b)):
    for T in (6, 8):
        if_p, hyb = detect(train, run2, T)
        if T == 6:
            report(f"Run 2, train {tname}: IF alone", run2, if_p)
        report(f"Run 2, train {tname}: hybrid T={T}", run2, hyb)
    print()

if_p, hyb = detect(train_a, run1, 6)
report("Run 1 (reference): hybrid T=6", run1, hyb)
