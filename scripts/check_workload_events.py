import sqlite3, csv, sys

labels_path = sys.argv[1] if len(sys.argv) > 1 else "data/labels_wl_run2.csv"
db = sqlite3.connect("data/sysinsight.db")
labels = list(csv.DictReader(open(labels_path)))

def num_cols(table):
    info = db.execute(f"PRAGMA table_info({table})").fetchall()
    return [r[1] for r in info
            if r[2].upper() in ("REAL", "INTEGER", "FLOAT", "DOUBLE") and r[1] != "id"]

def window_means(table, cols, start, end):
    sel = ", ".join(f"AVG({c})" for c in cols)
    row = db.execute(
        f"SELECT COUNT(*), {sel} FROM {table} WHERE timestamp >= ? AND timestamp <= ?",
        (start, end)).fetchone()
    return row[0], row[1:]

for table in ("samples", "io"):
    cols = num_cols(table)
    if not cols:
        print(f"[{table}] no numeric columns found, skipping")
        continue
    # baseline = average over all normal windows
    base_sum = [0.0] * len(cols)
    base_n = 0
    for r in labels:
        if r["kind"] == "normal":
            n, m = window_means(table, cols, r["start"], r["end"])
            if n:
                for i, v in enumerate(m):
                    base_sum[i] += (v or 0) * n
                base_n += n
    base = [s / base_n if base_n else 0 for s in base_sum]
    print(f"\n=== {table} (calm baseline from {base_n} rows) ===")
    print("columns:", ", ".join(cols))
    print("calm   :", "  ".join(f"{v:.2f}" for v in base))
    for r in labels:
        if r["kind"] == "normal":
            continue
        n, m = window_means(table, cols, r["start"], r["end"])
        vals = "  ".join(f"{(v or 0):.2f}" for v in m)
        print(f"{r['label']:<11} n={n:<3}: {vals}")
