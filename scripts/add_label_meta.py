import csv
import sys

# label -> (kind, subtle)
META = {
    "normal":        ("normal", "no"),
    "cpu_stress":    ("cpu",  "no"),
    "memory_stress": ("ram",  "no"),
    "disk_stress":   ("disk", "no"),
    "net_burst":     ("net",  "no"),
    "light_cpu":     ("cpu",  "yes"),
    "small_ram":     ("ram",  "yes"),
    "disk_drip":     ("disk", "yes"),
    "cpu_bursts":    ("cpu",  "yes"),
}

for path in sys.argv[1:]:
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        kind, subtle = META[r["label"]]
        r["kind"] = kind
        r["subtle"] = subtle
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["start", "end", "label", "kind", "subtle"])
        w.writeheader()
        w.writerows(rows)
    print(f"updated {path} ({len(rows)} rows)")
