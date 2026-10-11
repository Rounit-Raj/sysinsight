import csv
import sys
from datetime import datetime

FMT = "%Y-%m-%d %H:%M:%S"

src, dst = sys.argv[1], sys.argv[2]

with open(src, newline="") as f:
    rows = list(csv.DictReader(f))

# accept either "type" or "label" as the name column
name_col = "label" if "label" in rows[0] else "type"
events = sorted(
    (datetime.strptime(r["start"], FMT), datetime.strptime(r["end"], FMT), r[name_col])
    for r in rows
)

out = []
for i, (start, end, name) in enumerate(events):
    if i > 0:
        prev_end = events[i - 1][1]
        if start > prev_end:
            out.append((prev_end, start, "normal"))
    out.append((start, end, name))

with open(dst, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["start", "end", "label"])
    for s, e, name in out:
        w.writerow([s.strftime(FMT), e.strftime(FMT), name])

print(f"wrote {len(out)} rows to {dst}")
