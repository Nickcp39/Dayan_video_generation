"""Step 9: write out/REPORT_<set>.md from the s8 results, plus a blind-test page for people.

The HTML page (out/blind_test_<set>.html) shows each real/guideline-generated pair in
random order; the reader clicks the one they think is real and gets a score at the end.
It is a local file with no external requests.
"""
import argparse
import html
import json
import random

from common import OUT, SEED, load_channels, read_json

SYS_NAME = {"zero": "零样本（只给频道名）", "fewshot": "少样本（30 条旧标题）"}


def sys_label(s):
    if s in SYS_NAME:
        return SYS_NAME[s]
    return f"写作指南 {s.split('_')[-1]}" if s.startswith("guide_") else s


def fmt(x, pct=False):
    if x is None:
        return "-"
    return f"{round(100 * x)}%" if pct else f"{x}"


def overall(summary, systems):
    rows = []
    for s in systems:
        vals = [c[s] for c in summary["channels"].values() if s in c]
        n = sum(v["n"] for v in vals)
        w = lambda k: sum((v[k] or 0) * v["n"] for v in vals if v[k] is not None) / max(1, sum(v["n"] for v in vals if v[k] is not None))
        rows.append((s, n, w("fool_rate"), w("thesis_mean"), w("thesis_ge2"), w("attr_acc"),
                     sum(v["copy_flags"] for v in vals), sum(v.get("near_verbatim", 0) for v in vals)))
    real = [c["real_attr_acc"] for c in summary["channels"].values() if c.get("real_attr_acc") is not None]
    return rows, (sum(real) / len(real) if real else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", required=True, choices=["dev", "test"])
    args = ap.parse_args()
    summary = read_json(OUT / "results" / args.set / "summary.json")
    systems = summary["systems"]
    chans = {c["key"]: c for c in load_channels()}

    rows, real_attr = overall(summary, systems)
    out = [f"# 标题与中心思想复刻测试（{args.set}）", "",
           "评审：盲测辨真时，评审模型在真实标题和仿写标题里猜哪个是真的；骗过率 = 猜错的比例，50% 表示完全分不出。"
           "频道归属：把真实标题和各方案的仿写标题混在一起，让评审判断出自 9 个频道中的哪一个。"
           "中心思想：仿写论点与原视频论点的一致度，0–3 分。"
           "旧标题重合：与训练集某条旧标题的 3-gram 重合度；≥ 0.5 记为套用旧句式（作者自己的公式，允许），≥ 0.8 记为近乎照搬原句（算抄袭）。", "",
           "## 总体", "",
           "| 方案 | 期数 | 骗过率（越接近 50% 越好） | 中心思想均分 /3 | 中心思想 ≥2 分占比 | 频道归属准确率 | 套用旧句式 | 近乎照搬 |",
           "|---|---|---|---|---|---|---|---|"]
    for s, n, fool, th, th2, attr, cp, nv in rows:
        out.append(f"| {sys_label(s)} | {n} | {fmt(round(fool, 2), True)} | {th:.2f} | {fmt(round(th2, 2), True)} | "
                   f"{fmt(round(attr, 2), True)} | {cp} | {nv} |")
    out.append(f"\n真实标题的频道归属准确率（上限参照）：{fmt(round(real_attr, 2), True) if real_attr is not None else '-'}\n")

    out += ["## 分频道", ""]
    for key, c in summary["channels"].items():
        out.append(f"### {chans[key]['name']}")
        out.append(f"真实标题：平均长度 {c['real_style']['len']}，问号 {fmt(c['real_style']['question'], True)}，"
                   f"数字 {fmt(c['real_style']['number'], True)}，括号标签 {fmt(c['real_style']['bracket'], True)}；"
                   f"频道归属准确率 {fmt(c['real_attr_acc'], True)}\n")
        out.append("| 方案 | 骗过率 | 中心思想 /3 | 归属准确率 | 长度 | 问号 | 数字 | 括号 | 套用旧句式 |")
        out.append("|---|---|---|---|---|---|---|---|---|")
        for s in systems:
            if s not in c:
                continue
            v = c[s]
            out.append(f"| {sys_label(s)} | {fmt(v['fool_rate'], True)} | {fmt(v['thesis_mean'])} | {fmt(v['attr_acc'], True)} | "
                       f"{v['style']['len']} | {fmt(v['style']['question'], True)} | {fmt(v['style']['number'], True)} | "
                       f"{fmt(v['style']['bracket'], True)} | {v['copy_flags']} |")
        details = read_json(OUT / "results" / args.set / f"{key}.json")
        guide = [s for s in systems if s.startswith("guide")]
        if guide and details:
            g = guide[-1]
            out.append(f"\n示例（{sys_label(g)}）：\n")
            for it in [x for x in details["items"] if g in x["systems"]][:4]:
                r = it["systems"][g]
                out.append(f"- 选题：{it['topic']}\n  - 真实：{it['real_title']}\n  - 仿写：{r['title']}"
                           f"（评审{'识破' if r.get('judge_correct') else '被骗'}；论点 {r.get('thesis_score')} 分）\n"
                           f"  - 真实论点：{it['real_thesis']}\n  - 仿写论点：{r['thesis']}")
        out.append("")
    (OUT / f"REPORT_{args.set}.md").write_text("\n".join(out), encoding="utf-8")
    print(f"wrote {OUT / f'REPORT_{args.set}.md'}")
    blind_test(args.set, systems, chans)


def blind_test(set_name, systems, chans):
    guide = [s for s in systems if s.startswith("guide")]
    if not guide:
        return
    g = guide[-1]
    rng = random.Random(f"{SEED}-blind")
    pairs = []
    for key in chans:
        d = read_json(OUT / "results" / set_name / f"{key}.json")
        if not d:
            continue
        for it in d["items"]:
            if g not in it["systems"]:
                continue
            real_first = rng.random() < 0.5
            a, b = it["real_title"], it["systems"][g]["title"]
            pairs.append({"channel": chans[key]["name"], "topic": it["topic"],
                          "a": a if real_first else b, "b": b if real_first else a, "real": "a" if real_first else "b"})
    rng.shuffle(pairs)
    data = json.dumps(pairs, ensure_ascii=False)
    page = TEMPLATE.replace("__DATA__", data).replace("__TITLE__", html.escape(f"标题盲测（{set_name}，{g}）"))
    (OUT / f"blind_test_{set_name}.html").write_text(page, encoding="utf-8")
    print(f"wrote blind test with {len(pairs)} pairs")


TEMPLATE = """<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>__TITLE__</title>
<style>
:root{--bg:#faf9f7;--fg:#1f1d1a;--muted:#6b665e;--card:#fff;--line:#e4e0d8;--accent:#2f6fde;--ok:#1d8a4e;--bad:#c2412d}
@media (prefers-color-scheme:dark){:root{--bg:#161514;--fg:#ece9e4;--muted:#a19b91;--card:#211f1d;--line:#38342f;--accent:#7aa7ff;--ok:#4cc38a;--bad:#ff7a66}}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.6 system-ui,-apple-system,"PingFang SC","Hiragino Sans","Microsoft YaHei",sans-serif}
main{max-width:720px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:20px;margin:0 0 4px}.muted{color:var(--muted);font-size:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin:16px 0}
button.opt{display:block;width:100%;text-align:left;background:transparent;color:var(--fg);border:1px solid var(--line);border-radius:10px;padding:12px;margin:8px 0;font:inherit;cursor:pointer}
button.opt:hover{border-color:var(--accent)}button.opt.ok{border-color:var(--ok);background:color-mix(in srgb,var(--ok) 12%,transparent)}
button.opt.bad{border-color:var(--bad);background:color-mix(in srgb,var(--bad) 12%,transparent)}
#next{background:var(--accent);color:#fff;border:0;border-radius:8px;padding:10px 18px;font:inherit;cursor:pointer}
.bar{height:6px;background:var(--line);border-radius:3px;overflow:hidden}.bar>i{display:block;height:100%;background:var(--accent)}
</style></head><body><main>
<h1>__TITLE__</h1><p class="muted">每题两个标题：一个是频道真实发布的，一个是 AI 按写作指南仿写的。点你认为是真实的那个。猜中率越接近 50%，说明仿写越难分辨。</p>
<div class="bar"><i id="prog" style="width:0"></i></div>
<div id="q" class="card"></div><p id="score" class="muted"></p></main>
<script>
const P=__DATA__;let i=0,right=0,done=false;
function show(){const q=document.getElementById('q');if(i>=P.length){q.innerHTML='<b>结束</b><p>你猜中真实标题 '+right+' / '+P.length+'（'+Math.round(100*right/P.length)+'%）。</p>';return}
const p=P[i];done=false;q.innerHTML='<div class="muted">'+(i+1)+' / '+P.length+' · '+esc(p.channel)+'</div><p>选题：'+esc(p.topic)+'</p>'
+'<button class="opt" data-k="a">'+esc(p.a)+'</button><button class="opt" data-k="b">'+esc(p.b)+'</button><p id="fb" class="muted"></p>';
q.querySelectorAll('.opt').forEach(b=>b.onclick=()=>pick(b));document.getElementById('prog').style.width=(100*i/P.length)+'%'}
function pick(b){if(done)return;done=true;const p=P[i],ok=b.dataset.k===p.real;if(ok)right++;
document.querySelectorAll('.opt').forEach(x=>x.classList.add(x.dataset.k===p.real?'ok':'bad'));
document.getElementById('fb').innerHTML=(ok?'猜中了。':'猜错了，这个是 AI 写的。')+' <button id="next">下一题</button>';
document.getElementById('next').onclick=()=>{i++;show()};document.getElementById('score').textContent='目前猜中 '+right+' / '+(i+1)}
function esc(s){return String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
show();
</script></body></html>
"""


if __name__ == "__main__":
    main()
