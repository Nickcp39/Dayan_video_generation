"""b2: Chinese tech pilot — every post on ruanyifeng.com/blog with its comment count.

Chinese blogs have no Hacker News equivalent, and Zhihu / Sina counters are closed to
anonymous access, so the popularity signal here is the post's own comment count
("留言（N）"). Monthly archive pages list the posts; each post page is fetched once.
The weekly newsletter issues (weekly-issue-*) are kept but flagged, since they are
link digests rather than essays.

Output: data/ruanyifeng.json. Raw pages are cached in data/ryf_raw/ so re-runs resume.
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "ryf_raw"
BASE = "https://www.ruanyifeng.com/blog"
UA = {"User-Agent": "Mozilla/5.0 (research; contact via github.com/nickcp39)"}

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def get(url, name):
    cache = RAW / name
    if cache.exists():
        return cache.read_text(encoding="utf-8")
    url = urllib.parse.quote(url, safe=":/?=&%#")  # a few old slugs contain spaces
    for i in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
                text = r.read().decode("utf-8", errors="replace")
            break
        except urllib.error.HTTPError as e:
            if e.code == 404:
                text = ""
                break
            time.sleep(5 * (i + 1))
        except Exception:
            time.sleep(5 * (i + 1))
    else:
        raise RuntimeError(f"failed: {url}")
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(text, encoding="utf-8")
    time.sleep(0.6)
    return text


# Month pages show the newest post in full and list the rest as plain links.
LINK = r'href="(https?://www\.ruanyifeng\.com/blog/{y}/{m}/[^"#/]+\.html)"[^>]*>([^<]*)</a>'
TITLE = re.compile(r'<h1 id="page-title"[^>]*>(.*?)</h1>', re.S)
COMMENTS = re.compile(r"留言（(\d+)(?:条)?）")
BODY = re.compile(r'id="main-content">(.*?)<div class="asset-footer"', re.S)


def main():
    posts = {}
    for year in range(2003, 2027):
        for month in range(1, 13):
            if (year, month) < (2003, 12) or (year, month) > (2026, 9):
                continue
            html = get(f"{BASE}/{year}/{month:02d}/", f"month_{year}_{month:02d}.html")
            for url, _ in re.findall(LINK.format(y=year, m=f"{month:02d}"), html):
                url = url.replace("http://", "https://")
                posts.setdefault(url, {"url": url, "year": year, "month": month})
        print(f"{year}: {len(posts)} posts listed", flush=True)

    out = []
    for i, p in enumerate(sorted(posts.values(), key=lambda p: p["url"])):
        name = "post_" + p["url"].split("/blog/")[1].replace("/", "_")
        try:
            html = get(p["url"], name)
        except RuntimeError as e:  # keep going; the post is recorded without a count
            print(f"  ! {e}", flush=True)
            html = ""
        t = TITLE.search(html)
        p["title"] = re.sub(r"<[^>]+>", "", t.group(1)).strip() if t else ""
        c = COMMENTS.search(html)
        body = BODY.search(html)
        text = re.sub(r"<[^>]+>", "", body.group(1)) if body else ""
        p["comments"] = int(c.group(1)) if c else None
        p["zh_chars"] = len(re.findall(r"[一-鿿]", text))
        p["weekly"] = "weekly-issue" in p["url"]
        out.append(p)
        if (i + 1) % 100 == 0:
            print(f"  fetched {i + 1}/{len(posts)}", flush=True)
    (ROOT / "data" / "ruanyifeng.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"done: {len(out)} posts, {sum(p['comments'] is not None for p in out)} with comment counts")


if __name__ == "__main__":
    main()
