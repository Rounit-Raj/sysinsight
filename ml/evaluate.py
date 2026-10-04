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

# Keep only the labelled recording window
df = readings.merge(io, on="timestamp")
df = df[(df["timestamp"] >= labels["start"].min()) & (df["timestamp"] <= labels["end"].max())].copy()

df["label"] = "normal"
for _, row in labels.iterrows():
    mask = (df["timestamp"] >= row["start"]) & (df["timestamp"] < row["end"])
    df.loc[mask, "label"] = row["label"]
df["is_anomaly"] = (df["label"] != "normal").astype(int)

print("Rows in labelled window:", len(df))
print(df["label"].value_counts().to_string())
print()

import numpy as np

df = df.sort_values("timestamp").reset_index(drop=True)

IOL = []
for c in IO:
    df[c + "_log"] = np.log1p(df[c])
    IOL.append(c + "_log")

ALLF = BASE + IOL
for c in ALLF:
    df[c + "_m5"] = df[c].rolling(5, min_periods=1).mean()
    df[c + "_s5"] = df[c].rolling(5, min_periods=1).std().fillna(0)

SETS = {
    "CPU+RAM+load": BASE,
    "with disk+network": BASE + IO,
    "smoothed base": [c + "_m5" for c in BASE] + [c + "_s5" for c in BASE],
    "smoothed all": [c + "_m5" for c in ALLF] + [c + "_s5" for c in ALLF],
}

def evaluate(name, features, contamination):
    model = IsolationForest(n_estimators=200, contamination=contamination, random_state=42)
    pred = (model.fit_predict(df[features]) == -1).astype(int)
    p = precision_score(df["is_anomaly"], pred, zero_division=0)
    r = recall_score(df["is_anomaly"], pred, zero_division=0)
    f = f1_score(df["is_anomaly"], pred, zero_division=0)
    print(f"{name:<18} contamination={contamination:<5} precision={p:.2f} recall={r:.2f} f1={f:.2f}")
    for lbl in ["cpu_stress", "memory_stress", "disk_stress"]:
        sel = df["label"] == lbl
        if sel.any():
            print(f"    caught {lbl:<14} {pred[sel.values].mean() * 100:5.1f}% of seconds")

for contamination in (0.1, 0.2):
    for name, feats in SETS.items():
        evaluate(name, feats, contamination)
    print()
