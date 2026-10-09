#!/usr/bin/env bash
# Network-burst scenario. The collector must already be running.
OUT="data/labels_run3_net.csv"
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
