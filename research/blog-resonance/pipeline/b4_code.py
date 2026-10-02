"""b4: blind content coding of every sampled post (one LLM call per post).

The coder sees the title and text only — not the blog's name, points, comments or whether
the post is in the hot or cold group. Posts are coded in a shuffled order.
Output: data/codes.json keyed by post_id.
"""
import random
import re

from common import DATA, SEED, llm, prompt, read_json, run_parallel, write_json

SCORE = {"type": "integer", "minimum": 0, "maximum": 2}
SCHEMA = {
    "type": "object",
    "properties": {
        "post_type": {"type": "string", "enum": ["essay_argument", "personal_story", "tutorial_howto", "data_analysis",
                                                  "explainer", "commentary_news", "announcement", "list_links", "other"]},
        "core_claim": {"type": "string"},
        "audience_scope": {"type": "integer", "minimum": 1, "maximum": 4},
        "life_domains": {"type": "array", "items": {"type": "string", "enum": [
            "career_work", "money", "family_relationships", "health_aging", "learning_thinking", "status_identity",
            "society_politics", "tech_tools", "craft_expertise"]}, "minItems": 1, "maxItems": 2},
        "reader_mirror": SCORE,
        "named_concept": {"type": "string"},
        "contrarian": SCORE,
        "surprise": SCORE,
        "emotion": {"type": "string", "enum": ["awe", "anxiety", "anger", "amusement", "inspiration", "tenderness",
                                                "sadness", "curiosity", "none"]},
        "arousal": {"type": "string", "enum": ["low", "medium", "high"]},
        "valence": {"type": "string", "enum": ["positive", "negative", "mixed", "neutral"]},
        "practical_value": SCORE,
        "social_currency": SCORE,
        "identity": SCORE,
        "narrative": SCORE,
        "vulnerability": SCORE,
        "authority": {"type": "string", "enum": ["personal_experience", "data_research", "insider_access", "reasoning",
                                                  "aggregation"]},
        "concreteness": SCORE,
        "debate": SCORE,
        "timeliness": SCORE,
        "accessibility": SCORE,
        "opening": {"type": "string", "enum": ["question", "scene", "bold_claim", "surprising_fact", "context", "none"]},
        "title_promise": {"type": "string", "enum": ["answer", "reveal", "instruct", "name_concept", "provoke", "topic",
                                                      "announce"]},
        "share_reason": {"type": "string"},
    },
}
SCHEMA["required"] = list(SCHEMA["properties"])
SYSTEM = "你是传播学研究的内容编码员。严格按编码手册逐项判断，只依据给定文本，不引入你对作者或文章名气的了解。"
HEAD, TAIL = 5000, 800  # words


def clip(text):
    if len(re.findall(r"[一-鿿]", text)) > len(text) / 3:  # Chinese: clip by characters
        return text if len(text) <= 14000 else text[:12000] + "\n……（中间省略）……\n" + text[-2000:]
    w = text.split()
    if len(w) <= HEAD + TAIL:
        return text
    return " ".join(w[:HEAD]) + "\n……（中间省略）……\n" + " ".join(w[-TAIL:])


def main():
    sample = read_json(DATA / "sample.json", []) + read_json(DATA / "sample_zh.json", [])
    order = list(sample)
    random.Random(SEED).shuffle(order)

    def code(p):
        text = (DATA / "text" / f"{p['post_id']}.txt").read_text(encoding="utf-8")
        user = prompt("code_post", title=p["hn_title"], text=clip(text))
        return llm(user, system=SYSTEM, schema=SCHEMA, tag=f"code:{p['post_id']}")

    results = run_parallel(code, order, label="code")
    codes = read_json(DATA / "codes.json", {})
    for p, r in zip(order, results):
        if r is not None:
            codes[p["post_id"]] = r
    write_json(DATA / "codes.json", codes)
    print(f"coded {len(codes)}/{len(sample)}")


if __name__ == "__main__":
    main()
