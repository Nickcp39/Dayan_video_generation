"""Step 7: write a title + thesis for each dev/test video from its neutral brief.

Three systems get the same brief and the same output protocol (3 candidates, pick 1):
  zero      channel name only (whatever the model already knows about the creator)
  fewshot   + 30 random training titles
  guide_vN  + the channel's writing guideline vN and its 8 training exemplars
            (topic -> title + thesis)
The guideline system must beat both baselines for the guideline to count as learned.

Usage: python s7_generate.py --set dev|test [--systems zero fewshot guide] [--version N]
"""
import argparse
import random

from common import (DATA, OUT, SEED, llm, load_channels, prompt, read_json, run_parallel, selected, split_path,
                    write_json)
from s4_decompose import LANG_NAME
from s5_guideline import latest_version

SYSTEM = "你是资深的 YouTube 财经频道编辑，擅长模仿特定创作者的选题角度和标题风格。严格按要求的 JSON 结构输出。"
SCHEMA = {"type": "object", "required": ["items"],
          "properties": {"items": {"type": "array", "items": {
              "type": "object", "required": ["id", "candidates", "title", "thesis"],
              "properties": {"id": {"type": "string"},
                             "candidates": {"type": "array", "items": {"type": "string"}},
                             "title": {"type": "string"},
                             "thesis": {"type": "string"}}}}}}
BATCH = 5


def context_for(system, ch, version):
    key = ch["key"]
    if system == "zero":
        return ""
    if system == "fewshot":
        train = read_json(split_path(key))["train_titles"]
        rng = random.Random(f"{SEED}-fewshot-{key}")
        ex = rng.sample(train, min(30, len(train)))
        return "\n这个频道以前发布过的一些标题（供参考风格）：\n" + "\n".join(f"- {e['title']}" for e in ex) + "\n"
    guide = (OUT / "guidelines" / f"{key}.v{version}.md").read_text(encoding="utf-8")
    ex_ids = read_json(OUT / "guidelines" / f"{key}.v{version}.json")["exemplar_ids"]
    content = {r["id"]: r for r in read_json(DATA / "decomp" / "content" / f"{key}.json", []) if r["set"] == "train"}
    shots = "\n".join(f"- 选题：{content[i]['topic']}\n  标题：{content[i]['title']}\n  中心思想：{content[i]['thesis']}"
                      for i in ex_ids if i in content)
    return (f"\n## 这个频道的写作指南\n{guide}\n\n## 示范（选题 → 标题 ＋ 中心思想，来自这个频道以前的视频）\n{shots}\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", required=True, choices=["dev", "test"])
    ap.add_argument("--systems", nargs="*", default=["zero", "fewshot", "guide"])
    ap.add_argument("--version", type=int, help="guideline version (default: latest)")
    ap.add_argument("--only", nargs="*")
    args = ap.parse_args()

    # Flatten (channel, system, batch) into one task list so every call runs in parallel.
    tasks, expected = [], {}
    for ch in load_channels(only=args.only):
        key = ch["key"]
        briefs = read_json(DATA / "briefs" / f"{key}.json", {})
        ids = [v for v in selected(key)[args.set] if v in briefs]
        if not ids:
            print(f"{key}: no briefs for {args.set}, run s6 first")
            continue
        for system in args.systems:
            version = args.version or latest_version(key)
            if system == "guide" and not version:
                print(f"{key}: no guideline yet, run s5 build first")
                continue
            name = f"guide_v{version}" if system == "guide" else system
            context = context_for(system, ch, version)
            expected[(key, name)] = len(ids)
            for i in range(0, len(ids), BATCH):
                tasks.append((ch, name, context, briefs, ids[i:i + BATCH]))

    def run(task):
        ch, name, context, briefs, batch = task
        items = "\n".join(f"### id: {v}\n选题：{briefs[v]['topic']}\n事实素材：\n"
                          + "\n".join(f"- {f}" for f in briefs[v]["facts"]) + "\n" for v in batch)
        out = llm(prompt("generate", channel=ch["name"], region=ch["region"], lang_name=LANG_NAME[ch["lang"]],
                         context=context, n=len(batch), items=items),
                  role="gen", system=SYSTEM, schema=SCHEMA, tag=f"gen:{name}:{ch['key']}:{args.set}")
        return {it["id"]: it for it in out["items"] if it["id"] in batch}

    results = run_parallel(run, tasks, label=f"generate {args.set}")
    got = {k: {} for k in expected}
    for task, r in zip(tasks, results):
        got[(task[0]["key"], task[1])].update(r or {})
    for (key, name), items in got.items():
        write_json(DATA / "gen" / args.set / name / f"{key}.json", items)
        print(f"{key} {name}: {len(items)}/{expected[(key, name)]}")


if __name__ == "__main__":
    main()
