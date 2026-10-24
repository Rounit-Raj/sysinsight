#!/usr/bin/env bash
# usage: load_net.sh [seconds]  -> sustained real downloads, prints bytes received
D=${1:-30}
end=$((SECONDS+D)); total=0
while [ $SECONDS -lt $end ]; do
  left=$((end-SECONDS))
  n=$(timeout "$left" curl -s -o /dev/null -w '%{size_download}' "https://speed.cloudflare.com/__down?bytes=50000000")
  total=$((total+${n:-0}))
done
echo "load_net: downloaded $total bytes" >&2
[ "$total" -gt 1000000 ] || { echo "load_net: NO real download happened" >&2; exit 1; }
