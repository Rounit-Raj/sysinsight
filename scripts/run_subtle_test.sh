#!/usr/bin/env bash
cd "$(dirname "$0")/.."
OUT="${1:-data/labels_run3.csv}"
echo "start,end,type" > "$OUT"

ts() { date '+%F %T'; }
calm() { echo "calm for $1 s"; sleep "$1"; }
run_event() {
  local type=$1; shift
  local s; s=$(ts)
  echo "start: $type"
  "$@"
  local e; e=$(ts)
  echo "$s,$e,$type" >> "$OUT"
}

disk_drip() {
  for i in $(seq 60); do
    dd if=/dev/zero of=/tmp/sysinsight_subtle.bin bs=1M count=2 conv=fsync status=none
    sleep 1
  done
  rm -f /tmp/sysinsight_subtle.bin
}

cpu_bursts() {
  for i in 1 2 3; do
    stress-ng --cpu 0 --timeout 3s -q
    if [ "$i" -lt 3 ]; then sleep 10; fi
  done
}

calm 60
run_event light_cpu  stress-ng --cpu 1 --cpu-load 20 --timeout 60s -q
calm 60
run_event small_ram  stress-ng --vm 1 --vm-bytes 4% --timeout 60s -q
calm 60
run_event disk_drip  disk_drip
calm 60
run_event cpu_bursts cpu_bursts
calm 60
echo "run 3 finished"
