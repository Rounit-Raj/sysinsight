import time
import pandas as pd
from sklearn.ensemble import IsolationForest
from rich.console import Console
from rich.table import Table
from rich.live import Live

console = Console()

REQUIRED_COLUMNS = ["timestamp", "cpu_percent", "ram_percent", "load_avg_1min"]

def get_latest_data():
    try:
        df = pd.read_csv("../data/readings.csv")
    except (FileNotFoundError, pd.errors.EmptyDataError):
        return None, "Waiting for data... (collector not running yet?)"

    if df.empty:
        return None, "CSV is empty — waiting for readings..."

    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        return None, f"Missing expected columns: {missing}"

    if len(df) < 10:
        return None, f"Only {len(df)} readings so far — need at least 10 for anomaly detection"

    features = df[["cpu_percent", "ram_percent", "load_avg_1min"]]
    model = IsolationForest(contamination=0.05, random_state=42)
    df["anomaly"] = model.fit_predict(features)
    return df, None

def build_table():
    df, error = get_latest_data()

    if error:
        table = Table(title="SysInsight — Live Monitor")
        table.add_column("Status")
        table.add_row(f"[yellow]{error}[/yellow]")
        return table

    recent = df.tail(10)
    total_anomalies = (df["anomaly"] == -1).sum()

    table = Table(
        title=f"SysInsight — Live Monitor  |  Total anomalies so far: [red]{total_anomalies}[/red]",
        style="bold cyan"
    )

    table.add_column("Timestamp", style="bright_black")
    table.add_column("CPU %", style="blue")
    table.add_column("RAM %", style="cyan")
    table.add_column("Load Avg", style="yellow")
    table.add_column("Status", style="green")

    for _, row in recent.iterrows():
        status = "[red]ANOMALY[/red]" if row["anomaly"] == -1 else "[green]OK[/green]"
        table.add_row(
            str(row["timestamp"]),
            f"{row['cpu_percent']:.2f}",
            f"{row['ram_percent']:.2f}",
            f"{row['load_avg_1min']:.2f}",
            status
        )
    return table

with Live(build_table(), refresh_per_second=1, console=console) as live:
    while True:
        time.sleep(2)
        live.update(build_table())
