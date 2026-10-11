"""Live CPU prediction: every INTERVAL seconds, predict CPU 5 min ahead from the latest samples.

Usage:
  python ml/live_predictor.py --check    # verify live features match training features
  python ml/live_predictor.py --once     # one prediction, then exit
  python ml/live_predictor.py            # loop forever (Ctrl+C to stop)
"""
import argparse
import sqlite3
import time
from datetime import timedelta
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "sysinsight.db"
MODEL = ROOT / "ml" / "models" / "cpu_model.joblib"
HORIZON = 300
BLEND = 0.25         # weight on the model; 0.75 goes to 'CPU stays as now'
WINDOW = 150          # rows read per cycle (needs >= 61 contiguous)
INTERVAL = 10         # seconds between predictions
TS_FMT = "%Y-%m-%d %H:%M:%S"


def init_table(con):
    con.execute("""CREATE TABLE IF NOT EXISTS predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        made_at TEXT, target_time TEXT,
        predicted_cpu REAL, actual_cpu REAL, model TEXT)""")
    con.commit()


def latest_window(con, end=None):
    if end is None:
        sql = ("SELECT timestamp, cpu_percent, ram_percent, load_avg_1min FROM "
               "(SELECT * FROM samples ORDER BY id DESC LIMIT ?) ORDER BY timestamp")
        return pd.read_sql_query(sql, con, params=(WINDOW,))
    sql = ("SELECT timestamp, cpu_percent, ram_percent, load_avg_1min FROM "
           "(SELECT * FROM samples WHERE timestamp <= ? ORDER BY id DESC LIMIT ?) "
           "ORDER BY timestamp")
    return pd.read_sql_query(sql, con, params=(end, WINDOW))


def make_features(df):
    """Same 9 features as ml/cpu_dataset.py, computed for the newest row only."""
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.drop_duplicates("timestamp").reset_index(drop=True)
    gap = df["timestamp"].diff().dt.total_seconds().fillna(1) > 2
    seg = gap.cumsum()
    df = df[seg == seg.iloc[-1]]          # keep only the newest unbroken stretch
    if len(df) < 61:
        return None
    c = df["cpu_percent"].reset_index(drop=True)
    last = df.iloc[-1]
    return pd.DataFrame([{
        "timestamp": last["timestamp"],
        "cpu_percent": last["cpu_percent"],
        "ram_percent": last["ram_percent"],
        "load_avg_1min": last["load_avg_1min"],
        "cpu_lag5": c.iloc[-6],
        "cpu_lag30": c.iloc[-31],
        "cpu_lag60": c.iloc[-61],
        "cpu_mean30": c.iloc[-30:].mean(),
        "cpu_mean60": c.iloc[-60:].mean(),
        "cpu_std60": c.iloc[-60:].std(),
    }])


def backfill(con, latest_ts):
    """Fill actual_cpu for predictions whose target time has passed."""
    rows = con.execute("SELECT id, target_time FROM predictions "
                       "WHERE actual_cpu IS NULL AND target_time <= ?", (latest_ts,)).fetchall()
    n = 0
    for pid, tt in rows:
        r = con.execute("SELECT timestamp, cpu_percent FROM samples "
                        "WHERE timestamp >= ? ORDER BY timestamp LIMIT 1", (tt,)).fetchone()
        if r and (pd.Timestamp(r[0]) - pd.Timestamp(tt)).total_seconds() <= 3:
            con.execute("UPDATE predictions SET actual_cpu=? WHERE id=?", (r[1], pid))
            n += 1
    con.commit()
    return n


def step(con, model, features, name):
    feats = make_features(latest_window(con))
    if feats is None:
        print("not enough unbroken recent data yet (need 61+ seconds)")
        return
    made_at = feats["timestamp"].iloc[0]
    raw = float(model.predict(feats[features])[0])
    now = float(feats['cpu_percent'].iloc[0])
    pred = float(np.clip(BLEND * raw + (1 - BLEND) * now, 0, 100))
    made_str = made_at.strftime(TS_FMT)
    target_str = (made_at + timedelta(seconds=HORIZON)).strftime(TS_FMT)
    if not con.execute("SELECT 1 FROM predictions WHERE made_at=?", (made_str,)).fetchone():
        con.execute("INSERT INTO predictions (made_at, target_time, predicted_cpu, model) "
                    "VALUES (?,?,?,?)", (made_str, target_str, round(pred, 2), f"blend{int(BLEND*100)}_{name}"))
        con.commit()
    filled = backfill(con, made_str)
    print(f"{made_str}  now {feats['cpu_percent'].iloc[0]:.1f}%  ->  "
          f"predicted CPU at {target_str}: {pred:.1f}%   (actuals filled: {filled})")


def check(con, features):
    """Compare live feature code against the training dataset builder."""
    from cpu_dataset import build
    _, test = build(str(DB))
    row = test.iloc[100]
    live = make_features(latest_window(con, end=row["timestamp"].strftime(TS_FMT)))
    a = live[features].iloc[0].values.astype(float)
    b = row[features].values.astype(float)
    print("live features    :", np.round(a, 3))
    print("training features:", np.round(b, 3))
    print("features match   :", np.allclose(a, b))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--interval", type=int, default=INTERVAL)
    args = ap.parse_args()

    bundle = joblib.load(MODEL)
    model, features, name = bundle["model"], bundle["features"], bundle["name"]
    con = sqlite3.connect(DB, timeout=10)
    init_table(con)
    try:
        if args.check:
            check(con, features)
            return
        while True:
            step(con, model, features, name)
            if args.once:
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        con.close()


if __name__ == "__main__":
    main()
