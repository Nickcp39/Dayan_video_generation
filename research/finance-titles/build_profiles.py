"""Step 2: aggregate labels into per-channel profiles."""
import csv
import glob
import json
import os
from collections import Counter

BASE = os.path.dirname(__file__)

def pct(n, d):
    return round(100 * n / d, 1) if d else 0.0

profiles = {}
for path in sorted(glob.glob(os.path.join(BASE, "labels", "*.csv"))):
    ch = os.path.basename(path)[:-4]
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    n = len(rows)
    if not n:
        continue

    lens = sorted(int(r["len"]) for r in rows)
    structure_c = Counter()
    hooks_c = Counter()
    emotion_c = Counter()
    sig_c = Counter()
    for r in rows:
        for s in r["structure"].split("|"):
            if s: structure_c[s] += 1
        for h in r["hooks"].split("|"):
            if h: hooks_c[h] += 1
        for e in r["emotion"].split("|"):
            if e: emotion_c[e] += 1
        for g in r["signature"].split("|"):
            if g: sig_c[g] += 1

    no_hook = sum(1 for r in rows if not r["hooks"])

    profiles[ch] = {
        "n": n,
        "len": {"p25": lens[n // 4], "median": lens[n // 2], "p75": lens[3 * n // 4],
                "mean": round(sum(lens) / n, 1)},
        "structure_pct": {k: pct(v, n) for k, v in structure_c.most_common()},
        "hooks_pct": {k: pct(v, n) for k, v in hooks_c.most_common()},
        "no_hook_pct": pct(no_hook, n),
        "emotion_pct": {k: pct(v, n) for k, v in emotion_c.most_common()},
        "signature_top": sig_c.most_common(8),
    }

with open(os.path.join(BASE, "channel_profiles.json"), "w", encoding="utf-8") as f:
    json.dump(profiles, f, ensure_ascii=False, indent=1)

# readable summary table
cols = ["alert", "number_list", "first_person", "expose", "series_number", "curiosity_gap"]
print(f"{'channel':24} {'n':>5} {'len中位':>6} {'问':>4} {'叹':>4} {'悬念':>4} | " +
      " ".join(f"{c[:9]:>9}" for c in cols) + f" {'无钩子':>6}")
for ch, p in sorted(profiles.items()):
    s, h = p["structure_pct"], p["hooks_pct"]
    print(f"{ch:24} {p['n']:>5} {p['len']['median']:>6} "
          f"{s.get('question',0):>4} {s.get('exclamation',0):>4} {s.get('suspense',0):>4} | " +
          " ".join(f"{h.get(c,0):>9}" for c in cols) + f" {p['no_hook_pct']:>6}")
print("\n招牌元素 TOP:")
for ch, p in sorted(profiles.items()):
    if p["signature_top"]:
        print(f"  {ch}: " + "; ".join(f"{k}×{v}" for k, v in p["signature_top"][:5]))
