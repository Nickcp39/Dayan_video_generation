"""b4b: coder reliability. Re-code a random subset with a second model and measure agreement.

Run with a different model, e.g.  BR_MODEL=claude-opus-5-5 python b4b_reliability.py
Writes data/codes_<model>.json and out/reliability.json (exact and within-one agreement
on the 0–2 scores, exact agreement on categories) against data/codes.json.
"""
import random
import statistics as st

from b4_code import SCHEMA, SYSTEM, clip
from common import DATA, MODEL, OUT, SEED, llm, prompt, read_json, run_parallel, write_json

N = 30
SCORES = [k for k, v in SCHEMA["properties"].items() if v.get("type") == "integer"]
CATS = [k for k, v in SCHEMA["properties"].items() if "enum" in v]


def main():
    base = read_json(DATA / "codes.json", {})
    sample = [p for p in read_json(DATA / "sample.json", []) if p["post_id"] in base]
    subset = random.Random(SEED + 1).sample(sample, min(N, len(sample)))

    def code(p):
        text = (DATA / "text" / f"{p['post_id']}.txt").read_text(encoding="utf-8")
        return llm(prompt("code_post", title=p["hn_title"], text=clip(text)), system=SYSTEM, schema=SCHEMA,
                   tag=f"rel:{p['post_id']}")

    second = {p["post_id"]: r for p, r in zip(subset, run_parallel(code, subset, label="reliability")) if r}
    write_json(DATA / f"codes_{MODEL}.json", second)
    rep = {"model_a": "codes.json", "model_b": MODEL, "n": len(second), "scores": {}, "categories": {}}
    for k in SCORES:
        pairs = [(base[i][k], second[i][k]) for i in second]
        rep["scores"][k] = {"exact": round(st.mean(a == b for a, b in pairs), 2),
                            "within_one": round(st.mean(abs(a - b) <= 1 for a, b in pairs), 2)}
    for k in CATS:
        rep["categories"][k] = {"exact": round(st.mean(base[i][k] == second[i][k] for i in second), 2)}
    write_json(OUT / "reliability.json", rep)
    print(rep)


if __name__ == "__main__":
    main()
