"""Step 3: fetch metadata and subtitles (text only, never the video) for the selected videos.

For each set, walk the seeded candidate list and keep the first videos that have a
subtitle track in the channel's language, until the quota is met. Track preference:
creator-uploaded subtitles, then YouTube's speech recognition of the original audio.
Raw subtitle files and transcripts stay in data/ (git-ignored).
"""
import argparse
import json
import random
import re
import time
from pathlib import Path

from common import DATA, QUOTA, SETS, clean_description, load_channels, read_json, split_path, write_json, ytdlp

BOT_WALL = ("Sign in to confirm", "HTTP Error 429", "Too Many Requests")


def parse_json3(path):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    lines = []
    for ev in d.get("events", []):
        text = "".join(s.get("utf8", "") for s in ev.get("segs", []) or []).strip()
        if text and (not lines or lines[-1] != text):
            lines.append(text)
    return "\n".join(lines)


def parse_vtt(path):
    lines = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip() or "-->" in line or line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")):
            continue
        text = re.sub(r"<[^>]+>", "", line).strip()
        if text and (not lines or lines[-1] != text):
            lines.append(text)
    return "\n".join(lines)


def pick_track(info, lang):
    """Best subtitle track: creator-uploaded > '<lang>-orig' speech recognition > plain '<lang>' auto track."""
    manual = [k for k in (info.get("subtitles") or {}) if k.lower().startswith(lang) and k != "live_chat"]
    if manual:
        return "manual", sorted(manual, key=len)[0]
    auto = list((info.get("automatic_captions") or {}).keys())
    orig = [k for k in auto if k.lower().startswith(lang) and k.endswith("-orig")]
    if orig:
        return "auto", orig[0]
    if lang in auto:
        return "auto", lang
    return None, None


def fetch_one(ch, vid):
    """Returns 'ok', 'nosubs' or an error string. One page fetch plus one subtitle request per video."""
    sub_dir = DATA / "subs" / ch["key"]
    if (sub_dir / f"{vid}.txt").exists():
        return "ok"
    raw_dir = DATA / "subs_raw" / ch["key"]
    raw_dir.mkdir(parents=True, exist_ok=True)
    lang = ch["lang"]
    info_path = raw_dir / f"{vid}.info.json"
    if not info_path.exists():
        p = ytdlp(["-j", "--skip-download", "--extractor-args", f"youtube:lang={ch['yt_lang']}",
                   f"https://www.youtube.com/watch?v={vid}"], timeout=600)
        if not p.stdout.strip():
            return "error: " + p.stderr.strip()[-300:]
        info_path.write_text(p.stdout.splitlines()[0], encoding="utf-8")
    info = json.loads(info_path.read_text(encoding="utf-8"))
    kind, sub_key = pick_track(info, lang)
    write_json(DATA / "meta" / ch["key"] / f"{vid}.json", {
        "id": vid, "title": info.get("title"), "upload_date": info.get("upload_date"),
        "views": info.get("view_count"), "likes": info.get("like_count"), "comments": info.get("comment_count"),
        "duration": info.get("duration"), "language": info.get("language"),
        "description": clean_description(info.get("description")), "tags": (info.get("tags") or [])[:20],
        "chapters": [c.get("title") for c in info.get("chapters") or []],
        "sub_key": sub_key, "sub_kind": kind,
    })
    if not sub_key:
        info_path.unlink()
        return "nosubs"
    p = ytdlp(["--load-info-json", str(info_path), "--skip-download",
               "--write-subs" if kind == "manual" else "--write-auto-subs",
               "--sub-langs", re.escape(sub_key), "--sub-format", "json3/vtt/best",
               "-o", str(raw_dir / "%(id)s.%(ext)s")], timeout=600)
    files = list(raw_dir.glob(f"{vid}.{sub_key}.json3")) + list(raw_dir.glob(f"{vid}.{sub_key}.vtt"))
    if not files:
        return "error: subtitle download failed: " + p.stderr.strip()[-300:]
    info_path.unlink()
    chosen = files[0]
    text = parse_json3(chosen) if chosen.suffix == ".json3" else parse_vtt(chosen)
    if len(text) < 300:
        return "nosubs"
    sub_dir.mkdir(parents=True, exist_ok=True)
    (sub_dir / f"{vid}.txt").write_text(text, encoding="utf-8")
    return "ok"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--sets", nargs="*", default=list(SETS))
    args = ap.parse_args()

    walls = 0
    for ch in load_channels(only=args.only):
        split = read_json(split_path(ch["key"]))
        if not split:
            print(f"{ch['key']}: no split, run s2 first")
            continue
        sel_path = DATA / "split" / f"{ch['key']}.selected.json"
        sel = read_json(sel_path, {s: [] for s in SETS})
        skipped = sel.setdefault("skipped", {})
        for s in args.sets:
            for vid in split["candidates"][s]:
                if len(sel[s]) >= QUOTA[s]:
                    break
                if vid in sel[s] or vid in skipped:
                    continue
                status = fetch_one(ch, vid)
                if status == "ok":
                    sel[s].append(vid)
                    walls = 0
                elif status == "nosubs":
                    skipped[vid] = "nosubs"
                else:
                    print(f"  {ch['key']} {vid}: {status}")
                    if any(w in status for w in BOT_WALL):
                        walls += 1
                        if walls >= 3:
                            write_json(sel_path, sel)
                            raise SystemExit("YouTube 开始拦截（bot check / 429），已保存进度，稍后重跑即可续抓。")
                        time.sleep(60 * walls)
                    else:
                        skipped[vid] = status[:120]
                write_json(sel_path, sel)
                time.sleep(1.5 + random.random() * 2)
            print(f"{ch['key']} {s}: {len(sel[s])}/{QUOTA[s]}", flush=True)


if __name__ == "__main__":
    main()
