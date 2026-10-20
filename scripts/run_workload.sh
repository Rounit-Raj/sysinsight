#!/usr/bin/env bash
# Repeatable labelled workload for SysInsight.
# Usage: scripts/run_workload.sh <run_name> [net_url]
# The collector must be running. Writes data/labels_<run_name>.csv
set -u
RUN="${1:?usage: run_workload.sh <run_name> [net_url]}"
NET_URL="${2:-https://speed.hetzner.de/100MB.bin}"
OUT="data/labels_${RUN}.csv"
CALM=60     # seconds of calm before each event
EVENT=30    # seconds per event

ts() { date '+%Y-%m-%d %H:%M:%S'; }
cleanup() { pkill -P $$ 2>/dev/null; rm -f /tmp/sysinsight_drip; }
trap cleanup EXIT INT TERM

ev_cpu_heavy()  { stress-ng --cpu 0 --timeout ${EVENT}s -q; }
ev_ram_heavy()  { stress-ng --vm 1 --vm-bytes 40% --vm-keep --timeout ${EVENT}s -q; }
ev_disk_heavy() { stress-ng --hdd 1 --hdd-bytes 1g --temp-path /tmp --timeout ${EVENT}s -q; }
ev_net_burst()  { timeout ${EVENT} bash -c "while true; do curl -s -o /dev/null '$NET_URL'; done"; }
ev_light_cpu()  { stress-ng --cpu 1 --cpu-load 20 --timeout ${EVENT}s -q; }
ev_small_ram()  { stress-ng --vm 1 --vm-bytes 300M --vm-keep --timeout ${EVENT}s -q; }
ev_disk_drip()  { for i in $(seq 1 $EVENT); do dd if=/dev/zero of=/tmp/sysinsight_drip bs=100k count=1 oflag=dsync 2>/dev/null; sleep 1; done; }
ev_cpu_bursts() { for i in $(seq 1 $((EVENT/5))); do stress-ng --cpu 2 --timeout 2s -q; sleep 3; done; }

# label|kind|subtle  (fixed order = repeatable)
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
