# Live forecast check (5 min ahead, 616 predictions)

| Forecast | MAE |
|---|---|
| Ridge model alone | 3.587 |
| 75% model / 25% stay | 3.213 |
| 50% model / 50% stay | 2.963 |
| 25% model / 75% stay | 2.886 |
| "CPU stays as now" baseline | 3.025 |

**Decision:** the live forecast is 25% Ridge + 75% "CPU stays as now".

Ridge alone lost to the naive baseline on live data, so the blend is used. The
blend beats the baseline by only about 0.14 MAE, a small margin on a short
window, so re-check it once more live data has been collected.
