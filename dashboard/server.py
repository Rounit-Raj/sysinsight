import sqlite3
from pathlib import Path

from flask import Flask, jsonify, request

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


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
