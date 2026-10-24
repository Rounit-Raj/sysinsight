#!/usr/bin/env bash
# usage: load_disk.sh [seconds]  -> sustained real disk writes (O_DIRECT + fsync)
D=${1:-30}
F="$(dirname "$0")/../data/.disk_load.tmp"
timeout "$D" bash -c "while true; do dd if=/dev/zero of='$F' bs=1M count=256 oflag=direct conv=fsync status=none; done"
rm -f "$F"
