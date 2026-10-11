"""Train CPU-prediction models (5 min ahead), compare them, save the best with joblib."""
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeRegressor

from cpu_dataset import build

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "docs" / "results"
MODELS = ROOT / "ml" / "models"


def split_xy(train, test):
    """Expects build() to return two DataFrames; target column starts with 'target'."""
    targets = [c for c in train.columns if c.startswith("target")]
    target = targets[0] if targets else train.columns[-1]
    feats = [c for c in train.columns if c not in (target, "timestamp", "segment")]
    return train[feats], train[target], test[feats], test[target], feats, target


def main():
    res = build()
    if not (len(res) == 2 and all(isinstance(r, pd.DataFrame) for r in res)):
        raise SystemExit(f"build() returned something unexpected: {[type(r) for r in res]}")
    X_tr, y_tr, X_te, y_te, feats, target = split_xy(*res)
    print(f"train {X_tr.shape}, test {X_te.shape}, target = {target}")
    print(f"features: {feats}")

    models = {
        "Always train mean": DummyRegressor(strategy="mean"),
        "Ridge regression": make_pipeline(StandardScaler(), Ridge(alpha=1.0)),
        "Decision Tree": DecisionTreeRegressor(max_depth=8, min_samples_leaf=20, random_state=42),
        "Random Forest": RandomForestRegressor(
            n_estimators=200, min_samples_leaf=10, n_jobs=-1, random_state=42
        ),
        "Gradient Boosting": GradientBoostingRegressor(
            n_estimators=200, max_depth=3, learning_rate=0.05, random_state=42
        ),
    }

    rows, fitted = [], {}
    for name, model in models.items():
        t0 = time.time()
        model.fit(X_tr, y_tr)
        fit_s = time.time() - t0
        pred = model.predict(X_te)
        row1 = X_te.iloc[[0]]
        model.predict(row1)
        times = []
        for _ in range(200):
            t1 = time.perf_counter()
            model.predict(row1)
            times.append(time.perf_counter() - t1)
        infer_ms = float(np.median(times) * 1000)
        rows.append({
            "model": name,
            "MAE": mean_absolute_error(y_te, pred),
            "RMSE": float(np.sqrt(mean_squared_error(y_te, pred))),
            "R2": r2_score(y_te, pred),
            "fit_seconds": fit_s,
            "infer_ms": infer_ms,
        })
        fitted[name] = model

    # Baseline: "CPU stays as now" (only if the current CPU is a feature)
    if "cpu_percent" in X_te.columns:
        pred = X_te["cpu_percent"].values
        rows.append({
            "model": "Baseline: CPU stays as now",
            "MAE": mean_absolute_error(y_te, pred),
            "RMSE": float(np.sqrt(mean_squared_error(y_te, pred))),
            "R2": r2_score(y_te, pred),
            "fit_seconds": 0.0,
            "infer_ms": 0.0,
        })

    table = pd.DataFrame(rows).sort_values("MAE").reset_index(drop=True).round(3)
    print("\n=== Model comparison (test set, lower MAE is better) ===")
    print(table.to_string(index=False))

    RESULTS.mkdir(parents=True, exist_ok=True)
    table.to_csv(RESULTS / "model_comparison.csv", index=False)
    header = "| " + " | ".join(table.columns) + " |"
    sep = "|" + "|".join(["---"] * len(table.columns)) + "|"
    body = ["| " + " | ".join(str(v) for v in r) + " |" for r in table.values]
    (RESULTS / "model_comparison.md").write_text("\n".join([header, sep] + body) + "\n")

    # Save the best real model (exclude the two baselines)
    candidates = table[~table["model"].str.contains("Baseline|Always")]
    best_name = candidates.iloc[0]["model"]
    best = fitted[best_name]
    MODELS.mkdir(parents=True, exist_ok=True)
    path = MODELS / "cpu_model.joblib"
    joblib.dump({"model": best, "features": feats, "target": target,
                 "name": best_name, "test_mae": float(candidates.iloc[0]["MAE"])}, path)

    # Load it back and check it predicts the same
    loaded = joblib.load(path)
    same = np.allclose(loaded["model"].predict(X_te), best.predict(X_te))
    print(f"\nSaved best model: {best_name} -> {path.relative_to(ROOT)}")
    print(f"Reload check (predictions identical): {same}")


if __name__ == "__main__":
    main()
