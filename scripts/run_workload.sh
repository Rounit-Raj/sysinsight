#!/usr/bin/env bash
# Repeatable labelled workload for SysInsight.
# Usage: scripts/run_workload.sh <run_name> [net_url]
# The collector must be running. Writes data/labels_<run_name>.csv
set -u
RUN="${1:?usage: run_workload.sh <run_name> [net_url]}"
NET_URL="${2:-}"
OUT="data/labels_${RUN}.csv"
CALM=60
EVENT=30
DISK_DIR="$HOME/sysinsight_disk"
STRESS_DIR="$HOME/stress_tmp"

URLS=(
  "http://ipv4.download.thinkbroadband.com/100MB.zip"
  "https://ash-speed.hetzner.com/100MB.bin"
  "https://speed.cloudflare.com/__down?bytes=100000000"
  "https://proof.ovh.net/files/100Mb.dat"
)

ts() { date '+%Y-%m-%d %H:%M:%S'; }
cleanup() { pkill -P $$ 2>/dev/null; rm -f "$DISK_DIR/drip"; rm -rf "$STRESS_DIR"; }
trap cleanup EXIT INT TERM

mkdir -p data "$DISK_DIR" "$STRESS_DIR"

if ! pgrep -x collector > /dev/null; then
  echo "The collector is not running. Start it first, then run this script again."
  exit 1
fi

if [ -z "$NET_URL" ]; then
  for u in "${URLS[@]}"; do
    bytes=$(curl -sL -o /dev/null --max-time 5 -w '%{size_download}' "$u")
    if [ "${bytes:-0}" -gt 1000000 ]; then NET_URL="$u"; break; fi
  done
fi
if [ -z "$NET_URL" ]; then
  echo "No download URL worked from this connection. Nothing was recorded."
  exit 1
fi
echo "Net URL: $NET_URL"

fs=$(df -T "$STRESS_DIR" | awk 'NR==2{print $2}')
if [ "$fs" = "tmpfs" ]; then
  echo "$STRESS_DIR is on tmpfs, so disk events would not hit the disk. Aborting."
  exit 1
fi

ev_cpu_heavy()  { stress-ng --cpu 0 --timeout ${EVENT}s -q; }
ev_ram_heavy()  { stress-ng --vm 1 --vm-bytes 40% --vm-keep --timeout ${EVENT}s -q; }
ev_disk_heavy() { stress-ng --hdd 2 --hdd-bytes 500m --temp-path "$STRESS_DIR" --timeout ${EVENT}s -q; }
ev_net_burst()  { timeout ${EVENT} bash -c "while true; do curl -sL -o /dev/null '$NET_URL'; done"; }
ev_light_cpu()  { stress-ng --cpu 1 --cpu-load 20 --timeout ${EVENT}s -q; }
ev_small_ram()  { stress-ng --vm 1 --vm-bytes 300M --vm-keep --timeout ${EVENT}s -q; }
ev_disk_drip()  { for i in $(seq 1 $EVENT); do dd if=/dev/zero of="$DISK_DIR/drip" bs=100k count=1 oflag=dsync 2>/dev/null; sleep 1; done; }
ev_cpu_bursts() { for i in $(seq 1 $((EVENT/5))); do stress-ng --cpu 2 --timeout 2s -q; sleep 3; done; }

EVENTS="cpu_heavy|cpu|no
ram_heavy|ram|no
disk_heavy|disk|no
net_burst|net|no
light_cpu|cpu|yes
small_ram|ram|yes
disk_drip|disk|yes
cpu_bursts|cpu|yes"

echo "start,end,label,kind,subtle" > "$OUT"
while IFS='|' read -r label kind subtle; do
  s=$(ts); echo "[$s] calm ${CALM}s"; sleep $CALM; e=$(ts)
  echo "$s,$e,normal,normal,no" >> "$OUT"
  s=$(ts); echo "[$s] event: $label"; "ev_$label"; e=$(ts)
  echo "$s,$e,$label,$kind,$subtle" >> "$OUT"
done <<< "$EVENTS"
s=$(ts); echo "[$s] final calm ${CALM}s"; sleep $CALM; e=$(ts)
echo "$s,$e,normal,normal,no" >> "$OUT"
echo "Done. Labels: $OUT"
