# Live prediction check: Ridge vs persistence vs blends

Rows scored (live predictions with actual CPU backfilled):
616

Mean absolute error in CPU percentage points (lower is better):

| ridge | blend_75_25 | blend_50_50 | blend_25_75 | stay  |
|-------|-------------|-------------|-------------|-------|
| 3.587 |       3.213 |       2.963 |       2.886 | 3.025 |

Reading: live Ridge is worse than 'CPU stays as now'. The 25/75 blend is only slightly better than 'stay', so the gain is small.
