"""Step 1: list every long-form upload per channel, newest first.

Uses the channel's /videos tab (Shorts and live streams live in other tabs) and asks
YouTube for the channel's own language, so Japanese titles come back in Japanese
instead of the auto-translated English the first scrape got.
"""
import argparse
import json
import time

from common import DATA, load_channels, write_json, ytdlp


def flat_listing(channel_id, lang):
    url = f"https://www.youtube.com/channel/{channel_id}/videos"
    p = ytdlp(["--flat-playlist", "-J", "--extractor-args", f"youtube:lang={lang}", url], timeout=3600)
    if p.returncode != 0 or not p.stdout.strip():
        print(f"{channel_id} ({lang}): FAILED {p.stderr[-300:]}")
        return None
    return json.loads(p.stdout)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", help="channel keys")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    for ch in load_channels(replicate_only=False, only=args.only):
        out = DATA / "listing" / f"{ch['key']}.json"
        if out.exists() and not args.force:
            print(f"{ch['key']}: cached")
            continue
        d = flat_listing(ch["channel_id"], ch["yt_lang"])
        if d is None:
            continue
        # yt-dlp only parses view counts from the English page; titles come from the native-language page.
        en = d if ch["yt_lang"] == "en" else flat_listing(ch["channel_id"], "en")
        en_by_id = {e["id"]: e for e in (en or {}).get("entries") or [] if e.get("id")}
        entries = []
        for i, e in enumerate(d.get("entries") or []):
            if not e.get("id"):
                continue
            alt = en_by_id.get(e["id"], {})
            entries.append({"rank": i, "id": e["id"], "title": e.get("title"),
                            "views": e.get("view_count") or alt.get("view_count"),
                            "duration": e.get("duration") or alt.get("duration")})
        write_json(out, {"key": ch["key"], "channel": d.get("channel") or ch["name"],
                         "followers": d.get("channel_follower_count") or (en or {}).get("channel_follower_count"),
                         "fetched": time.strftime("%Y-%m-%d"), "entries": entries})
        print(f"{ch['key']}: {len(entries)} videos, followers={d.get('channel_follower_count')}")


if __name__ == "__main__":
    main()
