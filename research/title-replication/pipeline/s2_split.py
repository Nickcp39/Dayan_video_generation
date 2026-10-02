"""Step 2: time-based train / dev / test split per channel.

The listing is newest-first. The newest 15% of uploads form the test pool, the next
10% the dev pool, everything older is training. The model learns only from training
videos and is scored on later videos it has never seen, the way it would be used:
write the next video for this creator.

Leakage guards: reruns (再放送 / Rerun) are dropped everywhere, and a dev/test video
whose title matches a training title after stripping labels is dropped.

Content candidates are shuffled with a fixed seed; s3 walks each list in order and
keeps the first videos that have subtitles, so selection never looks at content.
"""
import argparse
import random
import re

from common import DATA, OUT, QUOTA, SEED, load_channels, read_json, split_path, write_json

RERUN = re.compile(r"再放送|再掲|re-?run|rebroadcast|【再】|\(再\)", re.I)
MIN_DURATION = 120          # seconds; skip clips and trailers
TEST_FRAC, DEV_FRAC = 0.15, 0.10
TITLE_SAMPLE, TITLE_HITS = 300, 100


def norm(title):
    t = re.sub(r"[【\[(（][^】\])）]*[】\])）]", "", title or "")
    return re.sub(r"[\W_]+", "", t.lower())


def view_pct(pool):
    """Percentile of views within the pool (0-100); None when views are unknown."""
    ranked = sorted((e for e in pool if e.get("views") is not None), key=lambda e: e["views"])
    pct = {e["id"]: round(100 * i / max(1, len(ranked) - 1)) for i, e in enumerate(ranked)}
    return pct


def stratified_order(pool, pct, rng):
    """Shuffle, then interleave view terciles so any prefix is balanced between hits and duds."""
    buckets = [[], [], []]
    for e in pool:
        p = pct.get(e["id"], 50)
        buckets[0 if p >= 67 else 1 if p >= 33 else 2].append(e)
    for b in buckets:
        rng.shuffle(b)
    out = []
    while any(buckets):
        for b in buckets:
            if b:
                out.append(b.pop())
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    args = ap.parse_args()

    manifest = {}
    for ch in load_channels(only=args.only):
        listing = read_json(DATA / "listing" / f"{ch['key']}.json")
        if not listing:
            print(f"{ch['key']}: no listing, run s1 first")
            continue
        entries = listing["entries"]
        reruns = [e for e in entries if RERUN.search(e.get("title") or "")]
        kept = [e for e in entries if e.get("title") and e not in reruns
                and (e.get("duration") is None or e["duration"] >= MIN_DURATION)]

        n = len(kept)
        n_test = max(round(n * TEST_FRAC), QUOTA["test"] + 5)
        n_dev = max(round(n * DEV_FRAC), QUOTA["dev"] + 5)
        test_pool, dev_pool, train_pool = kept[:n_test], kept[n_test:n_test + n_dev], kept[n_test + n_dev:]

        train_norms = {norm(e["title"]) for e in train_pool}
        leaked = [e for e in test_pool + dev_pool if norm(e["title"]) in train_norms]
        test_pool = [e for e in test_pool if e not in leaked]
        dev_pool = [e for e in dev_pool if e not in leaked]

        rng = random.Random(f"{SEED}-{ch['key']}")
        pct = view_pct(train_pool)
        for e in train_pool:
            e["view_pct"] = pct.get(e["id"])

        # Titles to decompose: the training pool's top hits plus a random draw of the rest.
        by_views = sorted(train_pool, key=lambda e: -(e.get("views") or 0))
        hits, rest = by_views[:TITLE_HITS], by_views[TITLE_HITS:]
        title_sample = hits + rng.sample(rest, min(len(rest), TITLE_SAMPLE - len(hits)))

        test_c, dev_c = test_pool[:], dev_pool[:]
        rng.shuffle(test_c)
        rng.shuffle(dev_c)
        split = {
            "key": ch["key"],
            "counts": {"listed": len(entries), "reruns_dropped": len(reruns), "kept": n,
                       "train_pool": len(train_pool), "dev_pool": len(dev_pool), "test_pool": len(test_pool),
                       "dev_test_dropped_as_duplicates": len(leaked)},
            "train_titles": train_pool,
            "title_sample": [e["id"] for e in title_sample],
            "candidates": {"train": [e["id"] for e in stratified_order(train_pool, pct, rng)],
                           "dev": [e["id"] for e in dev_c],
                           "test": [e["id"] for e in test_c]},
            "pools": {"dev": [e["id"] for e in dev_pool], "test": [e["id"] for e in test_pool]},
        }
        write_json(split_path(ch["key"]), split)
        manifest[ch["key"]] = split["counts"]
        print(f"{ch['key']}: {split['counts']}")

    if manifest:
        old = read_json(OUT / "split_counts.json", {})
        old.update(manifest)
        write_json(OUT / "split_counts.json", old)


if __name__ == "__main__":
    main()
