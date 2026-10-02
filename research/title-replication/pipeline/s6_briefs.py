"""Step 6: neutral briefs for dev / test videos (the generator's only input).

The brief writer sees the transcript but never the title or description, and must
strip the creator's conclusions and rhetoric. A leak check then looks for long runs
of the real title inside the brief; a flagged brief is rewritten once with those
phrases banned. Leak statistics go to out/briefs_leak.json.
"""
import argparse
import re

from common import (CJK, DATA, OUT, llm, load_channels, meta, prompt, read_json, run_parallel, selected,
                    transcript, write_json)

SYSTEM = "你是财经资料编辑，负责把视频字幕整理成不带观点的事实素材。严格按要求的 JSON 结构输出。"
SCHEMA = {"type": "object", "required": ["topic", "facts"],
          "properties": {"topic": {"type": "string"},
                         "facts": {"type": "array", "items": {"type": "string"}}}}
LEAK_CJK, LEAK_WORDS = 6, 4   # a shared run this long counts as a leaked phrase


def leaked_phrases(title, brief_text):
    """Phrases of the real title that reappear verbatim in the brief."""
    if CJK.search(title):
        t = re.sub(r"[\s【】\[\]「」『』“”\"'?？!！,，.。:：|｜()（）-]", "", title)
        found, i = [], 0
        while i <= len(t) - LEAK_CJK:
            j = i + LEAK_CJK
            if t[i:j] in brief_text:
                while j < len(t) and t[i:j + 1] in brief_text:
                    j += 1
                found.append(t[i:j])
                i = j
            else:
                i += 1
        return found
    words = re.findall(r"[a-z0-9$%']+", title.lower())
    low = brief_text.lower()
    return [" ".join(words[i:i + LEAK_WORDS]) for i in range(len(words) - LEAK_WORDS + 1)
            if " ".join(words[i:i + LEAK_WORDS]) in low]


def brief_text(b):
    return b["topic"] + "\n" + "\n".join(b["facts"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--sets", nargs="*", default=["dev", "test"])
    args = ap.parse_args()

    leak_report = read_json(OUT / "briefs_leak.json", {})
    for ch in load_channels(only=args.only):
        key = ch["key"]
        sel = selected(key)
        items = [vid for s in args.sets for vid in sel.get(s, [])]

        def run(vid):
            base = prompt("neutral_brief", transcript=transcript(key, vid))
            b = llm(base, role="extract", system=SYSTEM, schema=SCHEMA, tag=f"brief:{key}:{vid}")
            leaks = leaked_phrases(meta(key, vid)["title"], brief_text(b))
            first = list(leaks)
            if leaks:
                b = llm(base + "\n\n另外，素材里不要出现下面这些说法（可以换成平实的描述）：" + "；".join(leaks),
                        role="extract", system=SYSTEM, schema=SCHEMA, tag=f"brief:{key}:{vid}:retry")
                leaks = leaked_phrases(meta(key, vid)["title"], brief_text(b))
            return vid, b, first, leaks

        results = [r for r in run_parallel(run, items, label=f"{key} briefs") if r]
        path = DATA / "briefs" / f"{key}.json"
        briefs = read_json(path, {})
        for vid, b, first, leaks in results:
            briefs[vid] = {**b, "leaks_first_pass": first, "leaks_final": leaks}
        write_json(path, briefs)
        leak_report[key] = {"n": len(results), "flagged_first_pass": sum(1 for r in results if r[2]),
                            "still_leaking": sum(1 for r in results if r[3])}
        print(f"{key}: {leak_report[key]}")
    write_json(OUT / "briefs_leak.json", leak_report)


if __name__ == "__main__":
    main()
