"""Shared paths, IO and the headless Claude CLI backend for the blog-resonance study.

The LLM backend follows research/title-replication/pipeline/common.py: the locally
installed Claude Code CLI runs headless with no tools, the JSON result is checked
against a schema, and every call is cached on disk so steps can be re-run or resumed
without paying twice. Cache and usage log live under this study's data/ folder.
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
DATA = ROOT / "data"
OUT = ROOT / "out"
PROMPTS = ROOT / "prompts"
CLAUDE_CLI = Path(os.environ.get("APPDATA", "")) / "npm" / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
LLM_CWD = DATA / "llm_cwd"
SEED = 20261002
MODEL = os.environ.get("BR_MODEL", "claude-sonnet-5-5")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


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


def blogs():
    return read_json(ROOT / "blogs.json")


def prompt(name, **kw):
    """Fill {{var}} slots in prompts/<name>.md."""
    text = (PROMPTS / f"{name}.md").read_text(encoding="utf-8")
    for k, v in kw.items():
        text = text.replace("{{" + k + "}}", str(v))
    left = re.findall(r"\{\{(\w+)\}\}", text)
    if left:
        raise KeyError(f"prompt {name}: unfilled slots {left}")
    return text


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


def llm(user, *, system, schema, tag=""):
    """One headless Claude call returning a dict that matches `schema` (cached)."""
    key = hashlib.sha256(json.dumps([MODEL, system, user, schema], ensure_ascii=False).encode("utf-8")).hexdigest()
    cache = DATA / "llm_cache" / key[:2] / f"{key}.json"
    hit = read_json(cache)
    if hit is not None:
        return hit["output"]

    LLM_CWD.mkdir(parents=True, exist_ok=True)
    cmd = [str(CLAUDE_CLI), "-p", "--model", MODEL, "--output-format", "json",
           "--tools", "", "--no-session-persistence", "--setting-sources", "", "--strict-mcp-config",
           "--system-prompt", system, "--json-schema", json.dumps(schema, ensure_ascii=False)]
    last = None
    for attempt in range(4):
        try:
            p = subprocess.run(cmd, input=user, capture_output=True, text=True, encoding="utf-8",
                               errors="replace", cwd=str(LLM_CWD), env=_child_env(), timeout=1200)
            d = json.loads(p.stdout)
            if d.get("is_error"):
                msg = str(d.get("result", ""))[:300]
                if "authenticate" in msg or "401" in msg:
                    raise LLMError("claude CLI 未登录或登录失效：请在终端运行 claude auth login --claudeai。原始信息：" + msg)
                raise ValueError(msg)
            out = d.get("structured_output")
            if out is None:
                out = _extract_json(d.get("result", ""))
            missing = [k for k in schema.get("required", []) if k not in out]
            if missing:
                raise ValueError(f"missing keys {missing}")
        except LLMError:
            raise
        except Exception as e:  # malformed output, timeout, rate limit: back off and retry
            last = e
            time.sleep(10 * (attempt + 1) + random.random() * 5)
            continue
        write_json(cache, {"model": MODEL, "tag": tag, "cost_usd": d.get("total_cost_usd"), "output": out})
        with _usage_lock, open(DATA / "llm_usage.tsv", "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}\t{MODEL}\t{tag}\t{d.get('total_cost_usd')}\t{d.get('duration_ms')}\n")
        return out
    raise LLMError(f"[{tag}] failed after retries: {last}")


def run_parallel(fn, items, workers=None, label=""):
    """Apply fn to items with a thread pool; returns results in input order, None for failures."""
    workers = workers or int(os.environ.get("BR_WORKERS", "3"))
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
