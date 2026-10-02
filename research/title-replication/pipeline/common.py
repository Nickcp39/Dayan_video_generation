"""Shared paths, IO helpers, the yt-dlp runner and the claude-CLI LLM backend.

Every LLM call goes through `llm()`: it runs the locally installed Claude Code CLI
headless (no tools, no project settings, empty working directory), validates the
JSON against a schema and caches the result on disk, so any step can be re-run
or resumed without paying for the same call twice.
"""
import hashlib
import json
import os
import random
import re
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
DATA = ROOT / "data"
OUT = ROOT / "out"
PROMPTS = ROOT / "prompts"
YTDLP = REPO / "tools" / "yt-dlp.exe"
CLAUDE_CLI = Path(os.environ.get("APPDATA", "")) / "npm" / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
LLM_CWD = DATA / "llm_cwd"

SEED = 20261001
QUOTA = {"train": 30, "dev": 10, "test": 20}
SETS = ("train", "dev", "test")

# Model per role; override with env TR_MODEL_EXTRACT=... etc. Needs Claude Code CLI >= 2.1.280 for Opus 5.5.
MODELS = {"extract": "claude-sonnet-5-5", "synth": "claude-opus-5-5", "gen": "claude-opus-5-5", "judge": "claude-opus-5-5"}

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------- IO

def read_json(path, default=None):
    path = Path(path)
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def load_channels(replicate_only=True, only=None):
    chans = read_json(ROOT / "channels.json")
    if replicate_only:
        chans = [c for c in chans if c.get("replicate")]
    if only:
        chans = [c for c in chans if c["key"] in only]
    return chans


def split_path(key):
    return DATA / "split" / f"{key}.json"


def selected(key):
    """Video ids per set that have a transcript (written by s3)."""
    return read_json(DATA / "split" / f"{key}.selected.json", {s: [] for s in SETS})


def meta(key, vid):
    return read_json(DATA / "meta" / key / f"{vid}.json")


def transcript(key, vid, head=24000, tail=8000):
    """Transcript text, trimmed to the opening and the ending where the thesis usually sits."""
    path = DATA / "subs" / key / f"{vid}.txt"
    text = path.read_text(encoding="utf-8")
    if len(text) <= head + tail:
        return text
    return text[:head] + "\n……（中间省略）……\n" + text[-tail:]


def prompt(name, **kw):
    """Fill {{var}} slots in prompts/<name>.md (double braces leave JSON examples alone)."""
    text = (PROMPTS / f"{name}.md").read_text(encoding="utf-8")
    for k, v in kw.items():
        text = text.replace("{{" + k + "}}", str(v))
    left = re.findall(r"\{\{(\w+)\}\}", text)
    if left:
        raise KeyError(f"prompt {name}: unfilled slots {left}")
    return text


def clean_description(desc, limit=800):
    """Drop sponsor links, URLs and hashtags from a video description."""
    lines = []
    for line in (desc or "").splitlines():
        line = re.sub(r"https?://\S+", "", line).strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line)
    return "\n".join(lines)[:limit]


# ---------------------------------------------------------------- yt-dlp

def ytdlp(args, timeout=900):
    cmd = [str(YTDLP), "--js-runtimes", "node", "--no-warnings", "--encoding", "utf-8"] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)


# ---------------------------------------------------------------- LLM backend

class LLMError(RuntimeError):
    pass


_usage_lock = threading.Lock()
# Variables the desktop app sets for its own session; the child CLI must use its own login.
_HOST_ENV_PREFIXES = ("CLAUDE_CODE_", "CLAUDECODE", "CLAUDE_AGENT_SDK", "CLAUDE_PID", "CLAUDE_EFFORT", "CLAUDE_PREVIEW")


def _child_env():
    return {k: v for k, v in os.environ.items() if not k.startswith(_HOST_ENV_PREFIXES)}


def _extract_json(text):
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if m:
        text = m.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        raise ValueError("no JSON object in model output")
    return json.loads(text[start:end + 1])


def _check(obj, schema):
    for key in schema.get("required", []):
        if key not in obj:
            raise ValueError(f"missing key {key}")


def llm(user, *, role, system, schema, tag=""):
    """One headless Claude call returning a dict that matches `schema` (cached)."""
    model = os.environ.get(f"TR_MODEL_{role.upper()}", MODELS[role])
    key = hashlib.sha256(json.dumps([model, system, user, schema], ensure_ascii=False).encode("utf-8")).hexdigest()
    cache = DATA / "llm_cache" / key[:2] / f"{key}.json"
    hit = read_json(cache)
    if hit is not None:
        return hit["output"]

    LLM_CWD.mkdir(parents=True, exist_ok=True)
    use_schema = os.environ.get("TR_NO_SCHEMA") != "1"
    cmd = [str(CLAUDE_CLI), "-p", "--model", model, "--output-format", "json",
           "--tools", "", "--no-session-persistence", "--setting-sources", "", "--strict-mcp-config",
           "--system-prompt", system]
    body = user
    if use_schema:
        cmd += ["--json-schema", json.dumps(schema, ensure_ascii=False)]
    else:
        body = user + "\n\n只输出一个 JSON 对象，符合这个 JSON Schema：\n" + json.dumps(schema, ensure_ascii=False)

    last = None
    for attempt in range(4):
        try:
            p = subprocess.run(cmd, input=body, capture_output=True, text=True, encoding="utf-8",
                               errors="replace", cwd=str(LLM_CWD), env=_child_env(), timeout=1200)
            d = json.loads(p.stdout)
            if d.get("is_error"):
                msg = str(d.get("result", ""))[:300]
                if "authenticate" in msg or "401" in msg:
                    raise LLMError("claude CLI 未登录或登录失效：请在终端运行 claude 并 /login。原始信息：" + msg)
                raise ValueError(msg)
            out = d.get("structured_output")
            if out is None:
                out = _extract_json(d.get("result", ""))
            _check(out, schema)
        except LLMError:
            raise
        except Exception as e:  # malformed output, timeout, rate limit: back off and retry
            last = e
            time.sleep(10 * (attempt + 1) + random.random() * 5)
            continue
        write_json(cache, {"model": model, "tag": tag, "cost_usd": d.get("total_cost_usd"), "output": out})
        with _usage_lock, open(DATA / "llm_usage.tsv", "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}\t{role}\t{model}\t{tag}\t{d.get('total_cost_usd')}\t{d.get('duration_ms')}\n")
        return out
    raise LLMError(f"[{tag}] failed after retries: {last}")


def run_parallel(fn, items, workers=None, label=""):
    """Apply fn to items with a thread pool; returns results in input order, None for failures."""
    workers = workers or int(os.environ.get("TR_WORKERS", "4"))
    results = [None] * len(items)
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(fn, it): i for i, it in enumerate(items)}
        for fut in as_completed(futs):
            i = futs[fut]
            try:
                results[i] = fut.result()
            except LLMError as e:
                if "未登录" in str(e):
                    ex.shutdown(wait=False, cancel_futures=True)
                    raise
                print(f"  ! {label} item {i}: {e}", flush=True)
            done += 1
            if done % 10 == 0 or done == len(items):
                print(f"  {label}: {done}/{len(items)}", flush=True)
    return results


# ---------------------------------------------------------------- text features (shared by s5 / s8)

CJK = re.compile(r"[぀-ヿ㐀-鿿]")
BRACKET = re.compile(r"[【\[]([^】\]]{1,20})[】\]]")
QUESTION = re.compile(r"[?？]")
DIGIT = re.compile(r"[0-9０-９]|[一二三四五六七八九十百千万亿兆]+(?:年|个|大|种|条|倍|万|亿)")


def title_len(t):
    """Characters for CJK titles, words for others."""
    return len(t) if CJK.search(t) else len(t.split())


def title_features(t):
    words = re.findall(r"[A-Za-z]{2,}", t)
    caps = sum(1 for w in words if w.isupper())
    return {
        "len": title_len(t),
        "question": bool(QUESTION.search(t)),
        "number": bool(DIGIT.search(t)),
        "bracket": bool(BRACKET.search(t)),
        "allcaps_word": caps > 0,
        "pipe_suffix": "|" in t or "｜" in t,
    }


def ngrams(t, n):
    t = t.lower()
    if CJK.search(t):
        s = re.sub(r"\s+", "", t)
        return {s[i:i + n] for i in range(max(0, len(s) - n + 1))}
    w = re.findall(r"[a-z0-9$%']+", t)
    return {" ".join(w[i:i + n]) for i in range(max(0, len(w) - n + 1))}


def jaccard(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0
