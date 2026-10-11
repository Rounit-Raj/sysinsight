# Stress test parameters

How the labelled anomaly runs were generated. Label files live in data/ with columns: start,end,label,kind,subtle.

## stress-ng commands found in scripts/

```
scripts/run_stress_test.sh:17:run_phase cpu_stress 30 stress-ng --cpu 0 --timeout 30s
scripts/run_stress_test.sh:19:run_phase memory_stress 30 stress-ng --vm 1 --vm-bytes 40% --timeout 30s
scripts/run_stress_test.sh:21:run_phase disk_stress 30 stress-ng --hdd 2 --hdd-bytes 500m --temp-path "$HOME/stress_tmp" --timeout 30s
scripts/run_subtle_test.sh:27:    stress-ng --cpu 0 --timeout 3s -q
scripts/run_subtle_test.sh:33:run_event light_cpu  stress-ng --cpu 1 --cpu-load 20 --timeout 60s -q
scripts/run_subtle_test.sh:35:run_event small_ram  stress-ng --vm 1 --vm-bytes 4% --timeout 60s -q
```

## data/labels_run1.csv

```
start,end,label,kind,subtle
2026-10-04 21:48:48,2026-10-04 21:49:48,normal,normal,no
2026-10-04 21:49:48,2026-10-04 21:50:18,cpu_stress,cpu,no
2026-10-04 21:50:18,2026-10-04 21:51:18,normal,normal,no
2026-10-04 21:51:18,2026-10-04 21:51:49,memory_stress,ram,no
2026-10-04 21:51:49,2026-10-04 21:52:49,normal,normal,no
2026-10-04 21:52:49,2026-10-04 21:53:19,disk_stress,disk,no
2026-10-04 21:53:19,2026-10-04 21:54:19,normal,normal,no
```

## data/labels_run2.csv

```
start,end,label,kind,subtle
2026-10-04 22:45:09,2026-10-04 22:46:09,normal,normal,no
2026-10-04 22:46:09,2026-10-04 22:46:39,cpu_stress,cpu,no
2026-10-04 22:46:39,2026-10-04 22:47:39,normal,normal,no
2026-10-04 22:47:39,2026-10-04 22:48:09,memory_stress,ram,no
2026-10-04 22:48:09,2026-10-04 22:49:09,normal,normal,no
2026-10-04 22:49:09,2026-10-04 22:49:39,disk_stress,disk,no
2026-10-04 22:49:39,2026-10-04 22:50:39,normal,normal,no
```

## data/labels_run3_std.csv

```
start,end,label,kind,subtle
2026-10-11 22:04:54,2026-10-11 22:05:54,light_cpu,cpu,yes
2026-10-11 22:05:54,2026-10-11 22:06:54,normal,normal,no
2026-10-11 22:06:54,2026-10-11 22:07:54,small_ram,ram,yes
2026-10-11 22:07:54,2026-10-11 22:08:54,normal,normal,no
2026-10-11 22:08:54,2026-10-11 22:09:55,disk_drip,disk,yes
2026-10-11 22:09:55,2026-10-11 22:10:55,normal,normal,no
2026-10-11 22:10:55,2026-10-11 22:11:24,cpu_bursts,cpu,yes
```

## data/labels_net_run.csv

```
start,end,label,kind,subtle
2026-10-09 22:38:32,2026-10-09 22:39:32,normal,normal,no
2026-10-09 22:39:32,2026-10-09 22:40:02,net_burst,net,no
2026-10-09 22:40:02,2026-10-09 22:41:02,normal,normal,no
```

## Summary of events

Calm periods of 60 s separate every event. Times are in the label CSVs above.

| Run | Label file | Event | Duration | Command / method |
|---|---|---|---|---|
| 1, 2 | labels_run1.csv, labels_run2.csv | cpu_stress | 30 s | `stress-ng --cpu 0 --timeout 30s` |
| 1, 2 | same | memory_stress | 30 s | `stress-ng --vm 1 --vm-bytes 40% --timeout 30s` |
| 1, 2 | same | disk_stress | 30 s | `stress-ng --hdd 2 --hdd-bytes 500m --temp-path "$HOME/stress_tmp" --timeout 30s` |
| 3 | labels_run3_std.csv | light_cpu (subtle) | 60 s | `stress-ng --cpu 1 --cpu-load 20 --timeout 60s -q` |
| 3 | same | small_ram (subtle) | 60 s | `stress-ng --vm 1 --vm-bytes 4% --timeout 60s -q` |
| 3 | same | disk_drip (subtle) | 60 s | see scripts/run_subtle_test.sh |
| 3 | same | cpu_bursts (subtle) | about 30 s | see scripts/run_subtle_test.sh |
| net run | labels_net_run.csv | net_burst | 30 s | `scripts/run_net_test.sh` (looped curl download for 30 s) |

## scripts/run_subtle_test.sh (copy)

```bash
#!/usr/bin/env bash
cd "$(dirname "$0")/.."
OUT=data/labels_run3.csv
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
```

## scripts/run_net_test.sh (copy)

The script tries three download URLs, uses the first one that delivers more than 1 MB in 5 s, then loops `curl` downloads of that file for the 30 s burst.

```bash
#!/usr/bin/env bash
# Network-burst scenario. The collector must already be running.
OUT="data/labels_net_run.csv"
URLS=(
  "http://ipv4.download.thinkbroadband.com/100MB.zip"
  "https://ash-speed.hetzner.com/100MB.bin"
  "https://speed.cloudflare.com/__down?bytes=100000000"
)

URL=""
for u in "${URLS[@]}"; do
    bytes=$(curl -sL -o /dev/null --max-time 5 -w '%{size_download}' "$u")
    if [ "${bytes:-0}" -gt 1000000 ]; then URL="$u"; break; fi
done
if [ -z "$URL" ]; then
    echo "No download URL worked from this connection. Nothing was recorded."
    exit 1
fi
echo "Using: $URL"

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
run_phase net_burst 30 timeout 30 bash -c "while true; do curl -sL -o /dev/null '$URL'; done"
run_phase normal 60
echo "Done. Labels saved to $OUT"
```
