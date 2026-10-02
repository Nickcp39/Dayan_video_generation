"""b5: statistics for the report.

1. Concentration: per blog, how much of its total HN points comes from its top 10% of posts.
2. Title features over *all* collected posts, compared inside each blog
   (top quartile by points vs bottom half), then summarized across blogs.
3. Content codes for the hot/cold pairs: per dimension, hot minus cold inside each pair,
   with the share of pairs where hot > cold and a two-sided sign test.
4. Chinese pilot (ruanyifeng): comment-count distribution and the same title comparison.

Output: out/results.json and out/tables.md.
"""
import math
import re
import statistics as st
from collections import Counter, defaultdict

from common import DATA, OUT, blogs, read_json, write_json

SCORES = ["audience_scope", "reader_mirror", "contrarian", "surprise", "practical_value", "social_currency",
          "identity", "narrative", "vulnerability", "concreteness", "debate", "timeliness", "accessibility"]
CATS = ["post_type", "emotion", "arousal", "valence", "authority", "opening", "title_promise"]
# Pair-level tests on categorical codes, turned into numbers.
DERIVED = {
    "arousal_level": lambda c: {"low": 0, "medium": 1, "high": 2}[c["arousal"]],
    "felt_emotion": lambda c: int(c["emotion"] not in ("curiosity", "none")),  # an emotion beyond plain interest
    "personal_story": lambda c: int(c["post_type"] == "personal_story"),
    "scene_opening": lambda c: int(c["opening"] == "scene"),
    "title_topic_only": lambda c: int(c["title_promise"] == "topic"),
    "life_domain": lambda c: int(bool({"career_work", "family_relationships", "status_identity", "health_aging"}
                                      & set(c["life_domains"]))),
    "craft_or_tool_only": lambda c: int(set(c["life_domains"]) <= {"tech_tools", "craft_expertise"}),
}

EN_TITLE = {
    "question": lambda t: "?" in t,
    "number": lambda t: bool(re.search(r"\d", t)),
    "how_why_what": lambda t: bool(re.match(r"(?i)(how|why|what|when|who)\b", t.strip())),
    "you": lambda t: bool(re.search(r"(?i)\b(you|your)\b", t)),
    "first_person": lambda t: bool(re.search(r"(?i)\b(i|i'm|i've|my|we|our)\b", t)),
    "negation": lambda t: bool(re.search(r"(?i)\b(not|no|never|don't|doesn't|isn't|can't|won't|stop)\b", t)),
    "colon": lambda t: ":" in t,
    "imperative_start": lambda t: bool(re.match(r"(?i)(do|don't|stop|start|use|learn|choose|write|make|be|keep)\b", t.strip())),
}
ZH_TITLE = {
    "question": lambda t: bool(re.search(r"[?？]", t)),
    "number": lambda t: bool(re.search(r"\d|[一二三四五六七八九十百千万]+(?:个|种|条|年|大)", t)),
    "how_why_what": lambda t: bool(re.search(r"为什么|怎么|如何|什么|是否|吗", t)),
    "you": lambda t: "你" in t,
    "first_person": lambda t: bool(re.search(r"我", t)),
    "negation": lambda t: bool(re.search(r"不|没|别|无", t)),
    "colon": lambda t: bool(re.search(r"[:：]", t)),
    "tutorial": lambda t: bool(re.search(r"教程|入门|指南|详解|简介|笔记", t)),
}


def sign_test(pos, neg):
    """Two-sided binomial sign test p-value, ties dropped."""
    n = pos + neg
    if n == 0:
        return 1.0
    k = min(pos, neg)
    p = sum(math.comb(n, i) for i in range(0, k + 1)) / 2 ** n
    return min(1.0, 2 * p)


def title_words(t):
    return len(t) if re.search(r"[一-鿿]", t) else len(t.split())


def concentration():
    rows = {}
    for b in blogs():
        posts = read_json(DATA / "hn" / f"{b['key']}.json", [])
        pts = sorted((p["points"] for p in posts), reverse=True)
        total = sum(pts)
        if len(pts) < 20 or not total:
            continue
        k = max(1, len(pts) // 10)
        rows[b["key"]] = {"posts": len(pts), "top10pct_share": round(sum(pts[:k]) / total, 3),
                          "top_post_share": round(pts[0] / total, 3), "median": pts[len(pts) // 2],
                          "p90": pts[len(pts) // 10]}
    return rows


def title_compare(groups, feats):
    """groups: list of (hot_titles, cold_titles) per blog. Returns per-feature summary across blogs."""
    out = {}
    for name, f in list(feats.items()) + [("length", None)]:
        diffs = []
        for hot, cold in groups:
            if name == "length":
                h, c = st.mean(map(title_words, hot)), st.mean(map(title_words, cold))
            else:
                h, c = st.mean(map(f, hot)), st.mean(map(f, cold))
            diffs.append(h - c)
        pos, neg = sum(d > 0 for d in diffs), sum(d < 0 for d in diffs)
        out[name] = {"mean_diff": round(st.mean(diffs), 3), "blogs_hot_higher": pos, "blogs_hot_lower": neg,
                     "p_sign": round(sign_test(pos, neg), 4)}
    return out


def hn_titles():
    groups, per_blog = [], {}
    for b in blogs():
        posts = read_json(DATA / "hn" / f"{b['key']}.json", [])
        if len(posts) < 40:
            continue
        posts = sorted(posts, key=lambda p: -p["points"])
        hot = [p["title"] for p in posts[: len(posts) // 4]]
        cold = [p["title"] for p in posts[len(posts) // 2:]]
        groups.append((hot, cold))
        per_blog[b["key"]] = len(posts)
    return {"blogs": per_blog, "features": title_compare(groups, EN_TITLE)}


def pair_codes(sample_file="sample.json"):
    sample = read_json(DATA / sample_file, [])
    codes = read_json(DATA / "codes.json", {})
    pairs = defaultdict(dict)
    for p in sample:
        if p["post_id"] in codes:
            pairs[p["pair"]][p["group"]] = {**p, **codes[p["post_id"]]}
    pairs = {k: v for k, v in pairs.items() if "hot" in v and "cold" in v}
    res = {"n_pairs": len(pairs), "scores": {}, "categories": {}, "by_field": {}}

    def score_summary(items):
        out = {}
        for s in SCORES:
            d = [v["hot"][s] - v["cold"][s] for v in items]
            pos, neg = sum(x > 0 for x in d), sum(x < 0 for x in d)
            out[s] = {"hot_mean": round(st.mean(v["hot"][s] for v in items), 2),
                      "cold_mean": round(st.mean(v["cold"][s] for v in items), 2),
                      "pairs_hot_higher": pos, "pairs_hot_lower": neg, "ties": len(d) - pos - neg,
                      "p_sign": round(sign_test(pos, neg), 4)}
        # named concept is free text: present vs absent
        d = [bool(v["hot"]["named_concept"].strip()) - bool(v["cold"]["named_concept"].strip()) for v in items]
        pos, neg = sum(x > 0 for x in d), sum(x < 0 for x in d)
        out["named_concept"] = {"hot_mean": round(st.mean(bool(v["hot"]["named_concept"].strip()) for v in items), 2),
                                "cold_mean": round(st.mean(bool(v["cold"]["named_concept"].strip()) for v in items), 2),
                                "pairs_hot_higher": pos, "pairs_hot_lower": neg, "ties": len(d) - pos - neg,
                                "p_sign": round(sign_test(pos, neg), 4)}
        for name, f in DERIVED.items():
            d = [f(v["hot"]) - f(v["cold"]) for v in items]
            pos, neg = sum(x > 0 for x in d), sum(x < 0 for x in d)
            out[name] = {"hot_mean": round(st.mean(f(v["hot"]) for v in items), 2),
                         "cold_mean": round(st.mean(f(v["cold"]) for v in items), 2),
                         "pairs_hot_higher": pos, "pairs_hot_lower": neg, "ties": len(d) - pos - neg,
                         "p_sign": round(sign_test(pos, neg), 4), "derived": True}
        d = [math.log10(v["hot"]["words"] + 1) - math.log10(v["cold"]["words"] + 1) for v in items]
        pos, neg = sum(x > 0 for x in d), sum(x < 0 for x in d)
        out["log_words"] = {"hot_mean": round(st.median(v["hot"]["words"] for v in items)),
                            "cold_mean": round(st.median(v["cold"]["words"] for v in items)),
                            "pairs_hot_higher": pos, "pairs_hot_lower": neg, "ties": len(d) - pos - neg,
                            "p_sign": round(sign_test(pos, neg), 4), "note": "means are medians of word counts"}
        return out

    items = list(pairs.values())
    if not items:
        return res
    res["scores"] = score_summary(items)
    for c in CATS:
        hot, cold = Counter(v["hot"][c] for v in items), Counter(v["cold"][c] for v in items)
        res["categories"][c] = {k: {"hot": hot.get(k, 0), "cold": cold.get(k, 0)} for k in sorted(set(hot) | set(cold))}
    dom_hot, dom_cold = Counter(), Counter()
    for v in items:
        dom_hot.update(v["hot"]["life_domains"])
        dom_cold.update(v["cold"]["life_domains"])
    res["categories"]["life_domains"] = {k: {"hot": dom_hot.get(k, 0), "cold": dom_cold.get(k, 0)}
                                         for k in sorted(set(dom_hot) | set(dom_cold))}
    fields = defaultdict(list)
    for v in items:
        fields["finance_econ" if v["hot"]["field"].startswith(("finance", "econ", "ideas-econ")) else "tech"].append(v)
    for f, its in fields.items():
        res["by_field"][f] = {"n_pairs": len(its), "scores": score_summary(its)}
    res["examples"] = [{"pair": k, "hot": {x: v["hot"][x] for x in ("url", "hn_title", "points", "core_claim", "named_concept", "share_reason", "emotion")},
                        "cold": {x: v["cold"][x] for x in ("url", "hn_title", "points", "core_claim", "named_concept", "share_reason", "emotion")}}
                       for k, v in sorted(pairs.items())]
    return res


def ruanyifeng():
    posts = [p for p in read_json(DATA / "ruanyifeng.json", []) if p.get("comments") is not None and not p["weekly"]]
    if not posts:
        return {}
    posts.sort(key=lambda p: -p["comments"])
    by_era = defaultdict(list)
    for p in posts:
        by_era[(p["year"] - 2004) // 4].append(p)
    groups = []
    for era, ps in by_era.items():  # compare inside 4-year eras: the blog's readership changed a lot
        if len(ps) < 40:
            continue
        ps = sorted(ps, key=lambda p: -p["comments"])
        groups.append(([p["title"] for p in ps[: len(ps) // 4]], [p["title"] for p in ps[len(ps) // 2:]]))
    c = [p["comments"] for p in posts]
    return {"posts": len(posts), "median_comments": st.median(c), "p90": sorted(c, reverse=True)[len(c) // 10],
            "max": c[0], "eras_compared": len(groups), "title_features": title_compare(groups, ZH_TITLE),
            "top30": [{"title": p["title"], "comments": p["comments"], "year": p["year"], "url": p["url"]} for p in posts[:30]]}


def is_finance(field):
    return field.startswith(("finance", "econ", "ideas-econ"))


def top_posts(n=30):
    """Highest-scoring HN posts across blogs, split into tech and economics/finance."""
    rows = {"tech": [], "finance_econ": []}
    for b in blogs():
        for p in read_json(DATA / "hn" / f"{b['key']}.json", []):
            rows["finance_econ" if is_finance(b["field"]) else "tech"].append(
                {"blog": b["name"], "title": p["title"], "points": p["points"], "comments": p["comments"],
                 "first_submitted": p["first_submitted"], "url": p["url"]})
    return {k: sorted(v, key=lambda r: -r["points"])[:n] for k, v in rows.items()}


def main():
    res = {"concentration": concentration(), "top_posts": top_posts(), "hn_titles": hn_titles(),
           "pairs": pair_codes(), "pairs_zh": pair_codes("sample_zh.json"), "ruanyifeng": ruanyifeng()}
    write_json(OUT / "results.json", res)
    print("concentration:", len(res["concentration"]), "blogs; title blogs:", len(res["hn_titles"]["blogs"]),
          "; coded pairs:", res["pairs"]["n_pairs"], "; ryf posts:", res["ruanyifeng"].get("posts"))


if __name__ == "__main__":
    main()
