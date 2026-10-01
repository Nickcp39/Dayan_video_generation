"""Analyze scraped finance-YouTuber titles: length, digits, questions, casing, signature phrases."""
import csv
import glob
import os
import re
from collections import Counter

RAW = os.path.join(os.path.dirname(__file__), "raw")
OUT = os.path.dirname(__file__)

CHANNEL_META = {
    "us_GrahamStephan": ("美国", "Graham Stephan", "个人理财/房产", "约400万"),
    "us_AndreiJikh": ("美国", "Andrei Jikh", "投资/股票", "约240万"),
    "us_MeetKevin": ("美国", "Meet Kevin", "市场快评/地产", "约190万"),
    "us_EconomicsExplained": ("美国", "Economics Explained", "宏观经济科普", "约290万"),
    "us_HowMoneyWorks": ("美国", "How Money Works", "财富观念/金钱史", "约280万"),
    "jp_ryogakucho": ("日本", "両学長 リベラルアーツ大学", "理财/省钱/副业", "约260万"),
    "jp_nktofficial": ("日本", "中田敦彦のYouTube大学", "知识综合(含大量经济回)", "约530万"),
    "jp_DanTakahashi1": ("日本", "高橋ダン Dan Takahashi", "市场分析/投资", "约70万+"),
    "cn_xiao_lin_shuo": ("中文", "小Lin说", "财经科普/商业故事", "283万"),
    "cn_caijinglengyan": ("中文", "财经冷眼", "时政财经评论", "约150万"),
}

NUM_RE = re.compile(r"\d")
Q_RE = re.compile(r"[?？]")
CAPS_RE = re.compile(r"\b[A-Z]{3,}\b")
JP_RE = re.compile(r"[぀-ヿ一-鿿]")
CN_ONLY_RE = re.compile(r"[一-鿿]")


def title_len(t):
    return len(t.replace(" ", ""))


def ngrams(words, n):
    return [" ".join(words[i:i + n]) for i in range(len(words) - n + 1)]


def bracket_prefix(t):
    m = re.match(r"^[【\[](.{1,12})[】\]]", t)
    return m.group(1) if m else None


summary_rows = []
per_channel_counter = {}

for path in sorted(glob.glob(os.path.join(RAW, "*.tsv"))):
    key = os.path.basename(path)[:-4]
    if key not in CHANNEL_META:
        continue
    titles = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if parts and parts[0].strip():
                titles.append(parts[0].strip())
    if not titles:
        continue
    n = len(titles)
    lens = [title_len(t) for t in titles]
    with_num = sum(bool(NUM_RE.search(t)) for t in titles)
    with_q = sum(bool(Q_RE.search(t)) for t in titles)
    with_caps = sum(bool(CAPS_RE.search(t)) for t in titles)
    with_bracket = sum(bool(bracket_prefix(t)) for t in titles)

    # word frequency (English: words; JP/CN: bracket prefixes + common kanji phrases)
    region = CHANNEL_META[key][0]
    if region == "美国":
        words_all = []
        for t in titles:
            words_all += [w.strip("“”\"'():,!?—-").lower() for w in t.split()]
        common = Counter(w for w in words_all if len(w) > 3).most_common(15)
        phrases = []
        for t in titles:
            phrases += ngrams(t.lower().split(), 2)
        common_ph = Counter(p for p in phrases if not p.startswith(("the ", "a "))).most_common(10)
    else:
        bp = [bracket_prefix(t) for t in titles]
        common = Counter(b for b in bp if b).most_common(15)
        common_ph = []

    region, name, topic, subs = CHANNEL_META[key]
    summary_rows.append({
        "region": region, "channel": name, "topic": topic, "subs": subs,
        "videos": n,
        "avg_len": round(sum(lens) / n, 1),
        "median_len": sorted(lens)[n // 2],
        "pct_number": round(100 * with_num / n),
        "pct_question": round(100 * with_q / n),
        "pct_caps_or_bracket": round(100 * (with_caps if region == "美国" else with_bracket) / n),
        "top_tokens": "; ".join(f"{w}×{c}" for w, c in common[:10]),
        "top_bigrams": "; ".join(f"{w}×{c}" for w, c in common_ph[:8]),
    })
    per_channel_counter[key] = common

with open(os.path.join(OUT, "stats_summary.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
    w.writeheader()
    w.writerows(summary_rows)

for row in summary_rows:
    print(row)
print("\nsaved stats_summary.csv")
