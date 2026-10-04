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
test = df[(df["timestamp"] >= w0) & (df["timestamp"] <= w1)].copy().reset_index(drop=True)

test["label"] = "normal"
for _, row in labels.iterrows():
    m = (test["timestamp"] >= row["start"]) & (test["timestamp"] < row["end"])
    test.loc[m, "label"] = row["label"]

# Drop 3 seconds around every phase boundary (label noise)
margin = pd.Timedelta(seconds=3)
edge = pd.Series(False, index=test.index)
for _, row in labels.iterrows():
    edge |= ((test["timestamp"] - row["start"]).abs() <= margin)
    edge |= ((test["timestamp"] - row["end"]).abs() <= margin)
test = test[~edge].reset_index(drop=True)
test["is_anomaly"] = (test["label"] != "normal").astype(int)

IOL = []
for c in IO:
    for d in (train, test):
        d[c + "_log"] = np.log1p(d[c])
    IOL.append(c + "_log")

print(f"Training rows: {len(train)} | Test rows after trimming: {len(test)} "
      f"(normal: {(test['label'] == 'normal').sum()})\n")

# Isolation Forest on the log feature set
model = IsolationForest(n_estimators=200, contamination=0.01, random_state=42)
model.fit(train[BASE + IOL])
if_pred = (model.predict(test[BASE + IOL]) == -1).astype(int)

y = test["is_anomaly"].values
normal = (test["label"] == "normal").values

FLOORS = {"cpu_percent": 5.0, "ram_percent": 2.0, "load_avg_1min": 0.3,
          "disk_read_mb_s_log": 0.5, "disk_write_mb_s_log": 0.5}

def col_flag(col, T):
    med = train[col].median()
    mad = 1.4826 * (train[col] - med).abs().median()
    return ((test[col] - med) / max(mad, FLOORS[col]) > T).values

def caught(pred):
    return "  ".join(
        f"{lbl.split('_')[0]}={pred[(test['label'] == lbl).values].mean() * 100:.0f}%"
        for lbl in ["cpu_stress", "memory_stress", "disk_stress"])

def report(name, pred):
    pred = pred.astype(int)
    p = precision_score(y, pred, zero_division=0)
    r = recall_score(y, pred, zero_division=0)
    f = f1_score(y, pred, zero_division=0)
    print(f"{name:<26} P={p:.2f} R={r:.2f} F1={f:.2f} false_alarms={pred[normal].mean() * 100:4.1f}%  caught: {caught(pred)}")

print("Each rule on its own (T=8):")
for col in FLOORS:
    report(col, col_flag(col, 8))

print("\nIsolation Forest plus a narrow rule:")
report("IF alone", if_pred)
for T in (6, 8):
    report(f"IF + RAM rule (T={T})", np.maximum(if_pred, col_flag("ram_percent", T)))
    report(f"IF + RAM,CPU rule (T={T})", np.maximum(if_pred, col_flag("ram_percent", T) | col_flag("cpu_percent", T)))
