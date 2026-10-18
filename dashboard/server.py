import sqlite3
from pathlib import Path
import csv
import os
from flask import Flask, jsonify, request, send_from_directory

from flask import Flask, jsonify, request, send_from_directory

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "sysinsight.db"

app = Flask(__name__)


def query(sql, params=()):
    # read-only connection, so the API can never disturb the collector's writes
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=5)
    con.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in con.execute(sql, params).fetchall()]
    finally:
        con.close()


@app.after_request
def add_cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


@app.route("/api/health")
def health():
    n = query("SELECT COUNT(*) AS n FROM samples")[0]["n"]
    return jsonify(status="ok", samples=n)


@app.route("/api/latest")
def latest():
    rows = query("SELECT * FROM samples ORDER BY id DESC LIMIT 1")
    return jsonify(rows[0] if rows else None)


@app.route("/api/samples")
def samples():
    minutes = request.args.get("minutes", default=5, type=int)
    minutes = max(1, min(minutes, 120))
    rows = query("SELECT * FROM samples ORDER BY id DESC LIMIT ?", (minutes * 60,))
    rows.reverse()  # oldest first, ready for charting
    return jsonify(rows)


@app.route("/api/alerts")
def alerts():
    limit = request.args.get("limit", default=20, type=int)
    limit = max(1, min(limit, 200))
    return jsonify(query("SELECT * FROM alerts ORDER BY rowid DESC LIMIT ?", (limit,)))


@app.route("/api/predictions/latest")
def prediction_latest():
    rows = query("SELECT * FROM predictions ORDER BY made_at DESC LIMIT 1")
    return jsonify(rows[0] if rows else None)


STATIC_DIR = ROOT / "dashboard" / "static"


@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")

PROCESSES_CSV = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "data", "processes.csv"
)


def read_latest_processes(limit=5):
    path = os.path.abspath(PROCESSES_CSV)
    with open(path, "rb") as f:
        header = f.readline().decode().strip().split(",")
        f.seek(0, os.SEEK_END)
        size = f.tell()
        f.seek(max(size - 65536, 0))
        tail = f.read().decode(errors="ignore").splitlines()
    if size > 65536:
        tail = tail[1:]  # first line of the chunk may be cut in half
    rows = [r for r in csv.reader(tail) if len(r) == len(header) and r != header]
    if not rows:
        return header, None, []

    time_idx = next((i for i, c in enumerate(header) if "time" in c.lower()), 0)
    cpu_idx = next((i for i, c in enumerate(header) if "cpu" in c.lower()), None)

    last_stamp = rows[-1][time_idx]
    latest = [r for r in rows if r[time_idx] == last_stamp]
    if cpu_idx is not None:
        def cpu_value(r):
            try:
                return float(r[cpu_idx])
            except ValueError:
                return 0.0
        latest.sort(key=cpu_value, reverse=True)
    latest = latest[:limit]
    return header, last_stamp, [dict(zip(header, r)) for r in latest]


@app.route("/api/processes/latest")
def api_processes_latest():
    try:
        header, stamp, rows = read_latest_processes()
    except FileNotFoundError:
        return jsonify({"error": "processes.csv not found"}), 404
    return jsonify({"timestamp": stamp, "columns": header, "rows": rows})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
