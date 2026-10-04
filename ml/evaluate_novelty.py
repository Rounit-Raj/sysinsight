import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import precision_score, recall_score, f1_score

BASE = ["cpu_percent", "ram_percent", "load_avg_1min"]
IO = ["disk_read_mb_s", "disk_write_mb_s", "net_rx_kb_s", "net_tx_kb_s"]

readings = pd.read_csv("../data/readings.csv").drop_duplicates("timestamp")
io = pd.read_csv("../data/io.csv").drop_duplicates("timestamp")
labels = pd.read_csv("../data/labels.csv")

readings["timestamp"] = pd.to_datetime(readings["timestamp"])
io["timestamp"] = pd.to_datetime(io["timestamp"])
labels["start"] = pd.to_datetime(labels["start"])
labels["end"] = pd.to_datetime(labels["end"])

df = readings.merge(io, on="timestamp").sort_values("timestamp").reset_index(drop=True)
w0, w1 = labels["start"].min(), labels["end"].max()

train = df[df["timestamp"] < w0].copy()
test = df[(df["timestamp"] >= w0) & (df["timestamp"] <= w1)].copy()

test["label"] = "normal"
for _, row in labels.iterrows():
    m = (test["timestamp"] >= row["start"]) & (test["timestamp"] < row["end"])
    test.loc[m, "label"] = row["label"]
test["is_anomaly"] = (test["label"] != "normal").astype(int)

IOL = []
for c in IO:
    for d in (train, test):
        d[c + "_log"] = np.log1p(d[c])
    IOL.append(c + "_log")

print(f"Training rows (before test window): {len(train)}")
print(f"Test rows: {len(test)}  (normal: {(test['label'] == 'normal').sum()})")
print()

SETS = {
    "CPU+RAM+load": BASE,
    "with disk+network": BASE + IO,
    "with log disk+net": BASE + IOL,
}

for cont in (0.005, 0.01, 0.02):
    for name, feats in SETS.items():
        model = IsolationForest(n_estimators=200, contamination=cont, random_state=42)
        model.fit(train[feats])
        pred = (model.predict(test[feats]) == -1).astype(int)
        y = test["is_anomaly"]
        p = precision_score(y, pred, zero_division=0)
        r = recall_score(y, pred, zero_division=0)
        f = f1_score(y, pred, zero_division=0)
        fa = pred[(test["label"] == "normal").values].mean() * 100
        print(f"{name:<18} cont={cont:<5} precision={p:.2f} recall={r:.2f} f1={f:.2f} false_alarms={fa:.1f}%")
        for lbl in ["cpu_stress", "memory_stress", "disk_stress"]:
            sel = (test["label"] == lbl).values
            print(f"    caught {lbl:<14} {pred[sel].mean() * 100:5.1f}%")
    print()
