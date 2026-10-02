"""Step 2+: quantity + time-evolution of techniques per channel.

Time axis: playlist order (index 0 = newest). Split into 5 equal buckets:
  T1 = newest 20% ... T5 = oldest 20%.
财经冷眼 titles embed absolute dates (YYYYMMDDX第N期) -> extract real years.
"""
import csv
import glob
import os
import re
from collections import Counter

BASE = os.path.dirname(__file__)
LBL = os.path.join(BASE, "labels")

MARKERS = [  # (name, how to detect from label row)
    ("问句", lambda r: "question" in r["structure"]),
    ("感叹", lambda r: "exclamation" in r["structure"]),
    ("悬念省略", lambda r: "suspense" in r["structure"]),
    ("警报体", lambda r: "alert" in r["hooks"]),
    ("数字清单", lambda r: "number_list" in r["hooks"]),
    ("第一人称", lambda r: "first_person" in r["hooks"]),
    ("好奇缺口", lambda r: "curiosity_gap" in r["hooks"]),
    ("系列编号", lambda r: "series_number" in r["hooks"]),
    ("招牌元素", lambda r: bool(r["signature"])),
]

def pct(n, d):
    return round(100 * n / d) if d else 0

DATE_RE = re.compile(r"[（(](\d{4})(\d{2})(\d{2})第?\d*期?[）)]")

report = []
for path in sorted(glob.glob(os.path.join(LBL, "*.csv"))):
    ch = os.path.basename(path)[:-4]
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    n = len(rows)
    if not n:
        continue

    # quantity per marker (all time)
    total_line = {name: pct(sum(f(r) for r in rows), n) for name, f in MARKERS}

    # time buckets: T1 newest .. T5 oldest
    bsize = max(1, n // 5)
    buckets = [rows[i * bsize:(i + 1) * bsize] if i < 4 else rows[4 * bsize:]
               for i in range(5)]
    trends = {}
    for name, f in MARKERS:
        trends[name] = [pct(sum(f(r) for r in b), len(b)) for b in buckets]

    report.append(f"\n## {ch}（共 {n} 条，T1=最新20% → T5=最早20%）\n")
    report.append("| 手法 | 总量% | T1最新 | T2 | T3 | T4 | T5最早 | 趋势 |")
    report.append("|---|---|---|---|---|---|---|---|")
    for name, _ in MARKERS:
        t = trends[name]
        delta = t[0] - t[-1]
        arrow = "↑走强" if delta >= 15 else ("↓减弱" if delta <= -15 else "→平稳")
        report.append(f"| {name} | {total_line[name]} | {t[0]} | {t[1]} | {t[2]} | {t[3]} | {t[4]} | {arrow} |")

    # absolute years for channels with dates in titles (财经冷眼)
    years = Counter()
    for r in rows:
        m = DATE_RE.search(r["title"])
        if m:
            years[m.group(1)] += 1
    if years:
        yr = ", ".join(f"{y}年{c}条" for y, c in sorted(years.items()))
        report.append(f"\n标题内嵌真实年份分布：{yr}")

out = "\n".join(report)
with open(os.path.join(BASE, "手法数量与时间.md"), "w", encoding="utf-8") as f:
    f.write("# 各频道标题手法：使用数量与时间演变\n\n")
    f.write("> 时间轴说明：播放列表顺序（新→旧）五等分，T1=最新20%，T5=最早20%。\n")
    f.write("> 绝对年份标注待网络恢复后补齐；财经冷眼标题自带日期，已直接提取真实年份。\n")
    f.write(out)
print(out)
