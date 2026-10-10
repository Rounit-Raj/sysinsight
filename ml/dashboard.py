import sqlite3
import time
from pathlib import Path

import pandas as pd
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "data" / "readings.csv"
DB_PATH = ROOT / "data" / "sysinsight.db"

REQUIRED_COLUMNS = ["timestamp", "cpu_percent", "ram_percent", "load_avg_1min"]
ALERT_ROWS = 8

console = Console()


def read_stats():
    try:
        df = pd.read_csv(CSV_PATH)
    except (FileNotFoundError, pd.errors.EmptyDataError):
        return None, "Waiting for data... (collector not running yet?)"

    if df.empty:
        return None, "CSV is empty, waiting for readings..."

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        return None, f"Missing expected columns: {missing}"

    return df.tail(10), None


def read_alerts():
    try:
        con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=1)
        total = con.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
        rows = con.execute(
            "SELECT timestamp, severity, message FROM alerts ORDER BY id DESC LIMIT ?",
            (ALERT_ROWS,),
        ).fetchall()
        con.close()
        return total, rows, None
    except sqlite3.Error as e:
        return 0, [], f"Alert store unavailable: {e}"


def build_stats_panel():
    recent, error = read_stats()
    if error:
        body = Text(error, style="yellow")
    else:
        table = Table(header_style="bold red", border_style="red", expand=True)
        table.add_column("Timestamp", style="bright_black")
        table.add_column("CPU %", style="white", justify="right")
        table.add_column("RAM %", style="white", justify="right")
        table.add_column("Load Avg", style="white", justify="right")
        for _, row in recent.iterrows():
            table.add_row(
                str(row["timestamp"]),
                f"{row['cpu_percent']:.2f}",
                f"{row['ram_percent']:.2f}",
                f"{row['load_avg_1min']:.2f}",
            )
        body = table
    return Panel(body, title="[bold red]SYSINSIGHT // LIVE MONITOR[/bold red]",
                 border_style="red")


def build_alerts_panel():
    total, rows, error = read_alerts()
    if error:
        body = Text(error, style="yellow")
    elif not rows:
        body = Text("No alerts recorded.", style="bright_black")
    else:
        table = Table(header_style="bold red", border_style="red", expand=True)
        table.add_column("Timestamp", style="bright_black", no_wrap=True)
        table.add_column("Severity", no_wrap=True)
        table.add_column("Message", style="white")
        for ts, sev, msg in rows:
            sev_text = (sev or "?").upper()
            sev_style = "bold yellow" if sev_text == "LOW" else "bold red"
            table.add_row(str(ts), Text(sev_text, style=sev_style), Text(str(msg)))
        body = table
    return Panel(
        body,
        title=f"[bold red]SHADOW ACTIVITY LOG[/bold red]  |  total alerts: [red]{total}[/red]",
        border_style="red",
    )


def build_view():
    return Group(build_stats_panel(), build_alerts_panel())


if __name__ == "__main__":
    try:
        with Live(build_view(), refresh_per_second=1, console=console) as live:
            while True:
                time.sleep(2)
                live.update(build_view())
    except KeyboardInterrupt:
        pass
