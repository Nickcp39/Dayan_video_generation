"""Step 8: score each system on dev or test.

  pair      blind A/B test: the judge sees the real title and one generated title for the
            same topic (random order) plus 15 training titles, and picks the real one.
            Judge accuracy 50% = indistinguishable; fool rate = 1 - accuracy.
  attr      channel attribution: real and generated titles shuffled together, the judge
            assigns each to one of the 9 channels (8 training titles shown per channel).
  thesis    generated thesis vs the gold thesis from s4 (0-3, 3 = same claim).
  copy      max char/word 3-gram Jaccard to any training title (flag >= 0.5): imitation
            should come from style, not from reusing old titles.
  style     length / question / number / bracket rates vs the real titles.

Writes out/results/<set>/<key>.json (per video) and out/results/<set>/summary.json.
"""
import argparse
import hashlib
import random
import re
from statistics import mean

from common import (DATA, OUT, SEED, jaccard, llm, load_channels, ngrams, prompt, read_json, run_parallel,
                    selected, split_path, title_features, write_json)

SYSTEM = "你是严格的内容评审，熟悉各国 YouTube 财经频道的标题风格。严格按要求的 JSON 结构输出。"
PAIR_SCHEMA = {"type": "object", "required": ["items"], "properties": {"items": {"type": "array", "items": {
    "type": "object", "required": ["id", "real", "confidence", "reason"],
    "properties": {"id": {"type": "string"}, "real": {"type": "string", "enum": ["A", "B"]},
                   "confidence": {"type": "integer", "minimum": 1, "maximum": 5}, "reason": {"type": "string"}}}}}}
ATTR_SCHEMA = {"type": "object", "required": ["items"], "properties": {"items": {"type": "array", "items": {
    "type": "object", "required": ["n", "channel"],
    "properties": {"n": {"type": "integer"}, "channel": {"type": "string"}}}}}}
THESIS_SCHEMA = {"type": "object", "required": ["items"], "properties": {"items": {"type": "array", "items": {
    "type": "object", "required": ["id", "score", "reason"],
    "properties": {"id": {"type": "string"}, "score": {"type": "integer", "minimum": 0, "maximum": 3},
                   "reason": {"type": "string"}}}}}}
COPY_FLAG = 0.5        # reuses an old title's frame (the creator's own formula)
NEAR_VERBATIM = 0.8    # an old title with a word or number swapped: counts as copying


def seeded(*parts):
    return random.Random(hashlib.sha256("|".join(map(str, (SEED,) + parts)).encode()).hexdigest())


def train_refs(key, n, salt):
    train = read_json(split_path(key))["train_titles"]
    return [e["title"] for e in seeded(key, salt).sample(train, min(n, len(train)))]


# Judge calls are built as tasks first and run in one pool across channels and systems.

def pair_tasks(ch, system, ids, real, gen, topic):
    refs = "\n".join(f"- {t}" for t in train_refs(ch["key"], 15, "pair"))
    order = {v: seeded(ch["key"], system, v).random() < 0.5 for v in ids}   # True -> real is A
    tasks = []
    for i in range(0, len(ids), 10):
        pairs = "\n".join(
            f"### id: {v}\n选题：{topic[v]}\nA：{real[v] if order[v] else gen[v]}\nB：{gen[v] if order[v] else real[v]}\n"
            for v in ids[i:i + 10])
        tasks.append({"kind": "pair", "key": ch["key"], "system": system, "order": order, "schema": PAIR_SCHEMA,
                      "prompt": prompt("judge_pair", channel=ch["name"], refs=refs, pairs=pairs),
                      "tag": f"pair:{system}:{ch['key']}"})
    return tasks


def thesis_tasks(key, system, ids, gold, cand):
    tasks = []
    for i in range(0, len(ids), 10):
        items = "\n".join(f"### id: {v}\n真实：{gold[v]}\n仿写：{cand[v]}\n" for v in ids[i:i + 10])
        tasks.append({"kind": "thesis", "key": key, "system": system, "schema": THESIS_SCHEMA,
                      "prompt": prompt("judge_thesis", items=items), "tag": f"thesis:{system}:{key}"})
    return tasks


def attr_tasks(chans, entries):
    """Real and generated titles shuffled together; each batch asks for the channel of 20 titles."""
    codes = {f"C{i + 1}": ch["key"] for i, ch in enumerate(chans)}
    block = "\n\n".join(f"{c}（{ch['name']}）\n" + "\n".join(f"- {t}" for t in train_refs(ch["key"], 8, "attr"))
                        for c, ch in zip(codes, chans))
    order = list(range(len(entries)))
    seeded("attr").shuffle(order)
    tasks = []
    for i in range(0, len(order), 20):
        batch = order[i:i + 20]
        titles = "\n".join(f"{j + 1}. {entries[k]['title']}" for j, k in enumerate(batch))
        tasks.append({"kind": "attr", "batch": batch, "codes": codes, "schema": ATTR_SCHEMA,
                      "prompt": prompt("judge_attr", k=len(codes), channels=block, titles=titles), "tag": "attr"})
    return tasks


def run_task(t):
    return llm(t["prompt"], role="judge", system=SYSTEM, schema=t["schema"], tag=t["tag"])["items"]


def collect(tasks, results):
    pair, thesis, attr = {}, {}, {}
    for t, items in zip(tasks, results):
        for it in items or []:
            if t["kind"] == "pair" and it["id"] in t["order"]:
                pair.setdefault((t["key"], t["system"]), {})[it["id"]] = {
                    "judge_correct": it["real"] == ("A" if t["order"][it["id"]] else "B"),
                    "judge_conf": it["confidence"], "judge_reason": it["reason"]}
            elif t["kind"] == "thesis":
                thesis.setdefault((t["key"], t["system"]), {})[it["id"]] = {
                    "thesis_score": it["score"], "thesis_reason": it["reason"]}
            elif t["kind"] == "attr" and 1 <= it["n"] <= len(t["batch"]):
                m = re.search(r"C\d+", it["channel"])
                attr[t["batch"][it["n"] - 1]] = t["codes"].get(m.group(0)) if m else None
    return pair, thesis, attr


def copy_check(title, train_grams):
    """train_grams: list of (title, 3-gram set) for the channel's training titles."""
    g = ngrams(title, 3)
    best, near = 0.0, ""
    for t, tg in train_grams:
        s = jaccard(g, tg)
        if s > best:
            best, near = s, t
    return round(best, 3), near


def style(titles):
    f = [title_features(t) for t in titles]
    n = len(f) or 1
    return {"len": round(mean(x["len"] for x in f), 1) if f else 0,
            "question": round(sum(x["question"] for x in f) / n, 2),
            "number": round(sum(x["number"] for x in f) / n, 2),
            "bracket": round(sum(x["bracket"] for x in f) / n, 2),
            "allcaps": round(sum(x["allcaps_word"] for x in f) / n, 2)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", required=True, choices=["dev", "test"])
    ap.add_argument("--systems", nargs="*")
    args = ap.parse_args()

    chans = load_channels()
    systems = args.systems or sorted(p.name for p in (DATA / "gen" / args.set).iterdir() if p.is_dir())
    per = {}
    attr_entries = []
    for ch in chans:
        key = ch["key"]
        gold = {r["id"]: r for r in read_json(DATA / "decomp" / "content" / f"{key}.json", []) if r["set"] == args.set}
        briefs = read_json(DATA / "briefs" / f"{key}.json", {})
        gens = {s: read_json(DATA / "gen" / args.set / s / f"{key}.json", {}) for s in systems}
        ids = [v for v in selected(key)[args.set] if v in briefs and v in gold and all(v in g for g in gens.values())]
        if not ids:
            continue
        per[key] = {"ch": ch, "ids": ids, "gold": gold, "briefs": briefs, "gens": gens}
        for v in ids:
            attr_entries.append({"key": key, "system": "real", "id": v, "title": gold[v]["title"]})
            for s in systems:
                attr_entries.append({"key": key, "system": s, "id": v, "title": gens[s][v]["title"]})

    tasks = attr_tasks([p["ch"] for p in per.values()], attr_entries) if attr_entries else []
    for key, p in per.items():
        real = {v: p["gold"][v]["title"] for v in p["ids"]}
        topic = {v: p["briefs"][v]["topic"] for v in p["ids"]}
        for s in systems:
            tasks += pair_tasks(p["ch"], s, p["ids"], real, {v: p["gens"][s][v]["title"] for v in p["ids"]}, topic)
            tasks += thesis_tasks(key, s, p["ids"], {v: p["gold"][v]["thesis"] for v in p["ids"]},
                                  {v: p["gens"][s][v]["thesis"] for v in p["ids"]})
    pair_res, thesis_res, attr = collect(tasks, run_parallel(run_task, tasks, label=f"judge {args.set}"))
    attr_hit = {}
    for i, e in enumerate(attr_entries):
        if i in attr:
            attr_hit[(e["key"], e["system"], e["id"])] = attr[i] == e["key"]

    summary = {"set": args.set, "systems": systems, "channels": {}}
    for key, p in per.items():
        ch, ids, gold, briefs, gens = p["ch"], p["ids"], p["gold"], p["briefs"], p["gens"]
        train_grams = [(e["title"], ngrams(e["title"], 3)) for e in read_json(split_path(key))["train_titles"]]
        real = {v: gold[v]["title"] for v in ids}
        topic = {v: briefs[v]["topic"] for v in ids}
        # Briefs are transcript-derived, so only the one-line topic goes into the published results.
        items = {v: {"id": v, "upload_date": gold[v].get("upload_date"), "topic": topic[v],
                     "real_title": real[v], "real_thesis": gold[v]["thesis"], "real_thesis_type": gold[v]["thesis_type"],
                     "real_title_thesis": gold[v]["title_thesis"], "real_attr_correct": attr_hit.get((key, "real", v)),
                     "systems": {}} for v in ids}
        sums = {"real_style": style(real.values()), "real_attr_acc": None}
        hits = [attr_hit[(key, "real", v)] for v in ids if (key, "real", v) in attr_hit]
        sums["real_attr_acc"] = round(sum(hits) / len(hits), 2) if hits else None
        for s in systems:
            gen_title = {v: gens[s][v]["title"] for v in ids}
            pair = pair_res.get((key, s), {})
            thesis = thesis_res.get((key, s), {})
            rows = []
            for v in ids:
                sim, near = copy_check(gen_title[v], train_grams)
                row = {"title": gen_title[v], "thesis": gens[s][v]["thesis"], "candidates": gens[s][v].get("candidates", []),
                       **pair.get(v, {}), **thesis.get(v, {}), "attr_correct": attr_hit.get((key, s, v)),
                       "copy_sim": sim, "copy_nearest": near if sim >= COPY_FLAG else "",
                       "real_overlap": round(jaccard(ngrams(gen_title[v], 2), ngrams(real[v], 2)), 3)}
                items[v]["systems"][s] = row
                rows.append(row)
            judged = [r for r in rows if "judge_correct" in r]
            scored = [r for r in rows if "thesis_score" in r]
            attrd = [r for r in rows if r["attr_correct"] is not None]
            sums[s] = {
                "n": len(rows),
                "judge_acc": round(sum(r["judge_correct"] for r in judged) / len(judged), 2) if judged else None,
                "fool_rate": round(1 - sum(r["judge_correct"] for r in judged) / len(judged), 2) if judged else None,
                "thesis_mean": round(mean(r["thesis_score"] for r in scored), 2) if scored else None,
                "thesis_ge2": round(sum(r["thesis_score"] >= 2 for r in scored) / len(scored), 2) if scored else None,
                "attr_acc": round(sum(r["attr_correct"] for r in attrd) / len(attrd), 2) if attrd else None,
                "copy_flags": sum(r["copy_sim"] >= COPY_FLAG for r in rows),
                "near_verbatim": sum(r["copy_sim"] >= NEAR_VERBATIM for r in rows),
                "real_overlap": round(mean(r["real_overlap"] for r in rows), 3),
                "style": style(gen_title.values()),
            }
        write_json(OUT / "results" / args.set / f"{key}.json", {"key": key, "systems": systems, "items": list(items.values())})
        summary["channels"][key] = sums
        print(key, {s: {k: sums[s][k] for k in ("fool_rate", "thesis_mean", "attr_acc", "copy_flags")} for s in systems})
    write_json(OUT / "results" / args.set / "summary.json", summary)


if __name__ == "__main__":
    main()
