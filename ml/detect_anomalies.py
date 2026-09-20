import pandas as pd
from sklearn.ensemble import IsolationForest

# Load the CSV from the C++ collector
df = pd.read_csv("../data/readings.csv")

# Selection of numeric columns to feed to the model
features = df[["cpu_percent", "ram_percent", "load_avg_1min"]]

# Isolation forest will be trained on this data
model = IsolationForest(contamination=0.05, random_state=42)
df["anomaly"] = model.fit_predict(features)

# -1 = anomaly, 1 = normal
anomalies = df[df["anomaly"] == -1]

print(f"Total rows: {len(df)}")
print(f"Anomalies detected: {len(anomalies)}")
print(anomalies)
