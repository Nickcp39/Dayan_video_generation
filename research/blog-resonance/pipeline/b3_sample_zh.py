"""b3 (Chinese pilot): hot/cold pairs from ruanyifeng.com, by comment count.

hot  = the most-commented essays (weekly newsletter issues excluded);
cold = an essay from the same year with comments at or below that year's 25th percentile,
       chosen at random with a fixed seed; both need >= 600 Chinese characters.
Text comes from the cached post pages written by b2.
Output: data/sample_zh.json, data/text/<post_id>.txt.
"""
import hashlib
import random
import re
import sys
from collections import defaultdict

from common import DATA, SEED, read_json, write_json

N_PAIRS = int(sys.argv[1]) if len(sys.argv) > 1 else 16
MIN_CHARS = 600
BODY = re.compile(r'id="main-content">(.*?)<div class="asset-footer"', re.S)


def text_of(p):
    name = "post_" + p["url"].split("/blog/")[1].replace("/", "_")
    html = (DATA / "ryf_raw" / name).read_text(encoding="utf-8")
    m = BODY.search(html)
    if not m:
        return ""
    body = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", m.group(1), flags=re.S)
    body = re.sub(r"</(p|li|h\d|blockquote|pre)>", "\n", body)
    return re.sub(r"[ \t]+", " ", re.sub(r"<[^>]+>", "", body)).strip()


def main():
    rng = random.Random(SEED)
    posts = [p for p in read_json(DATA / "ruanyifeng.json", []) if p.get("comments") is not None and not p["weekly"]
             and p["zh_chars"] >= MIN_CHARS]
    by_year = defaultdict(list)
    for p in posts:
        by_year[p["year"]].append(p)
    q25 = {y: sorted(x["comments"] for x in ps)[len(ps) // 4] for y, ps in by_year.items() if len(ps) >= 12}
    hot = sorted((p for p in posts if p["year"] in q25), key=lambda p: -p["comments"])
    used, pairs = set(), []
    for h in hot:
        if len(pairs) // 2 >= N_PAIRS:
            break
        pool = [c for c in by_year[h["year"]] if c["comments"] <= q25[h["year"]] and c["url"] not in used]
        if not pool:
            continue
        c = rng.choice(pool)
        used.update({h["url"], c["url"]})
        pair_id = f"ruanyifeng-{len(pairs) // 2 + 1}"
        for group, p in (("hot", h), ("cold", c)):
            pid = hashlib.sha1(p["url"].encode("utf-8")).hexdigest()[:12]
            text = text_of(p)
            (DATA / "text").mkdir(parents=True, exist_ok=True)
            (DATA / "text" / f"{pid}.txt").write_text(text, encoding="utf-8")
            pairs.append({"pair": pair_id, "blog": "ruanyifeng", "field": "tech-zh", "group": group, "post_id": pid,
                          "url": p["url"], "hn_title": p["title"], "points": p["comments"], "comments": p["comments"],
                          "submissions": 0, "first_submitted": f"{p['year']}-{p['month']:02d}-01",
                          "words": p["zh_chars"]})
    write_json(DATA / "sample_zh.json", pairs)
    print(f"{len(pairs) // 2} pairs; hot comments {[p['points'] for p in pairs if p['group'] == 'hot']}")


if __name__ == "__main__":
    main()
