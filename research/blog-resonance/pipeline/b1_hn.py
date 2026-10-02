"""b1: collect every Hacker News submission of each blog's posts and aggregate per post.

Source: HN Algolia search_by_date API (no login). Queries are split into yearly windows
so that no window exceeds the API's 1000-hit pagination cap; a window that still hits
the cap is halved until it fits. Hits are kept only when the URL's host really belongs
to the blog, then grouped by normalized URL.

Per post: max points over submissions (popularity), total comments, number of submissions,
first submission date, the title of the top submission.
Output: data/hn/<key>.json (one list of posts, sorted by points), out/hn_summary.json.
Re-running reuses cached raw windows in data/hn_raw/.
"""
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "hn_raw"
OUT = ROOT / "data" / "hn"
API = "https://hn.algolia.com/api/v1/search_by_date"
START = int(datetime(2006, 10, 1, tzinfo=timezone.utc).timestamp())
END = int(datetime(2026, 10, 2, tzinfo=timezone.utc).timestamp())
YEAR = 365 * 24 * 3600

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def fetch(params, tries=4):
    url = API + "?" + urllib.parse.urlencode(params)
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return json.load(r)
        except Exception as e:  # network hiccup or rate limit
            if i == tries - 1:
                raise
            time.sleep(5 * (i + 1))


def window(domain, a, b):
    """All story hits for `domain` created in [a, b), splitting the window if it overflows."""
    cache = RAW / domain / f"{a}_{b}.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    d = fetch({"query": domain, "restrictSearchableAttributes": "url", "tags": "story",
               "hitsPerPage": 1000, "numericFilters": f"created_at_i>={a},created_at_i<{b}"})
    if d["nbHits"] > 1000 and b - a > 3600:
        mid = (a + b) // 2
        hits = window(domain, a, mid) + window(domain, mid, b)
    else:
        hits = [{k: h.get(k) for k in ("objectID", "title", "url", "points", "num_comments", "created_at_i")}
                for h in d["hits"]]
        time.sleep(0.4)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(hits, ensure_ascii=False), encoding="utf-8")
    return hits


def host_ok(url, domains):
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in domains)


def normalize(url):
    s = urllib.parse.urlsplit(url)
    host = (s.hostname or "").lower()
    host = host[4:] if host.startswith("www.") else host
    path = s.path.rstrip("/")
    for suffix in ("/index.html", "/index.htm"):
        if path.endswith(suffix):
            path = path[: -len(suffix)]
    if path.endswith("/amp"):  # AMP variant of the same post
        path = path[:-4]
    if path.endswith(".htm"):  # paulgraham.com/genius.htm and /genius.html are the same essay
        path += "l"
    return host + path


def collect(blog):
    hits = []
    for domain in blog["domains"]:
        a = START
        while a < END:
            hits += window(domain, a, min(a + YEAR, END))
            a += YEAR
    posts = {}
    for h in hits:
        if not h.get("url") or not host_ok(h["url"], blog["domains"]):
            continue
        key = normalize(h["url"])
        if key.count("/") == 0:  # homepage, not a post
            continue
        p = posts.setdefault(key, {"url_key": key, "url": h["url"], "points": 0, "comments": 0,
                                   "submissions": 0, "first_submitted": h["created_at_i"], "title": h["title"],
                                   "hn_ids": []})
        pts = h.get("points") or 0
        p["comments"] += h.get("num_comments") or 0
        p["submissions"] += 1
        p["hn_ids"].append(h["objectID"])
        p["first_submitted"] = min(p["first_submitted"], h["created_at_i"])
        if pts > p["points"]:
            p["points"], p["title"], p["url"] = pts, h["title"], h["url"]
    out = sorted(posts.values(), key=lambda p: -p["points"])
    for p in out:
        p["first_submitted"] = datetime.fromtimestamp(p["first_submitted"], timezone.utc).strftime("%Y-%m-%d")
    return len(hits), out


def main():
    blogs = json.loads((ROOT / "blogs.json").read_text(encoding="utf-8"))
    only = set(sys.argv[1:])
    summary = {}
    OUT.mkdir(parents=True, exist_ok=True)
    for b in blogs:
        if only and b["key"] not in only:
            continue
        n_hits, posts = collect(b)
        (OUT / f"{b['key']}.json").write_text(json.dumps(posts, ensure_ascii=False, indent=1), encoding="utf-8")
        pts = sorted((p["points"] for p in posts), reverse=True)
        median = pts[len(pts) // 2] if pts else 0
        summary[b["key"]] = {"name": b["name"], "field": b["field"], "raw_hits": n_hits, "posts": len(posts),
                             "posts_ge_100": sum(x >= 100 for x in pts), "top_points": pts[0] if pts else 0,
                             "median_points": median, "total_points": sum(pts)}
        s = summary[b["key"]]
        print(f"{b['key']:22} hits={n_hits:5d} posts={s['posts']:5d} >=100={s['posts_ge_100']:4d} "
              f"top={s['top_points']:5d} median={median:4d}")
    if not only:
        (ROOT / "out" / "hn_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
