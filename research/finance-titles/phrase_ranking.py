"""Generate per-channel most-common signature phrase rankings -> 惯用语句排行榜.md"""
import glob
import os
import re
from collections import Counter

BASE = os.path.dirname(__file__)
RAW = os.path.join(BASE, "raw")

NAMES = {
    "us_GrahamStephan": "Graham Stephan（美）",
    "us_AndreiJikh": "Andrei Jikh（美）",
    "us_MeetKevin": "Meet Kevin（美）",
    "us_EconomicsExplained": "Economics Explained（美）",
    "us_HowMoneyWorks": "How Money Works（美）",
    "jp_ryogakucho": "両学長 リベ大（日）",
    "jp_nktofficial": "中田敦彦（日）",
    "jp_DanTakahashi1": "高橋ダン（日）",
    "cn_xiao_lin_shuo": "小Lin说（中）",
    "cn_caijinglengyan": "财经冷眼（中）",
}

STOP_EN = {"the", "a", "an", "of", "to", "in", "is", "are", "on", "for", "and",
           "or", "you", "your", "my", "i", "it", "its", "this", "that", "how",
           "why", "what", "new", "will", "be", "by", "at", "as", "with", "from"}

def load_titles(path):
    return [l.split("\t")[0].strip() for l in open(path, encoding="utf-8")
            if l.split("\t")[0].strip()]

def en_phrases(titles):
    """top bigrams/trigrams + ALL-CAPS words + bracket/suffix patterns"""
    bi, tri, caps, paren = Counter(), Counter(), Counter(), Counter()
    for t in titles:
        words = [w.strip("“”\"'():,!?—-[]|") for w in t.split()]
        words = [w for w in words if w]
        low = [w.lower() for w in words]
        for i in range(len(low) - 1):
            if low[i] not in STOP_EN and low[i + 1] not in STOP_EN:
                bi[" ".join(low[i:i + 2])] += 1
        for i in range(len(low) - 2):
            if sum(w in STOP_EN for w in low[i:i + 3]) <= 1:
                tri[" ".join(low[i:i + 3])] += 1
        for w in re.findall(r"\b[A-Z]{3,}\b", t):
            caps[w] += 1
        for m in re.findall(r"[\(\|]([^()\|]{4,40})[\)]?\s*$", t):
            paren[m.strip().lower()] += 1
    return bi, tri, caps, paren

def cjk_phrases(titles):
    """bracket tokens, prefix-before-colon, and char 2-4grams with count>=5"""
    bracket, prefix, grams = Counter(), Counter(), Counter()
    for t in titles:
        for m in re.findall(r"[【\[]([^】\]]{1,15})[】\]]", t):
            bracket[m] += 1
        m = re.match(r"^([^：:，,]{2,12})[：:]", t)
        if m:
            prefix[m.group(1)] += 1
        chars = re.sub(r"[\s　【】\[\]（）()：:，,。.!！?？…~〜|丨、\-—]", "", t)
        for n in (4, 3, 2):
            for i in range(len(chars) - n + 1):
                g = chars[i:i + n]
                if not g.isascii() and sum(c.isdigit() for c in g) < 2:
                    grams[g] += 1
    # keep grams that are not fully contained in a longer gram with same count
    items = {g: c for g, c in grams.items() if c >= 5 and not re.search(r"[a-zA-Z]", g)}
    drop = set()
    for g, c in items.items():
        for g2, c2 in items.items():
            if len(g2) > len(g) and g in g2 and c2 >= c * 0.9:
                drop.add(g)
                break
    grams = Counter({g: c for g, c in items.items() if g not in drop})
    return bracket, prefix, grams

GLOSS = {
    "暴落": "暴跌", "買う": "买入", "投資": "投资", "発表": "发布", "ドル": "美元",
    "とは": "“是什么”句式", "のか": "疑问尾“…吗”", "時代": "时代", "お金": "金钱",
    "お金の": "金钱的", "動画": "视频", "アニメ動画": "动画视频", "第1": "第1xx集编号",
    "ない": "否定结尾", "世界": "世界", "日本": "日本", "中田": "中田（本人名）",
    "高橋": "高桥（本人名）", "ダン": "Dan（本人名）", "高橋ダン": "高桥Dan（本人名）",
    "速報": "速报", "一口气": "一口气（招牌句式）", "了解": "了解", "到底": "到底",
    "怎么": "怎么", "事儿": "事儿", "硬核": "硬核", "什么": "什么", "如何": "如何",
    "经济": "经济", "全球": "全球", "冷眼": "冷眼（栏目名）", "财经": "财经",
    "财经冷眼": "财经冷眼（栏目名）", "中国": "中国", "近平": "近平", "习近平": "习近平",
    "美国": "美国", "金融": "金融",
    "you must know": "你必须知道", "need to know": "需要知道", "do this now": "现在就做",
    "just got worse": "刚刚恶化", "how much money": "多少钱", "step by step": "手把手",
    "stock market": "股市", "passive income": "被动收入", "must know": "必须知道",
    "dividend investing": "股息投资", "stimulus check": "刺激支票",
    "stimulus check update": "刺激支票进展", "real estate": "房地产",
    "the stock market": "股市", "the fed just": "美联储刚刚", "the housing market": "房市",
    "in real estate": "在房地产", "major changes explained": "重大变化解读",
    "housing market": "房市", "fed just": "美联储刚刚", "federal reserve": "美联储",
    "credit cards": "信用卡", "elon musk": "马斯克", "just said": "刚刚说",
    "economics explained": "经济学解析（品牌后缀）", "how money works": "金钱如何运作（品牌后缀）",
}

def gloss(p):
    return f"（{GLOSS[p]}）" if p in GLOSS else ""

lines = ["# 各频道最常见惯用语句 / 手法排行榜", "",
         "> 统计自全量 13,388 条真实标题。括号内为出现次数；短语后（）内为中文解释。", ""]

for path in sorted(glob.glob(os.path.join(RAW, "*.tsv"))):
    key = os.path.basename(path)[:-4]
    titles = load_titles(path)
    if not titles:
        continue
    lines.append(f"\n## {NAMES[key]}（{len(titles)} 条）\n")
    if key.startswith("us_"):
        bi, tri, caps, paren = en_phrases(titles)
        lines.append("**高频固定短语（3 词）**：")
        lines.append("")
        for p, c in tri.most_common(8):
            if c >= 5:
                lines.append(f"- {p}{gloss(p)} ×{c}")
        lines.append("")
        lines.append("**高频短语（2 词）**：")
        lines.append("")
        for p, c in bi.most_common(8):
            if c >= 8:
                lines.append(f"- {p}{gloss(p)} ×{c}")
        lines.append("")
        if caps:
            lines.append("**高频全大写警报词**：" + "、".join(f"{w}×{c}" for w, c in caps.most_common(8)))
            lines.append("")
        if paren:
            lines.append("**高频括号/竖线后缀**：" + "、".join(f"「{p}」×{c}" for p, c in paren.most_common(5)))
            lines.append("")
    else:
        bracket, prefix, grams = cjk_phrases(titles)
        if bracket:
            lines.append("**高频【】/[] 标签**：")
            lines.append("")
            for p, c in bracket.most_common(10):
                if c >= 3:
                    lines.append(f"- 【{p}】×{c}")
            lines.append("")
        if prefix:
            tops = [(p, c) for p, c in prefix.most_common(5) if c >= 3]
            if tops:
                lines.append("**高频开头前缀**：" + "、".join(f"「{p}：」×{c}" for p, c in tops))
                lines.append("")
        lines.append("**高频固定词组（≥5 次）**：")
        lines.append("")
        for p, c in grams.most_common(12):
            lines.append(f"- {p}{gloss(p)} ×{c}")
        lines.append("")

with open(os.path.join(BASE, "惯用语句排行榜.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("written 惯用语句排行榜.md")
