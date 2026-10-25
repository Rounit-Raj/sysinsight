## 2026-10-25: Full-stack validation and CPU stress test

### Setup
- Started the complete SysInsight stack: collector, live anomaly detector, live predictor, and dashboard.
- Verified that sample and prediction records continued to increase in SQLite.
- Stopped the previous standalone predictor to avoid duplicate predictor processes.

### CPU stress test
- Tool: `stress-ng`
- Command: `stress-ng --cpu 0 --timeout 30s`
- Duration: 30.01 seconds
- CPU workers: 12
- Result: 12 passed, 0 failed.

### Observed anomaly
- Recorded CPU usage increased from approximately 10.74% at 13:52:13 to 72.44% at 13:52:14.
- CPU usage reached 100% in subsequent samples.
- The detector recorded a HIGH CPU spike alert at 13:52:14.
- Alert message: `CPU spike: 72.4% (calm baseline 9.8%)`.

### Outcome
The collector recorded the CPU-load event, and the detector generated a corresponding HIGH alert. This confirms a successful observed detection event during the test session. It does not establish overall detection accuracy or false-positive rate; those require evaluation across multiple labelled normal and anomalous runs.
