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
- 2026-10-05: train B hurt CPU detection although run 1 normal rows were clean (no contamination); Isolation Forest scores for CPU stress flipped from anomalous to normal depending on the training mix. Rules alone (CPU, RAM, disk write; median/MAD thresholds) reached F1 about 0.98 with 0% false alarms on both runs and both training sets (docs/results/hybrid3_20261005.txt). Caveat: the test only contains single-metric overloads, which favours rules; need subtler anomalies to see what Isolation Forest adds.
- 2026-10-09: run 3 (subtle CPU, combo, network burst; scripts/run_subtle_test.sh, run_net_test.sh). Four median/MAD rules (CPU, RAM, disk write, network rx; T=3) reached F1 about 0.98-0.99 on runs 1-3 with 0-0.9% false alarms; Isolation Forest alone F1 about 0.75-0.79; IF added only false alarms (1.5-3.3%). Caveat: T=3 and the network rule were chosen after seeing run 3; all tested anomalies are single-metric overloads; calm phases were quieter than normal use (docs/results/final_compare_20261009.txt). Isolation Forest kept only as a secondary signal.

## 2026-10-11: Live detector
- Added ml/live_detector.py: four rules (CPU, RAM, disk write, network) against a rolling median+MAD baseline of calm data from data/sysinsight.db.
- One alert per event; a constant level for 5 minutes becomes the new baseline (handles RAM drift 8.5% to 12.5%).
- Dry run on old data: one alert per stress event. Live test with stress-ng: one CPU spike alert written to the alerts table.
- Next: Isolation Forest as a lower-severity "unusual pattern" warning.

## 2026-10-11: CPU prediction dataset (ml/cpu_dataset.py)
- Target: CPU % 5 minutes ahead. Features are gap-safe, so rows spanning a recording gap are not mixed.
- Split: chronological (train on earlier data, test on later data), to avoid leaking the future into training.
- Size: 13786 raw samples -> 9127 train rows / 2357 test rows after building.
- Baselines to beat (test MAE): always predict train mean = 9.461; "CPU stays as now" = 5.148.
- Next: train Random Forest / Decision Tree, build the comparison table, save the best model with joblib.

## 2026-10-11: CPU prediction models (Phase 2)

**Setup:** The target is CPU % five minutes ahead. The dataset is 9127 train rows and 2357 test rows, split chronologically, with gap-safe lag and rolling features (`ml/cpu_dataset.py`). Models are trained by `ml/train_cpu_models.py`.

**Results (test set, lower MAE is better):**

| Model | MAE | RMSE | R2 |
|---|---|---|---|
| Ridge regression | 4.554 | 6.376 | -0.264 |
| Gradient Boosting | 4.802 | 7.107 | -0.570 |
| Baseline: CPU stays as now | 5.148 | 7.224 | -0.622 |
| Random Forest | 5.635 | 8.339 | -1.161 |
| Decision Tree | 6.208 | 8.856 | -1.438 |
| Always train mean | 9.461 | 11.007 | -2.766 |

**Findings:**
- Ridge is the best model. Its MAE is about 11.5% lower than the "CPU stays as now" baseline, so the gain is modest but real.
- Random Forest and Decision Tree are worse than the baseline. They overfit the training period and do not transfer to the test period.
- All R2 values are negative, so no model beats predicting the test-set average in variance terms. A 5-minute-ahead target is noisy, and the data covers only about 3.8 hours on one machine.
- On small data with a chronological split, the simple model generalised best.

**Output:** The best model is saved to `ml/models/cpu_model.joblib`. The reload check confirmed identical predictions. The comparison table is in `docs/results/model_comparison.csv` and `.md`.

**Next:** Collect more varied data and re-run the comparison, then build the real dashboard.

## 2026-10-11: live forecast check
- Ran ml/live_predictor.py alongside the collector and compared 616 predictions with actual CPU 5 minutes later.
- Ridge alone (MAE 3.587) lost to "CPU stays as now" (3.025).
- A 25% model / 75% stay blend scored best (2.886), so it is the chosen forecast.
- Details: docs/results/live_forecast_check.md

## 2026-10-12 - Replay event check: subtle events (run 3)

Ran `ml/live_detector.py --replay --dry-run` on the two run 3 recordings and compared the alerts to the label files with `ml/check_replay_events.py` (output: `docs/results/replay_event_check_20261011.txt`).

| Event | run3 | rep1 |
|---|---|---|
| light_cpu | missed (0 alerts) | missed (0 alerts) |
| small_ram | missed (0 alerts) | missed (0 alerts) |
| disk_drip | missed (0 alerts) | missed (0 alerts) |
| cpu_bursts | detected (CPU spike) | detected (CPU spike) |

- Matching-rule detection: 1/4 events in each recording.
- Alerts inside labelled normal gaps: 4 in run3 (Network surge x3, CPU spike x1), 1 in rep1 (CPU spike).
- In both recordings the gap CPU spike sits in the normal window right before the cpu_bursts window; not yet checked whether this is label-boundary slack or a real false alarm.
- Conclusion: the current rule floors do not see subtle events (light CPU load, small RAM growth, slow disk writes). The earlier `evaluate_run3.py` numbers were baseline-mismatch artifacts, so this replay check is the reference result.
- Next: test lower rule floors, measuring catches on the subtle events against false alarms on calm data, before changing the defaults.

## 2026-10-12: Floor-scale sweep (live detector rules)

- Added `--floor-scale` to ml/live_detector.py; replayed the full db at scales 1.0, 0.5, 0.3, 0.2, 0.1 (docs/results/replay_floor_*.txt) and checked alerts against the run 3 labels (ml/check_floor_sweep.py, docs/results/floor_sweep_event_check.txt).
- cpu_bursts: detected 2/2 at every scale.
- light_cpu and small_ram: 0/2 at every scale, even at 0.1. Floors are not the limiting factor.
- disk_drip: detected 2/2 only at 0.1, with 12 alerts in the 360 s of normal gaps and about 600 disk alerts elsewhere. Not usable.
- Scales 0.5 to 0.2 add alerts without detecting anything new.
- Decision: keep the floors at 1.0 (CPU 15, RAM 3, disk 5, net 500). The rules catch large events; the subtle events are below what a median+MAD rule can separate from noise. Documented as a known limitation.

## 2026-10-12: Event-level check of the live detector on run 3

- Replayed the real pipeline (`python ml/live_detector.py --replay --dry-run`), saved to `docs/results/replay_alerts_20261011.txt`.
- Compared the alerts with the run 3 labels using `ml/check_replay_events.py` (262 alerts parsed). Output is in `docs/results/replay_event_check_20261011.txt`.
- Result: the rules caught only `cpu_bursts` (1 of 4 events), in both run3 and rep1.
- `light_cpu`, `small_ram` and `disk_drip` were missed completely (0 alerts inside their windows).
- False alarms in normal gaps: run3 had 4 (Network surge x3, CPU spike x1). rep1 had 1 (CPU spike just before the `cpu_bursts` window).
- Earlier `evaluate_run3.py` numbers were distorted by a baseline mismatch (the 1800-row calm baseline did not match machine state during the run 3 windows), so the replay check is the number to trust.
- Next: decide whether to lower the rule floors for the subtle events, with a false-alarm check on calm data.

## 2026-10-15 — Lower rule floors on run 3 replay
- Replay with --floor-scale 0.5 and 0.3 checked against run3 and rep1 labels (docs/results/replay_check_floor0.3_20261012.txt).
- Matching rule caught only cpu_bursts (1/4) in both recordings at every floor tested; light_cpu, small_ram and disk_drip produced 0 matching alerts.
- Lower floors added false alarms in normal gaps (rep1: 1 -> 4) without new detections.
- Conclusion: the subtle events lie within normal variation; floor tuning does not fix this. Keep the original floors.

## 2026-10-15 - Run 3 (subtle anomalies): live detector replay results

- Replayed both run 3 recordings (labels_run3_std.csv and labels_run3_rep1_std.csv) through `ml/live_detector.py --replay --dry-run` at the original floors, `--floor-scale 0.5` and `--floor-scale 0.3`.
- Event-level check (`ml/check_replay_events.py`): the matching rule caught only cpu_bursts (1 of 4 events) in both recordings. light_cpu, small_ram and disk_drip were never caught by their matching rule, even at floor scale 0.3.
- Lowering the floors did not help detection and added noise. At floor 0.3 there were 358 alerts, 347 of them outside labelled windows. Normal-gap alerts were 2 (run3) and 4 (rep1).
- The earlier suspicion that the checker was mis-parsing the new alert files was ruled out: the regex matched all 358 lines in the floor 0.3 file.
- Conclusion: lowering the rule floors does not catch the subtle events and costs many false alarms, so the floors stay at their original values. The subtle events are a documented limitation of the rule-based detector.
- Results saved in docs/results/ (replay_event_check_*, replay_check_floor0.3_20261012.txt).

## 2026-10-15 - Run 3 replay check (subtle anomalies)

- The first run 3 evaluation (ml/evaluate_run3.py) used a 1800-calm-row baseline from about 4 hours before the events. It did not match the machine state during the run 3 windows (event RAM 7-16 points below the baseline median), so its numbers and false alarms are baseline-mismatch artifacts.
- Switched to evaluating the real pipeline: `python ml/live_detector.py --replay --dry-run`, then an event-level check with ml/check_replay_events.py against both run 3 label files.
- Original floors: rules caught only cpu_bursts (1/4 events) in both run3 and rep1. light_cpu, small_ram and disk_drip got 0 alerts in their windows. Normal gaps had 4 alerts in run3 and 1 in rep1.
- Floor scale 0.3: 358 alerts parsed. The matching rule still caught only cpu_bursts (1/4 events) in both label files. Any alert hit 3/4 events. Normal-gap alerts: 2 (run3), 4 (rep1). 347 alerts fell outside labelled windows.
- Floor scale 0.5: not re-checked yet since the checker change (the first check of this file looked wrong).
- disk_drip is only about +0.05-0.10 MB/s above calm, so it is very small relative to the current rules.
- Result so far: lowering the floors to 0.3 did not make the rules catch light_cpu, small_ram or disk_drip.
- Results are in docs/results/ (replay_event_check_*, replay_check_floor0.3_20261012.txt).

## 2026-10-15: Run 3 replay findings (subtle anomalies)

- Evaluated the real pipeline with `python ml/live_detector.py --replay --dry-run`, then checked alerts against the run 3 label files (labels_run3_std.csv, labels_run3_rep1_std.csv) using `ml/check_replay_events.py`.
- Original floors: the rules caught only cpu_bursts (1/4 events) in both recordings. light_cpu, small_ram and disk_drip produced 0 alerts inside their windows. Normal gaps had 4 alerts in run3 and 1 in rep1.
- Floor scale 0.3: the matching rule still caught only cpu_bursts (1/4) in both recordings. Any alert in a window: 3/4. Normal-gap alerts: 2 in run3, 4 in rep1. 347 alerts fell outside labelled windows.
- Lowering the floors raised the alert count (269 lines originally, 365 at 0.3) without catching the subtle events with their matching rule.
- The floor 0.5 check result looked wrong (fewer detections than the original floors), so it is not used here.
- Earlier evaluate_run3.py numbers are baseline-mismatch artifacts (the 1800-row baseline did not match the machine state during the run 3 windows), so the replay results above are the ones to trust.
- Results files: docs/results/replay_event_check_20261011.txt, docs/results/replay_check_floor0.3_20261012.txt.
