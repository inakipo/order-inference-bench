"""Prefix caching on the local server: same requests with the cache on, off, and broken by a date at the top.

llama.cpp reports per request how many prompt tokens came from cache (timings.cache_n) and how many
it had to prefill (timings.prompt_n), so the effect is measured, not inferred.
"""

import asyncio
import json
import statistics
from pathlib import Path

import httpx

from catalog import system_prompt, user_prompt
from client import chat

ROOT = Path(__file__).parent.parent
N = 12


async def run(http, cases, variant):
    rows = []
    for c in cases:
        if variant == "date_on_top":  # the classic mistake: per-request data at the start of the prompt
            msgs = [{"role": "system", "content": f"Fecha de hoy: {c['today']}\n\n" + system_prompt()},
                    {"role": "user", "content": user_prompt(c)}]
        else:
            msgs = [{"role": "system", "content": system_prompt()}, {"role": "user", "content": user_prompt(c)}]
        extra = {"cache_prompt": variant != "cache_off"}
        r = await chat(http, "local-mac", msgs, extra_body=extra)
        tm = r["timings"] or {}
        rows.append({"ttft": r["ttft"], "prompt_n": tm.get("prompt_n"), "cache_n": tm.get("cache_n"),
                     "prefill_tok_s": tm.get("prompt_per_second"), "decode_tok_s": tm.get("predicted_per_second")})
    ttfts = [r["ttft"] for r in rows[1:] if r["ttft"]]  # skip the first (cold) request
    return {
        "variant": variant,
        "ttft_mean_s": round(statistics.mean(ttfts), 2),
        "prefilled_tokens_avg": round(statistics.mean(r["prompt_n"] or 0 for r in rows[1:]), 0),
        "cached_tokens_avg": round(statistics.mean(r["cache_n"] or 0 for r in rows[1:]), 0),
        "prefill_tok_s_avg": round(statistics.mean(r["prefill_tok_s"] or 0 for r in rows[1:]), 1),
        "decode_tok_s_avg": round(statistics.mean(r["decode_tok_s"] or 0 for r in rows[1:]), 1),
    }


async def main():
    cases = [json.loads(line) for line in (ROOT / "data" / "eval.jsonl").open()][:N]
    # different 'today' per case so the date_on_top variant really changes the prefix
    async with httpx.AsyncClient() as http:
        out = [await run(http, cases, v) for v in ("cache_on", "cache_off", "date_on_top")]
    (ROOT / "results" / "prefix_cache_local.json").write_text(json.dumps(out, indent=1))
    for r in out:
        print(json.dumps(r))


if __name__ == "__main__":
    asyncio.run(main())
