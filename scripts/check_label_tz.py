import glob
import sqlite3
import pandas as pd

con = sqlite3.connect("data/sysinsight.db")
s = pd.read_sql_query("SELECT timestamp FROM samples", con)
s["ts"] = pd.to_datetime(s["timestamp"])
print("samples:", len(s), "rows")
print("  first:", s["ts"].min(), "| last:", s["ts"].max())
print()

for f in sorted(glob.glob("data/labels*.csv")):
    if "backup" in f:
        continue
    df = pd.read_csv(f)
    start = pd.to_datetime(df["start"])
    end = pd.to_datetime(df["end"])
    lo, hi = start.min(), end.max()
    inside = ((s["ts"] >= lo) & (s["ts"] <= hi)).sum()
    expected = int((hi - lo).total_seconds()) + 1
    print(f)
    print("  raw first start:", df["start"].iloc[0], "| raw last end:", df["end"].iloc[-1])
    print("  span:", lo, "->", hi)
    print("  samples inside span:", inside, "of ~", expected, "expected")
    print()
