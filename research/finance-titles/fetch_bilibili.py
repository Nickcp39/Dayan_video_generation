"""Fetch all video titles from a Bilibili uploader space via wbi-signed API."""
import hashlib
import json
import sys
import time
import urllib.parse
import urllib.request

MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
    27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
    37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4,
    22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52,
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Referer": "https://www.bilibili.com/",
}


def get_json(url, mid=None):
    headers = dict(HEADERS)
    headers["Cookie"] = f"buvid3={globals().get('BUVID3', '')}; b_nut={int(time.time())}"
    if mid:
        headers["Referer"] = f"https://space.bilibili.com/{mid}/video"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_buvid3():
    data = get_json("https://api.bilibili.com/x/frontend/finger/spi")
    return data["data"]["b_3"]


def get_mixin_key():
    nav = get_json("https://api.bilibili.com/x/web-interface/nav")
    img_key = nav["data"]["wbi_img"]["img_url"].rsplit("/", 1)[1].split(".")[0]
    sub_key = nav["data"]["wbi_img"]["sub_url"].rsplit("/", 1)[1].split(".")[0]
    raw = img_key + sub_key
    return "".join(raw[i] for i in MIXIN_KEY_ENC_TAB)[:32]


def sign(params, mixin_key):
    params = dict(params)
    params["wts"] = int(time.time())
    params = {k: "".join(c for c in str(v) if c not in "!'()*")
              for k, v in sorted(params.items())}
    query = urllib.parse.urlencode(params)
    params["wbi_sign"] = hashlib.md5((query + mixin_key).encode()).hexdigest()
    return urllib.parse.urlencode(params)


def fetch_space(mid, mixin_key, out_path):
    page, total, rows = 1, None, []
    while True:
        qs = sign({"mid": mid, "ps": 30, "tid": 0, "pn": page,
                   "order": "pubdate", "platform": "web"}, mixin_key)
        url = f"https://api.bilibili.com/x/space/wbi/arc/search?{qs}"
        data = get_json(url, mid=mid)
        if data.get("code") != 0:
            print(f"  page {page}: API error {data.get('code')} {data.get('message')}")
            break
        lst = data["data"]["list"]["vlist"]
        if total is None:
            total = data["data"]["page"]["count"]
            print(f"  total videos: {total}")
        for v in lst:
            rows.append((v["title"], v["bvid"], v.get("play"), v.get("created")))
        if not lst or len(rows) >= total:
            break
        page += 1
        time.sleep(1.2)
    with open(out_path, "w", encoding="utf-8") as f:
        for t, bvid, play, created in rows:
            f.write(f"{t}\t{bvid}\t{play}\t{created}\n")
    print(f"  saved {len(rows)} -> {out_path}")


if __name__ == "__main__":
    targets = json.loads(sys.argv[1])  # {"name": mid, ...}
    BUVID3 = get_buvid3()
    globals()["BUVID3"] = BUVID3
    key = get_mixin_key()
    for name, mid in targets.items():
        print(f"[{name}] mid={mid}")
        fetch_space(mid, key, f"research/finance-titles/raw/bili_{name}.tsv")
        time.sleep(2)
