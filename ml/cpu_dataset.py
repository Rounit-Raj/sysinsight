import sqlite3
import pandas as pd

HORIZON = 300  # predict CPU this many seconds ahead (5 minutes)
FEATURES = ["cpu_percent", "ram_percent", "load_avg_1min",
            "cpu_lag5", "cpu_lag30", "cpu_lag60",
            "cpu_mean30", "cpu_mean60", "cpu_std60"]


def build(db_path="data/sysinsight.db"):
    con = sqlite3.connect(db_path)
    df = pd.read_sql_query(
        "SELECT timestamp, cpu_percent, ram_percent, load_avg_1min "
        "FROM samples ORDER BY timestamp", con)
    con.close()

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.drop_duplicates("timestamp").reset_index(drop=True)

    # a gap of more than 2 s means the collector was stopped; start a new segment
    gap = df["timestamp"].diff().dt.total_seconds().fillna(1) > 2
    df["segment"] = gap.cumsum()

    parts = []
    for _, g in df.groupby("segment"):
        g = g.copy()
        g["cpu_lag5"] = g["cpu_percent"].shift(5)
        g["cpu_lag30"] = g["cpu_percent"].shift(30)
        g["cpu_lag60"] = g["cpu_percent"].shift(60)
        g["cpu_mean30"] = g["cpu_percent"].rolling(30).mean()
        g["cpu_mean60"] = g["cpu_percent"].rolling(60).mean()
        g["cpu_std60"] = g["cpu_percent"].rolling(60).std()
        g["target"] = g["cpu_percent"].shift(-HORIZON)
        parts.append(g.dropna())

    data = pd.concat(parts).reset_index(drop=True)

    # chronological split: first 80% train, last 20% test,
    # with a HORIZON-sized hole between them so no target leaks across
    cut = int(len(data) * 0.8)
    train = data.iloc[:cut - HORIZON]
    test = data.iloc[cut:]
    return train, test


if __name__ == "__main__":
    train, test = build()
    print("train rows:", len(train), " test rows:", len(test))
    print("train period:", train["timestamp"].min(), "->", train["timestamp"].max())
    print("test period: ", test["timestamp"].min(), "->", test["timestamp"].max())

    # reference scores any real model must beat (MAE, in CPU % points)
    mean_pred = train["target"].mean()
    print("baseline MAE, always predict train mean:",
          round((test["target"] - mean_pred).abs().mean(), 3))
    print("baseline MAE, 'CPU stays as it is now':",
          round((test["target"] - test["cpu_percent"]).abs().mean(), 3))
