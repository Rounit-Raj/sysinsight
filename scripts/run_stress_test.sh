#!/usr/bin/env bash
# Runs labelled stress scenarios. The collector must already be running.
OUT="data/labels.csv"
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
run_phase cpu_stress 30 stress-ng --cpu 0 --timeout 30s
run_phase normal 60
run_phase memory_stress 30 stress-ng --vm 1 --vm-bytes 40% --timeout 30s
run_phase normal 60
run_phase disk_stress 30 stress-ng --hdd 2 --hdd-bytes 500m --temp-path "$HOME/stress_tmp" --timeout 30s
run_phase normal 60

rm -rf "$HOME/stress_tmp"
echo "Done. Labels saved to $OUT"
