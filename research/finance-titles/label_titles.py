"""Step 1: structural/semantic labeling of every scraped title.

Labels per title:
  len            character length (spaces removed)
  structure      assertion | question | suspense(ellipsis) | exclamation (multi, pipe-joined)
  hooks          alert | number_list | first_person | expose | series_number | curiosity_gap
  emotion        crisis | excitement
  signature      channel-specific signature element if present
"""
import csv
import glob
import os
import re

BASE = os.path.dirname(__file__)
RAW = os.path.join(BASE, "raw")
OUT = os.path.join(BASE, "labels")
os.makedirs(OUT, exist_ok=True)

ALERT = ["breaking", "wtf", "urgent", "alert", "just in", "速報", "緊急",
         "突发", "重磅", "劲爆", "刚刚", "快讯", "紧急"]
CRISIS = ["crash", "collapse", "bubble", "crisis", "panic", "worst",
          "bankrupt", "recession", "崩", "暴跌", "暴落", "急落", "危机", "危機",
          "破产", "破産", "衰退", "暴雷"]
EXCITE = ["insane", "massive", "huge", "amazing", "finally", "biggest",
          "史上", "最大", "最強", "最强", "狂揽", "狂飙", "暴涨", "爆赚", "逆袭"]
EXPOSE = ["曝光", "揭秘", "深扒", "内幕", "起底", "exposed", "truth about",
          "secret", "secrets", "真実", "裏側", "暴露"]
FIRST_PERSON = re.compile(r"\b(i|my|we|our|me)\b", re.I)
FIRST_PERSON_CJK = ["自分", "僕", "うち", "私は", "俺"]
FIRST_PERSON_CN = re.compile(r"(?<!自)(?<!忘)(?<!知)我")
LISTICLE_EN = re.compile(r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+"
                         r"(ways|reasons|things|rules|signs|habits|steps|mistakes|lessons|stocks|tips)\b", re.I)
LISTICLE_JP = re.compile(r"\d+\s*(選|つ|個|ヶ所|か所|カ条|条|大|の理由|の共通点)")
LISTICLE_CN = re.compile(r"\d+\s*(个|种|大|条|招)")
SERIES = re.compile(r"(第\s*\d+\s*[期集回]|\bpart\s*\d+\b|\bepisode\s*\d+\b|[①②③④⑤⑥⑦⑧⑨⑩]|"
                    r"\(上\)|\(下\)|（上）|（下）|\bvol\.?\s*\d+)", re.I)
CURIOUS = ["…", "...", "竟然是", "没想到", "居然", "actually", "真相", "究竟", "到底"]

SIGNATURES = {
    "us_GrahamStephan": ["BREAKING:", "WTF"],
    "us_MeetKevin": ["BREAKING:", "WTF", "Update:"],
    "us_AndreiJikh": ["What You MUST Know", "What You Must Know", "My Response"],
    "us_EconomicsExplained": ["| Economics Explained", "The Economics of"],
    "us_HowMoneyWorks": ["- How Money Works"],
    "jp_ryogakucho": ["【お金のニュース】", "【リベ大公式切り抜き】", "【再放送】", "[Rebroadcast]", "[Rerun]"],
    "jp_nktofficial": ["【", "Part"],
    "jp_DanTakahashi1": ["【速報】", "【緊急】", "BREAKING"],
    "cn_xiao_lin_shuo": ["一口气", "【硬核】", "【精彩】"],
    "cn_caijinglengyan": ["财经冷眼：", "（未删减版）"],
}

def label(channel, title):
    low = title.lower()
    length = len(title.replace(" ", ""))

    structure = []
    if re.search(r"[?？❓❔⁉]", title):
        structure.append("question")
    if "…" in title or "..." in title:
        structure.append("suspense")
    if re.search(r"[!！‼❗]", title):
        structure.append("exclamation")
    if not structure:
        structure.append("assertion")

    hooks = []
    if any(a in low for a in [x.lower() for x in ALERT]):
        hooks.append("alert")
    if LISTICLE_EN.search(title) or LISTICLE_JP.search(title) or LISTICLE_CN.search(title):
        hooks.append("number_list")
    if FIRST_PERSON.search(title) or any(p in title for p in FIRST_PERSON_CJK) or FIRST_PERSON_CN.search(title):
        hooks.append("first_person")
    if any(e in low for e in [x.lower() for x in EXPOSE]):
        hooks.append("expose")
    if SERIES.search(title):
        hooks.append("series_number")
    if any(c in title for c in CURIOUS) or any(c in low for c in ["actually"]):
        hooks.append("curiosity_gap")

    emotion = []
    if any(c in low for c in [x.lower() for x in CRISIS]):
        emotion.append("crisis")
    if any(c in low for c in [x.lower() for x in EXCITE]):
        emotion.append("excitement")

    sig = [s for s in SIGNATURES.get(channel, []) if s.lower() in low]

    return {
        "title": title,
        "len": length,
        "structure": "|".join(structure),
        "hooks": "|".join(hooks),
        "emotion": "|".join(emotion),
        "signature": "|".join(sig),
    }

for path in sorted(glob.glob(os.path.join(RAW, "*.tsv"))):
    channel = os.path.basename(path)[:-4]
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            t = line.split("\t")[0].strip()
            if t:
                rows.append(label(channel, t))
    out_path = os.path.join(OUT, channel + ".csv")
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["title", "len", "structure", "hooks", "emotion", "signature"])
        w.writeheader()
        w.writerows(rows)
    print(f"{channel}: {len(rows)} labeled -> {out_path}")
