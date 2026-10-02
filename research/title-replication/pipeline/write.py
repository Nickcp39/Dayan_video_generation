"""Write a new episode with the tested guideline system (same prompt, model and guide as s7).

Input is a brief like s6 produces: a neutral topic plus fact lines, no opinions.
  python write.py ../drafts/china_us_bonds.json                 # 小Lin说 only
  python write.py ../drafts/china_us_bonds.json --channels all  # every channel's guide
Brief JSON: {"topic": "...", "facts": ["...", "..."]}. Output: <brief>.out.json next to it.
"""
import argparse
import json
from pathlib import Path

from common import llm, load_channels, prompt, run_parallel
from s4_decompose import LANG_NAME
from s5_guideline import latest_version
from s7_generate import SCHEMA, SYSTEM, context_for


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("brief")
    ap.add_argument("--channels", nargs="*", default=["cn_xiao_lin_shuo"], help="channel keys, or 'all'")
    ap.add_argument("--version", type=int, help="guideline version (default: latest)")
    args = ap.parse_args()

    path = Path(args.brief)
    brief = json.loads(path.read_text(encoding="utf-8"))
    chans = load_channels(only=None if args.channels == ["all"] else args.channels)
    item = "### id: new\n选题：" + brief["topic"] + "\n事实素材：\n" + "\n".join(f"- {f}" for f in brief["facts"]) + "\n"

    def run(ch):
        v = args.version or latest_version(ch["key"])
        out = llm(prompt("generate", channel=ch["name"], region=ch["region"], lang_name=LANG_NAME[ch["lang"]],
                         context=context_for("guide", ch, v), n=1, items=item),
                  role="gen", system=SYSTEM, schema=SCHEMA, tag=f"write:{ch['key']}:v{v}")
        return {"channel": ch["name"], "guide": f"v{v}", **out["items"][0]}

    results = [r for r in run_parallel(run, chans, label="write") if r]
    out_path = path.with_suffix(".out.json")
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    for r in results:
        print(f"\n## {r['channel']}（写作指南 {r['guide']}）\n标题：{r['title']}\n候选：" + " ／ ".join(r["candidates"])
              + f"\n中心思想：{r['thesis']}")
    print(f"\nsaved {out_path}")


if __name__ == "__main__":
    main()
