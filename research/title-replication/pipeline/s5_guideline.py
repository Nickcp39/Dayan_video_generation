"""Step 5: turn the training-set decompositions into one writing guideline per channel.

  build    v1 from training data only: title statistics computed here + hook / template /
           thesis distributions from s4, synthesised by the LLM into a 7-section guide.
  revise   v(n+1) from v(n) plus the dev-set results of s8 (diagnosis only; dev titles
           must not be copied into the guide). The test set is never shown to this step.

Outputs: out/guidelines/<key>.v<n>.md (the guide) and .json (exemplar ids, changes).
"""
import argparse
import re
from collections import Counter

from common import (DATA, OUT, llm, load_channels, prompt, read_json, run_parallel, split_path, title_features,
                    write_json)
from s4_decompose import LANG_NAME

SYSTEM = "你是资深内容策略研究员，擅长把一位创作者的写作习惯总结成可执行的写作指南。只依据给定数据，严格按要求的 JSON 结构输出。"
SCHEMA = {"type": "object", "required": ["guideline_md", "exemplar_ids"],
          "properties": {"guideline_md": {"type": "string"},
                         "exemplar_ids": {"type": "array", "items": {"type": "string"}}}}
REVISE_SCHEMA = {"type": "object", "required": ["guideline_md", "changes"],
                 "properties": {"guideline_md": {"type": "string"},
                                "changes": {"type": "array", "items": {"type": "string"}}}}


def pct(n, d):
    return f"{round(100 * n / d)}%" if d else "-"


def quantiles(xs, qs=(0.1, 0.5, 0.9)):
    xs = sorted(xs)
    return [xs[min(len(xs) - 1, int(q * len(xs)))] for q in qs] if xs else [0, 0, 0]


def stats_block(train_titles, lang):
    titles = [e["title"] for e in train_titles]
    hits = [e["title"] for e in train_titles if (e.get("view_pct") or 0) >= 67]
    unit = "字" if lang in ("zh", "ja") else "词"

    def row(name, ts):
        f = [title_features(t) for t in ts]
        n = len(f)
        p10, p50, p90 = quantiles([x["len"] for x in f])
        return (f"| {name} | {n} | {p10}–{p50}–{p90} | {pct(sum(x['question'] for x in f), n)} | "
                f"{pct(sum(x['number'] for x in f), n)} | {pct(sum(x['bracket'] for x in f), n)} | "
                f"{pct(sum(x['allcaps_word'] for x in f), n)} | {pct(sum(x['pipe_suffix'] for x in f), n)} |")

    labels = Counter()
    for t in titles:
        labels.update(m.group(0) for m in re.finditer(r"【[^】]{1,20}】|\[[^\]]{1,20}\]", t))
    suffix = Counter(re.split(r"\s[|｜]\s", t)[-1].strip() for t in titles if re.search(r"\s[|｜]\s", t))
    out = [f"长度单位：{unit}（p10–中位数–p90）",
           f"| 范围 | 条数 | 长度 | 问号 | 数字 | 括号标签 | 全大写词 | 含竖线分隔 |",
           "|---|---|---|---|---|---|---|---|",
           row("全部训练标题", titles), row("爆款（播放前 1/3）", hits)]
    if labels:
        out.append("常见括号标签：" + "；".join(f"{k}×{v}" for k, v in labels.most_common(12)))
    brand = [(k, v) for k, v in suffix.most_common(6) if v >= 3]
    if brand:
        out.append("重复出现的竖线后缀（品牌后缀）：" + "；".join(f"{k}×{v}" for k, v in brand))
    return "\n".join(out)


def dist(rows, field, multi=False):
    c = Counter()
    for r in rows:
        vals = r.get(field) or []
        c.update(vals if multi else [vals])
    n = len(rows)
    return "，".join(f"{k} {pct(v, n)}" for k, v in c.most_common())


def hooks_block(decomp):
    hits = [r for r in decomp if (r.get("view_pct") or 0) >= 67]
    lines = []
    for name, rows in (("全部", decomp), ("爆款", hits)):
        if not rows:
            continue
        lines.append(f"**{name}（{len(rows)} 条）**")
        lines.append(f"- 首要钩子：{dist([{'h': (r['hooks'] or ['none'])[0]} for r in rows], 'h')}")
        lines.append(f"- 出现过的钩子（可多选）：{dist(rows, 'hooks', multi=True)}")
        lines.append(f"- 人称：{dist(rows, 'persona')}")
        lines.append(f"- 情绪：{dist(rows, 'register')}")
        lines.append(f"- 数字作用：{dist(rows, 'numbers')}")
    return "\n".join(lines)


def templates_block(decomp, top=30):
    groups = {}
    for r in decomp:
        t = re.sub(r"\s+", " ", r["template"]).strip()
        groups.setdefault(t, []).append(r)
    ranked = sorted(groups.items(), key=lambda kv: (-len(kv[1]), -max((x.get("view_pct") or 0) for x in kv[1])))
    lines = []
    for t, rows in ranked[:top]:
        ex = sorted(rows, key=lambda x: -(x.get("view_pct") or 0))[:2]
        lines.append(f"- {t} ×{len(rows)}　例：" + " ／ ".join(f"「{x['title']}」(p{x.get('view_pct')})" for x in ex))
    return "\n".join(lines)


def content_block(rows):
    lines = []
    for r in rows:
        lines.append(f"[{r['id']}] p{r.get('view_pct')} 标题：{r['title']}\n"
                     f"  选题：{r['topic']}｜中心思想：{r['thesis']}｜类型：{r['thesis_type']}\n"
                     f"  角度：{r['angle']}｜标题与论点：{r['title_thesis']}（{r['title_thesis_note']}）")
    return "\n".join(lines)


def latest_version(key):
    vs = [int(m.group(1)) for p in (OUT / "guidelines").glob(f"{key}.v*.md")
          for m in [re.search(r"\.v(\d+)\.md$", p.name)] if m]
    return max(vs) if vs else 0


def build(ch):
    key = ch["key"]
    split = read_json(split_path(key))
    titles = read_json(DATA / "decomp" / "titles" / f"{key}.json", [])
    content = [r for r in read_json(DATA / "decomp" / "content" / f"{key}.json", []) if r["set"] == "train"]
    if not titles or not content:
        print(f"{key}: missing decompositions, run s4 first")
        return
    out = llm(prompt("guideline", channel=ch["name"], region=ch["region"], lang=LANG_NAME[ch["lang"]],
                     stats=stats_block(split["train_titles"], ch["lang"]), n_decomposed=len(titles),
                     hooks=hooks_block(titles), templates=templates_block(titles),
                     n_content=len(content), content=content_block(content)),
              role="synth", system=SYSTEM, schema=SCHEMA, tag=f"guideline:{key}:v1")
    valid = {r["id"] for r in content}
    ex = [i for i in out["exemplar_ids"] if i in valid][:8]
    save(key, 1, out["guideline_md"], {"exemplar_ids": ex, "source": "train"})


def revise(ch):
    key = ch["key"]
    v = latest_version(key)
    details = read_json(OUT / "results" / "dev" / f"{key}.json")
    sys_name = f"guide_v{v}"
    if not v or not details or sys_name not in details["systems"]:
        print(f"{key}: need guideline v{v} evaluated on dev (s7 + s8 --set dev) first")
        return
    lines = []
    for it in details["items"]:
        g = it["systems"][sys_name]
        lines.append(f"- 选题：{it['topic']}\n  真实标题：{it['real_title']}\n  仿写标题：{g['title']}\n"
                     f"  真实中心思想：{it['real_thesis']}\n  仿写中心思想：{g['thesis']}\n"
                     f"  评审：{'猜对（仿写被识破）' if g.get('judge_correct') else '猜错（仿写骗过评审）'}，"
                     f"把握 {g.get('judge_conf')}，依据：{g.get('judge_reason')}\n"
                     f"  中心思想一致度：{g.get('thesis_score')}（{g.get('thesis_reason')}）"
                     + (f"\n  与训练集旧标题重合度 {g['copy_sim']}：{g['copy_nearest']}" if g.get("copy_nearest") else ""))
    cur = (OUT / "guidelines" / f"{key}.v{v}.md").read_text(encoding="utf-8")
    out = llm(prompt("guideline_revise", channel=ch["name"], guideline=cur, results="\n".join(lines)),
              role="synth", system=SYSTEM, schema=REVISE_SCHEMA, tag=f"guideline:{key}:v{v + 1}")
    prev = read_json(OUT / "guidelines" / f"{key}.v{v}.json")
    save(key, v + 1, out["guideline_md"], {"exemplar_ids": prev["exemplar_ids"], "source": f"v{v} + dev",
                                           "changes": out["changes"]})


def save(key, v, md, extra):
    (OUT / "guidelines").mkdir(parents=True, exist_ok=True)
    (OUT / "guidelines" / f"{key}.v{v}.md").write_text(md.strip() + "\n", encoding="utf-8")
    write_json(OUT / "guidelines" / f"{key}.v{v}.json", extra)
    print(f"{key}: wrote guideline v{v} ({len(md)} chars)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["build", "revise"])
    ap.add_argument("--only", nargs="*")
    args = ap.parse_args()
    run_parallel(build if args.what == "build" else revise, load_channels(only=args.only), label=f"guideline {args.what}")


if __name__ == "__main__":
    main()
