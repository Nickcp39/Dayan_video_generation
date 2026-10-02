"""b3: pick hot/cold post pairs inside each blog and fetch their text.

Design: compare posts by the *same author*, so fame, audience and writing skill are held
roughly constant. For each eligible blog:
  hot  = its highest-scoring HN posts (points >= 50, i.e. reached the front page), in rank order;
  cold = a post by the same blog that was submitted to HN but stayed under 10 points,
         first submitted within two years of its hot partner (HN's audience grew a lot,
         so era matters), taken in a fixed pseudo-random order (hash of URL and seed).
A pair is kept only when both pages can be fetched and have >= 300 words of text.

Output: data/sample.json (pairs with metadata), data/text/<post_id>.txt.
"""
import hashlib
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from html.parser import HTMLParser

from common import DATA, SEED, blogs, read_json, write_json

# Economics/finance blogs get one more pair each so they are not swamped by the tech blogs.
PAIRS = {"finance_econ": 4, "tech": 3}
HOT_MIN, COLD_MAX = 50, 10
MIN_WORDS = 300
SKIP_EXT = (".pdf", ".png", ".jpg", ".jpeg", ".gif", ".mp4", ".mp3", ".zip", ".txt")
SKIP_SEGMENTS = {"tag", "tags", "category", "categories", "page", "feed", "search"}
LISTING_PAGES = {"archive", "archives", "about", "subscribe", "articles.html"}
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"}


class Text(HTMLParser):
    """Visible text by block; remembers which blocks sat inside <article>/<main>."""
    SKIP = {"script", "style", "nav", "header", "footer", "aside", "form", "noscript", "svg", "button"}
    BLOCK = {"p", "li", "h1", "h2", "h3", "h4", "blockquote", "pre", "td", "br", "div", "section", "dd"}

    def __init__(self):
        super().__init__()
        self.skip = 0
        self.main = 0
        self.buf = []
        self.all_blocks, self.main_blocks = [], []

    def _flush(self):
        t = re.sub(r"\s+", " ", "".join(self.buf)).strip()
        if t:
            self.all_blocks.append(t)
            if self.main:
                self.main_blocks.append(t)
        self.buf = []

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        if tag in ("article", "main"):
            self.main += 1
        if tag in self.BLOCK:
            self._flush()

    def handle_endtag(self, tag):
        if tag in self.BLOCK:
            self._flush()
        if tag in self.SKIP:
            self.skip = max(0, self.skip - 1)
        if tag in ("article", "main"):
            self._flush()
            self.main = max(0, self.main - 1)

    def handle_data(self, d):
        if not self.skip:
            self.buf.append(d)


def words(text):
    return len(re.findall(r"[A-Za-z0-9']+", text))


# Lines that mark the end of the article body: share widgets, related-post lists, comment
# sections and comment timestamps. Reader comments must not reach the coder, because their
# number and tone would leak how popular the post was.
END_MARKERS = re.compile(
    r"(?i)^(previous post:|next post:|you might also like|maybe others would like this piece|share this:|like this:"
    r"|related posts?|leave a (reply|comment)|discussion about this post|subscribe to new posts"
    r"|\d[\d,]* (responses|comments|replies|thoughts)\b"
    r"|.{0,60}(january|february|march|april|may|june|july|august|september|october|november|december) \d{1,2},? \d{4}"
    r"(,| at) \d{1,2}:\d{2}\s*(am|pm)\s*$"
    r"|.{0,60}\bsays:\s*$)")


def article_only(text):
    lines = text.split("\n")
    seen = 0
    for i, line in enumerate(lines):
        if seen >= 200 and END_MARKERS.match(line.strip()):
            return "\n".join(lines[:i])
        seen += words(line)
    return text


def current_url(url):
    """Where an old post lives now: https first; Coding Horror moved off www.codinghorror.com/blog."""
    m = re.match(r"https?://(?:www\.)?codinghorror\.com/blog/\d{4}/\d{2}/([^/]+)\.html", url)
    if m:
        return f"https://blog.codinghorror.com/{m.group(1)}/"
    return re.sub(r"^http://", "https://", url)


def download(url, tries=2):
    """Page HTML or "" on failure. Follows 307/308, which Python 3.9's urllib does not."""
    url = current_url(url)
    for i in range(tries):
        try:
            for _ in range(5):
                try:
                    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25) as r:
                        return r.read().decode(r.headers.get_content_charset() or "utf-8", errors="replace")
                except urllib.error.HTTPError as e:
                    if e.code in (307, 308) and e.headers.get("Location"):
                        url = urllib.parse.urljoin(url, e.headers["Location"])
                        continue
                    if e.code in (404, 410):
                        return ""
                    raise
        except Exception:
            time.sleep(3 * (i + 1))
    return ""


def fetch_text(url):
    pid = hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]
    cache = DATA / "text" / f"{pid}.txt"
    if cache.exists():
        return pid, cache.read_text(encoding="utf-8")
    raw_cache = DATA / "pages" / f"{pid}.html"
    if raw_cache.exists():
        html = raw_cache.read_text(encoding="utf-8")
    else:
        html = download(url)
        raw_cache.parent.mkdir(parents=True, exist_ok=True)
        raw_cache.write_text(html, encoding="utf-8")
        time.sleep(0.5)
    p = Text()
    try:
        p.feed(html)
        p._flush()
    except Exception:
        pass
    main = article_only("\n".join(p.main_blocks))
    text = main if words(main) >= MIN_WORDS else article_only("\n".join(p.all_blocks))
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(text, encoding="utf-8")
    return pid, text


def usable(post):
    u = post["url"].lower().split("?")[0].split("#")[0]
    segs = [s for s in u.split("://", 1)[-1].split("/")[1:] if s]
    return (not u.endswith(SKIP_EXT) and bool(segs) and not SKIP_SEGMENTS & set(segs)
            and segs[-1] not in LISTING_PAGES)


def title_key(t):
    """Title without year tags, punctuation or case, to catch one post submitted under two URLs."""
    t = re.sub(r"\(\d{4}\)|\[[^\]]*\]", "", t.lower())
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def days(a, b):
    return abs((date.fromisoformat(a) - date.fromisoformat(b)).days)


def main():
    pairs, report = [], {}
    for b in blogs():
        n_pairs = PAIRS["finance_econ" if b["field"].startswith(("finance", "econ", "ideas-econ")) else "tech"]
        posts = [p for p in read_json(DATA / "hn" / f"{b['key']}.json", []) if usable(p)]
        hot = [p for p in posts if p["points"] >= HOT_MIN]
        # A cold post must not be a re-submission of something that did well under another URL.
        did_well = {title_key(p["title"]) for p in posts if p["points"] >= COLD_MAX}
        cold = [p for p in posts if p["points"] < COLD_MAX and title_key(p["title"]) not in did_well]
        # Stable pseudo-random order: a post's position depends only on its URL, so changing a
        # filter later does not reshuffle the remaining candidates.
        cold.sort(key=lambda p: hashlib.sha1(f"{SEED}:{p['url_key']}".encode()).hexdigest())
        if len(hot) < n_pairs or len(cold) < n_pairs:
            report[b["key"]] = f"skip: {len(hot)} hot, {len(cold)} cold"
            continue
        used, kept, misses = set(), 0, 0
        for h in hot:
            if kept >= n_pairs:
                break
            if kept == 0 and misses >= 4:  # site unreachable or blocks scripts: give up on this blog
                break
            hid, htext = fetch_text(h["url"])
            if words(htext) < MIN_WORDS:
                misses += 1
                continue
            partner = None
            for window in (730, 1460):
                for c in cold:
                    if c["url_key"] in used or days(c["first_submitted"], h["first_submitted"]) > window:
                        continue
                    cid, ctext = fetch_text(c["url"])
                    used.add(c["url_key"])
                    if words(ctext) >= MIN_WORDS:
                        partner = (c, cid, ctext)
                        break
                if partner:
                    break
            if not partner:
                continue
            c, cid, ctext = partner
            pair_id = f"{b['key']}-{kept + 1}"
            for group, p, pid, text in (("hot", h, hid, htext), ("cold", c, cid, ctext)):
                pairs.append({"pair": pair_id, "blog": b["key"], "field": b["field"], "group": group, "post_id": pid,
                              "url": p["url"], "hn_title": p["title"], "points": p["points"], "comments": p["comments"],
                              "submissions": p["submissions"], "first_submitted": p["first_submitted"],
                              "words": words(text)})
            kept += 1
        report[b["key"]] = f"{kept} pairs"
        print(f"{b['key']:22} {report[b['key']]}", flush=True)
    write_json(DATA / "sample.json", pairs)
    write_json(DATA / "sample_report.json", report)
    print(f"total {len(pairs)} posts in {len({p['pair'] for p in pairs})} pairs")


if __name__ == "__main__":
    main()
