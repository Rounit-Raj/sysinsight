#!/usr/bin/env bash
# Subtle-anomaly scenarios. The collector must already be running.
OUT="${1:-data/labels_run3.csv}"
mkdir -p data "$HOME/stress_tmp"
[ -f "$OUT" ] || echo "start,end,label" > "$OUT"

run_phase() {
    label="$1"; secs="$2"; shift 2
    start=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$start] $label for ${secs}s"
    if [ "$#" -gt 0 ]; then "$@" > /dev/null 2>&1; else sleep "$secs"; fi
    end=$(date '+%Y-%m-%d %H:%M:%S')
    echo "$start,$end,$label" >> "$OUT"
}

run_phase normal 60
run_phase subtle_cpu 30 stress-ng --cpu 0 --cpu-load 20 --timeout 30s
run_phase normal 60
run_phase subtle_combo 30 bash -c 'stress-ng --cpu 0 --cpu-load 10 --vm 1 --vm-bytes 12% --timeout 30s & for i in $(seq 30); do dd if=/dev/zero of=$HOME/stress_tmp/w.bin bs=1M count=8 conv=fsync status=none; sleep 1; done; wait'
run_phase normal 60
run_phase net_burst 30 timeout 30 bash -c 'while true; do curl -sL -o /dev/null http://ipv4.download.thinkbroadband.com/100MB.zip; done'
run_phase normal 60

rm -rf "$HOME/stress_tmp"
echo "Done. Labels saved to $OUT"
