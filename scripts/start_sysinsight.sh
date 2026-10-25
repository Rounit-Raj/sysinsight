#!/usr/bin/env bash
# Starts the whole SysInsight stack: collector, live detector, live predictor, dashboard.
# Usage: ./scripts/start_sysinsight.sh [--open]
#   --open  also opens the dashboard in your browser
# Stop everything with Ctrl+C.

set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
mkdir -p logs data

PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || PY=python3

# ---- build the collector (incremental, fast when nothing changed) ----
if [ ! -f build/CMakeCache.txt ]; then
  cmake -S . -B build -DCMAKE_BUILD_TYPE=Release || { echo "cmake configure failed"; exit 1; }
fi
cmake --build build -j || { echo "build failed"; exit 1; }

# ---- find the collector binary (override with: COLLECTOR=path ./scripts/start_sysinsight.sh) ----
COLLECTOR="${COLLECTOR:-$(find build -maxdepth 2 -type f -perm -u+x ! -name '*.so*' ! -name '*.a' ! -path '*CMakeFiles*' | head -n 1)}"
if [ -z "$COLLECTOR" ]; then
  echo "Could not find the collector binary in build/"
  exit 1
fi
echo "Collector binary: $COLLECTOR"

PIDS=()
NAMES=()

start() {
  local name="$1"; shift
  "$@" > "logs/$name.log" 2>&1 &
  PIDS+=($!)
  NAMES+=("$name")
  echo "  started $name (pid $!)  -> logs/$name.log"
}

cleanup() {
  trap - INT TERM EXIT
  echo
  echo "Stopping SysInsight..."
  for ((i=${#PIDS[@]}-1; i>=0; i--)); do
      kill -TERM "${PIDS[$i]}" 2>/dev/null
  done
  wait 2>/dev/null
  echo "Stopped."
}
trap cleanup INT TERM EXIT

echo "Starting SysInsight..."
start collector "./$COLLECTOR"
sleep 3   # let the collector write its first rows before the detector reads them
start detector  "$PY" ml/live_detector.py
start predictor "$PY" ml/live_predictor.py
start server    "$PY" dashboard/server.py

# ---- wait until the dashboard answers ----
for i in $(seq 1 20); do
  if curl -s -o /dev/null http://localhost:5000/api/health; then
      echo
      echo "Dashboard ready: http://localhost:5000"
      break
  fi
  sleep 1
done

if [ "${1:-}" = "--open" ]; then
  xdg-open http://localhost:5000 >/dev/null 2>&1 &
fi

echo "Press Ctrl+C to stop everything."

# ---- keep running, warn once if a component dies ----
declare -A WARNED
while true; do
  sleep 5
  for i in "${!PIDS[@]}"; do
      if ! kill -0 "${PIDS[$i]}" 2>/dev/null && [ -z "${WARNED[${NAMES[$i]}]:-}" ]; then
          echo "WARNING: ${NAMES[$i]} has stopped. See logs/${NAMES[$i]}.log"
          WARNED[${NAMES[$i]}]=1
      fi
  done
done
