# SysInsight project log
## Status (as of 4-5 Oct 2026)

- Phase 0 (repo hygiene) and Phase 1 (collector hardening): done.
- Phase 2 (ML): labelled test set built, detector variants compared, validated on a second run.
- Not started: CPU prediction models, dashboard upgrade, tests, report.

## Prototype (before this log)

- C++17 collector: CPU %, RAM %, 1-minute load average, one row per second to data/readings.csv.
- Python: Isolation Forest anomaly detection (ml/detect_anomalies.py) and a Rich terminal dashboard (ml/dashboard.py).

## Phase 1: collector hardening (4-5 Oct 2026)

- Per-process logging: top 5 processes by CPU each second (pid, name, cpu %, memory MB) to data/processes.csv. Reads /proc/[pid]/stat; handles process names containing spaces.
- Disk and network metrics to data/io.csv: disk read/write MB/s (whole disks only, no partitions) and network down/up KB/s (all interfaces except lo). Verified with dd and curl: 1000 MB written showed as about 1000 MB/s-seconds in the log.
- SQLite logging (collector/db.hpp, data/sysinsight.db): tables samples, processes, io, alerts; WAL mode; one transaction per batch. CSVs are still written alongside.
- Threaded design: sampler thread (1 Hz, drift-free sleep_until) builds a snapshot and puts it on a mutex-protected queue; writer thread drains the queue and writes CSVs and DB. Verified row counts matched between CSV and DB (117 = 117; processes = 5 x samples).
- Clean shutdown on SIGINT/SIGTERM: sampler stops, writer drains the queue, files close.
- Error handling: unreadable /proc files warn once and use fallback values; counter glitches clamped to zero.
- Memory check: collector resident memory stayed about 4.7 MB over two minutes (no visible leak).
- CMake: C++17 required, find_package for SQLite3 and Threads, -Wall -Wextra -Wpedantic.
- Incident: two collectors ran at once and wrote duplicate rows. Lesson: check pgrep collector before starting. Duplicates only matter for time-based features; evaluation scripts drop duplicate timestamps.

## Phase 2: detector evaluation

Labelled test set: scripts/run_stress_test.sh runs 60 s normal, 30 s CPU stress (stress-ng --cpu 0), 60 s normal, 30 s memory stress (--vm 1 --vm-bytes 40%), 60 s normal, 30 s disk stress (--hdd 2 --hdd-bytes 500m), 60 s normal. Start/end times of each phase go to data/labels.csv (run 1) and data/labels_run2.csv (run 2, same script, browser closed).

Sanity check of the stress itself: during memory stress RAM averaged about 37% (peak about 42%) versus about 8-9% normally; during disk stress CPU, RAM and load stayed near normal, so only the disk columns reveal it.

Experiments (output files in docs/results/):

1. evaluate.py - fit and score on the same labelled window (332 rows, 27% anomalous). Best F1 about 0.76 for CPU+RAM+load at contamination 0.2. Adding raw disk/network columns raised disk-stress detection (about 3% to 37%) but lowered precision. Rolling-mean/std features did not help (worst F1 about 0.52). Weakness: the data is 27% anomalous, which is unrealistic for Isolation Forest, and train/test were the same rows.
2. evaluate_novelty.py - train on data from before the test window (375 rows), test on the window. CPU+RAM+load flagged 100% of normal seconds as anomalies (test session was calmer than the training sessions). Log-transformed disk/network set was best: F1 about 0.74, about 3% false alarms, caught about 97% of CPU and disk stress but 0% of memory stress.
3. evaluate_hybrid.py - trimmed 3 s around each phase boundary (label noise). Isolation Forest alone: F1 about 0.77, about 1.9% false alarms, memory stress 0% caught. A rule using all metrics flagged 14-25% of normal seconds; the cause was load_avg_1min (lagging average, about 14% false alarms alone). Isolation Forest plus a RAM-only rule (T=6, median/MAD-based): F1 about 0.95, about 1.9% false alarms, caught about 100% CPU, 88% memory, 100% disk.
4. evaluate_validate.py - same settings, scored on run 2 without re-tuning. Train A (data before run 1): hybrid F1 about 0.93, about 3.3% false alarms, caught 100% / 87% / 100% (CPU / memory / disk); Isolation Forest alone F1 about 0.75 with memory 0%. Train B (train A plus run 1's normal seconds): worse (hybrid F1 about 0.78, CPU stress caught only about 9%).

## Decisions and why

- Keep per-process, io and DB output separate from readings.csv so the original ML scripts keep working.
- Load average left out of the rule detector (too laggy).
- RAM rule added because Isolation Forest did not react to a large RAM jump while seven features were being watched.
- Disk/network features log-transformed (log1p) to tame spikes.
- 3 s trimmed at phase boundaries because collector timestamps lag the labels slightly.
## Limitations ( for research purposes)

- One machine, one day, one stress tool; stress-ng overloads are not the same as real-world faults.
- RAM rule threshold and contamination chosen on run 1; run 2 is the only independent check.
- Disk test writes only; disk-read anomalies untested.
- About 3% false alarms is roughly 2 per minute at 1 Hz, which is noisy for a dashboard.
- Training on more recent normal data (train B) made things worse; cause not yet confirmed.
## Open items

- Find why train B hurt CPU detection (suspect contaminated normal seconds).
- Test an "alert only after N consecutive anomalous seconds" rule to cut false alarms.
- CPU prediction models (Random Forest / Decision Tree) and model comparison table.
- Build the detector into the live pipeline; dashboard upgrade and theme.
- Unit tests, long soak test, final report and demo.
