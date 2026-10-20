"""One streaming chat call with the timings that matter: TTFT, total latency, tokens, cache hits, cost."""

import json
import os
import time

import httpx

from catalog import json_schema
from targets import TARGETS


async def chat(http: httpx.AsyncClient, target: str, messages: list, mode: str = "prompt", max_tokens: int = 400,
               extra_body: dict | None = None) -> dict:
    t = TARGETS[target]
    body = {
        "model": t["model"],
        "messages": messages,
        "temperature": 0,
        "max_tokens": max_tokens,
        "stream": True,
        "stream_options": {"include_usage": True},
        **t["extra"],
        **(extra_body or {}),
    }
    if mode == "json_schema":
        body["response_format"] = {"type": "json_schema", "json_schema": {"name": "order", "strict": True, "schema": json_schema()}}
    headers = {"Content-Type": "application/json"}
    if t["key_env"]:
        headers["Authorization"] = f"Bearer {os.environ[t['key_env']]}"

    out = {"target": target, "mode": mode, "content": "", "ttft": None, "latency": None, "usage": None,
           "timings": None, "provider": None, "error": None}
    t0 = time.perf_counter()
    try:
        async with http.stream("POST", f"{t['base_url']}/chat/completions", json=body, headers=headers, timeout=300) as r:
            if r.status_code != 200:
                out["error"] = f"HTTP {r.status_code}: {(await r.aread()).decode(errors='ignore')[:300]}"
                return out
            async for line in r.aiter_lines():
                if not line.startswith("data: ") or line == "data: [DONE]":
                    continue
                chunk = json.loads(line[6:])
                if "error" in chunk:
                    out["error"] = str(chunk["error"])[:300]
                for ch in chunk.get("choices") or []:
                    piece = (ch.get("delta") or {}).get("content") or ""
                    if piece and out["ttft"] is None:
                        out["ttft"] = time.perf_counter() - t0
                    out["content"] += piece
                if chunk.get("usage"):
                    out["usage"] = chunk["usage"]
                if chunk.get("timings"):  # llama.cpp: prompt_n, cache_n, prompt_ms, predicted_per_second ...
                    out["timings"] = chunk["timings"]
                if chunk.get("provider"):
                    out["provider"] = chunk["provider"]
    except Exception as e:  # network errors are results too
        out["error"] = f"{type(e).__name__}: {e}"[:300]
    out["latency"] = time.perf_counter() - t0
    return out
