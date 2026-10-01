"""Deep structural/semantic feature extraction per channel."""
import glob
import os
import re
from collections import Counter

RAW = os.path.join(os.path.dirname(__file__), "raw")

URGENCY = ["breaking", "wtf", "just", "warning", "urgent", "alert", "now",
           "速報", "緊急", "突发", "曝光", "刚刚", "重磅"]
CRISIS = ["crash", "collapse", "collapsing", "bubble", "crisis", "panic",
          "falling", "fall", "drop", "worst", "bankrupt", "崩", "暴跌", "暴落",
          "危机", "危機", "破产", "破産", "急落", "下げ"]
SELFREF = ["i ", "i'", "my ", "we ", "our ", "me ", "我", "自分", "僕", "うち", "私"]
LISTICLE_EN = re.compile(r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+(ways|reasons|things|rules|signs|habits|steps|mistakes|lessons|stocks|tips)\b", re.I)
LISTICLE_JP = re.compile(r"\d+\s*(選|つ|個|ヶ所|か所|カ条|条|大)")
QUESTION_OPEN_EN = re.compile(r"^(why|how|what|is|are|can|do|does|did|will|should|who|where|when)\b", re.I)

def load(path):
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            t = line.split("\t")[0].strip()
            if t:
                out.append(t)
    return out

def pct(n, d):
    return round(100 * n / d) if d else 0

for path in sorted(glob.glob(os.path.join(RAW, "*.tsv"))):
    key = os.path.basename(path)[:-4]
    titles = load(path)
    if not titles:
        continue
    n = len(titles)
    low = [t.lower() for t in titles]

    first_words = Counter(t.split()[0].strip("【[\"'").lower() for t in titles if t.split())
    urgency = sum(any(u in t for u in URGENCY) for t in low)
    crisis = sum(any(c in t for c in CRISIS) for t in low)
    selfref = sum(any(s in (" " + t) for s in SELFREF) for t in low)
    listicle = sum(bool(LISTICLE_EN.search(t) or LISTICLE_JP.search(t)) for t in titles)
    qopen = sum(bool(QUESTION_OPEN_EN.search(t)) for t in titles)
    suffix_bar = sum(bool(re.search(r"\|\s*\S+$", t)) for t in titles)
    excl = sum("!" in t or "！" in t for t in titles)
    ellipsis = sum("…" in t or "..." in t for t in titles)

    lens = sorted(len(t.replace(" ", "")) for t in titles)
    q1, q2, q3 = lens[n // 4], lens[n // 2], lens[3 * n // 4]

    print(f"\n### {key} ({n} titles)")
    print(f"len quartiles: {q1}/{q2}/{q3} | urgency {pct(urgency,n)}% | crisis {pct(crisis,n)}% | self-ref {pct(selfref,n)}% | listicle {pct(listicle,n)}% | q-open {pct(qopen,n)}% | bar-suffix {pct(suffix_bar,n)}% | excl {pct(excl,n)}% | ellipsis {pct(ellipsis,n)}%")
    print("top first-words:", ", ".join(f"{w}×{c}" for w, c in first_words.most_common(8)))
