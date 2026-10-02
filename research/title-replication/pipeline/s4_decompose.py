"""Step 4: semantic decomposition with the LLM.

  titles   every sampled training title -> template, hooks, gap, persona, register, numbers, label
  content  every selected video with a transcript -> topic, thesis, thesis type, angle, beats,
           title/thesis relation. Training videos are the learning material; dev/test
           decompositions are the gold labels the generated thesis is scored against.

Usage: python s4_decompose.py titles|content [--only KEY ...] [--sets train dev test]
"""
import argparse

from common import (DATA, SETS, llm, load_channels, meta, prompt, read_json, run_parallel, selected,
                    split_path, transcript, write_json)

SYSTEM = "你是内容策略研究员，擅长拆解财经视频的标题手法和论证结构。只做客观分析，严格按要求的 JSON 结构输出。"
LANG_NAME = {"zh": "中文", "ja": "日文", "en": "英文"}

HOOKS = ["question", "curiosity_gap", "urgency", "warning", "contrarian", "big_number", "listicle", "personal",
         "reveal", "explainer", "howto_benefit", "conflict", "prediction", "emotion_slang", "series_label"]
PERSONA = ["first_person", "we", "you", "third", "none"]
REGISTER = ["calm", "curious", "urgent", "alarmed", "excited", "angry", "ironic", "playful"]
NUMBERS = ["none", "scale", "precision", "list", "date", "price"]

TITLE_SCHEMA = {
    "type": "object", "required": ["items"],
    "properties": {"items": {"type": "array", "items": {
        "type": "object",
        "required": ["i", "template", "hooks", "gap", "persona", "register", "numbers", "label"],
        "properties": {
            "i": {"type": "integer"},
            "template": {"type": "string"},
            "hooks": {"type": "array", "items": {"type": "string", "enum": HOOKS}},
            "gap": {"type": "string"},
            "persona": {"type": "string", "enum": PERSONA},
            "register": {"type": "string", "enum": REGISTER},
            "numbers": {"type": "string", "enum": NUMBERS},
            "label": {"type": "string"},
        }}}},
}

CONTENT_SCHEMA = {
    "type": "object",
    "required": ["topic", "thesis", "thesis_type", "angle", "beats", "title_thesis", "title_thesis_note",
                 "audience_promise", "stance"],
    "properties": {
        "topic": {"type": "string"},
        "thesis": {"type": "string"},
        "thesis_type": {"type": "string", "enum": ["explain", "predict", "advise", "judge", "expose", "narrate"]},
        "angle": {"type": "string"},
        "beats": {"type": "array", "items": {"type": "string"}},
        "title_thesis": {"type": "string", "enum": ["states", "asks", "teases", "amplifies", "labels"]},
        "title_thesis_note": {"type": "string"},
        "audience_promise": {"type": "string"},
        "stance": {"type": "string", "enum": ["positive", "negative", "neutral", "mixed"]},
    },
}


def do_titles(ch):
    key = ch["key"]
    split = read_json(split_path(key))
    by_id = {e["id"]: e for e in split["train_titles"]}
    sample = [by_id[i] for i in split["title_sample"]]
    batches = [sample[i:i + 25] for i in range(0, len(sample), 25)]

    def run(batch):
        lines = "\n".join(f"{j + 1}. [p{e.get('view_pct', '?')}] {e['title']}" for j, e in enumerate(batch))
        out = llm(prompt("decompose_titles", channel=ch["name"], region=ch["region"], lang=LANG_NAME[ch["lang"]],
                         n=len(batch), titles=lines),
                  role="extract", system=SYSTEM, schema=TITLE_SCHEMA, tag=f"titles:{key}")
        rows = {it["i"]: it for it in out["items"]}
        res = []
        for j, e in enumerate(batch):
            r = rows.get(j + 1)
            if r:
                r = {k: v for k, v in r.items() if k != "i"}
                res.append({"id": e["id"], "title": e["title"], "views": e.get("views"), "view_pct": e.get("view_pct"), **r})
        return res

    results = run_parallel(run, batches, label=f"{key} titles")
    flat = [r for res in results if res for r in res]
    write_json(DATA / "decomp" / "titles" / f"{key}.json", flat)
    print(f"{key}: decomposed {len(flat)}/{len(sample)} titles")


def do_content(ch, sets):
    key = ch["key"]
    sel = selected(key)
    pct = {e["id"]: e.get("view_pct") for e in read_json(split_path(key))["train_titles"]}
    items = [(s, vid) for s in sets for vid in sel.get(s, [])]

    def run(item):
        s, vid = item
        m = meta(key, vid)
        out = llm(prompt("decompose_content", channel=ch["name"], region=ch["region"], title=m["title"],
                         description=m.get("description") or "（无）", transcript=transcript(key, vid)),
                  role="extract", system=SYSTEM, schema=CONTENT_SCHEMA, tag=f"content:{key}:{vid}")
        return {"id": vid, "set": s, "title": m["title"], "views": m.get("views"), "view_pct": pct.get(vid),
                "upload_date": m.get("upload_date"), **out}

    results = run_parallel(run, items, label=f"{key} content")
    path = DATA / "decomp" / "content" / f"{key}.json"
    old = {r["id"]: r for r in read_json(path, [])}
    old.update({r["id"]: r for r in results if r})
    write_json(path, list(old.values()))
    print(f"{key}: decomposed {sum(1 for r in results if r)}/{len(items)} videos")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["titles", "content"])
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--sets", nargs="*", default=list(SETS))
    args = ap.parse_args()
    for ch in load_channels(only=args.only):
        if args.what == "titles":
            do_titles(ch)
        else:
            do_content(ch, args.sets)


if __name__ == "__main__":
    main()
