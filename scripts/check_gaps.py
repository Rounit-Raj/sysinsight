import sqlite3
from datetime import datetime
from collections import Counter

con = sqlite3.connect("data/sysinsight.db")
tables = [r[0] for r in con.execute("select name from sqlite_master where type='table'")]

for t in tables:
    cols = [r[1] for r in con.execute(f"pragma table_info({t})")]
    if "timestamp" not in cols:
        continue
    rows = con.execute(
        f"select * from (select * from {t} order by timestamp desc limit 3600) order by timestamp"
    ).fetchall()
    ts = [datetime.fromisoformat(r[cols.index("timestamp")]) for r in rows]
    gaps = [((b - a).total_seconds(), a) for a, b in zip(ts, ts[1:])]
    big = [g for g in gaps if g[0] > 1.5]
    print(f"\n== {t}: {len(rows)} rows, {ts[0]} -> {ts[-1]}")
    print("gaps > 1.5 s:", len(big), "| largest:", max((g[0] for g in gaps), default=0), "s")
    print("gap size counts:", dict(Counter(int(g[0]) for g in big)))
    for g in big[-5:]:
        print("  gap of", g[0], "s after", g[1])
    for c in cols:
        if c in ("id", "timestamp"):
            continue
        idx = cols.index(c)
        nulls = sum(1 for r in rows if r[idx] is None)
        zeros = sum(1 for r in rows if r[idx] == 0)
        print(f"  {c}: NULL={nulls}, zero={zeros}")
