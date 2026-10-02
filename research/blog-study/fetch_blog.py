"""Download every post on yanda-cheng.com and convert it to plain text.

The blog list page renders from three config JSONs; posts live at posts/<file>.
Output: raw/*.json (index), raw/html/<file>, raw/text/<file>.md (front matter + headings/paragraphs/lists/tables).
Standard library only.
"""
import json
import re
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

SITE = "https://yanda-cheng.com"
ROOT = Path(__file__).parent / "raw"
CONFIGS = ["article_metadata", "article_tags", "category_macro_map"]

BLOCK = {"h1": "# ", "h2": "## ", "h3": "### ", "h4": "#### ", "p": "", "li": "- ", "blockquote": "> ",
         "td": "| ", "th": "| ", "figcaption": "图注：", "pre": ""}
SKIP = {"script", "style", "nav", "aside", "noscript", "head"}


def get(url):
    with urllib.request.urlopen(url, timeout=40) as r:
        return r.read()


class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.out, self.buf, self.skip, self.stack = [], [], 0, []

    def flush(self):
        t = re.sub(r"\s+", " ", "".join(self.buf)).strip()
        if t and self.stack:
            self.out.append(BLOCK[self.stack[-1]] + t)
        self.buf = []

    def handle_starttag(self, tag, attrs):
        if tag in SKIP:
            self.skip += 1
        if self.skip:
            return
        if tag in BLOCK:
            self.flush()
            self.stack.append(tag)
        if tag == "br":
            self.buf.append(" ")
        if tag == "tr":
            self.flush()
            self.out.append("")

    def handle_endtag(self, tag):
        if tag in SKIP:
            self.skip = max(0, self.skip - 1)
            return
        if self.skip:
            return
        if tag in BLOCK and self.stack:
            self.flush()
            if tag in self.stack:
                self.stack.remove(tag)

    def handle_data(self, d):
        if not self.skip and self.stack:
            self.buf.append(d)


def main():
    (ROOT / "html").mkdir(parents=True, exist_ok=True)
    (ROOT / "text").mkdir(exist_ok=True)
    for name in CONFIGS:
        (ROOT / f"{name}.json").write_bytes(get(f"{SITE}/config/{name}.json"))
    meta = json.loads((ROOT / "article_metadata.json").read_text(encoding="utf-8"))

    for f, m in sorted(meta.items(), key=lambda kv: kv[1].get("date", ""), reverse=True):
        raw = get(f"{SITE}/posts/{f}")
        (ROOT / "html" / f).write_bytes(raw)
        p = TextParser()
        p.feed(raw.decode("utf-8", errors="replace"))
        p.flush()
        body = "\n\n".join(l for l in p.out if l.strip() and "Leave a comment" not in l)
        head = (f"---\nfile: {f}\nurl: {SITE}/posts/{f}\ndate: {m.get('date')}\n"
                f"title: {m.get('title')}\nsummary: {m.get('summary')}\n---\n\n")
        (ROOT / "text" / f.replace(".html", ".md")).write_text(head + body + "\n", encoding="utf-8")
        zh = len(re.findall(r"[一-鿿]", body))
        print(f"{m.get('date')}  html={len(raw):6d}B  zh_chars={zh:5d}  {f}")


if __name__ == "__main__":
    main()
