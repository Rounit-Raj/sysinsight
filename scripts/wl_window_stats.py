import sqlite3
import sys
import pandas as pd

labels_file = sys.argv[1]
lab = pd.read_csv(labels_file)

con = sqlite3.connect("data/sysinsight.db")
s = pd.read_sql("SELECT * FROM samples", con)
io = pd.read_sql("SELECT * FROM io", con)
con.close()

df = pd.merge(s, io, on="timestamp", suffixes=("", "_io"))
df["timestamp"] = pd.to_datetime(df["timestamp"])
cols = [c for c in df.columns if c != "timestamp" and not c.startswith("id")
        and pd.api.types.is_numeric_dtype(df[c])]

rows = []
for _, r in lab.iterrows():
    w = df[(df["timestamp"] >= pd.Timestamp(r["start"])) & (df["timestamp"] <= pd.Timestamp(r["end"]))]
    row = {"label": r["label"], "n": len(w)}
    for c in cols:
        row[c] = round(w[c].max(), 2) if len(w) else None
    rows.append(row)

print("max per window")
print(pd.DataFrame(rows).to_string(index=False))
