"""Throughput and latency vs concurrency: the curve from the video, measured.

  python load_test.py --target local-mac --levels 1,2,4,8,16
"""

import argparse
import asyncio
import json
import time
from pathlib import Path

import httpx

from catalog import system_prompt, user_prompt
from client import chat
from run_eval import pct

ROOT = Path(__file__).parent.parent


async def level(http, target, conc, cases, mode):
    n = max(8, 3 * conc)
    sys_msg = {"role": "system", "content": system_prompt()}
    sem = asyncio.Semaphore(conc)

    async def one(i):
        async with sem:
            c = cases[i % len(cases)]
            return await chat(http, target, [sys_msg, {"role": "user", "content": user_prompt(c)}], mode=mode)

    t0 = time.perf_counter()
    rows = await asyncio.gather(*(one(i) for i in range(n)))
    wall = time.perf_counter() - t0
    ok = [r for r in rows if not r["error"]]
    out_tokens = sum((r["usage"] or {}).get("completion_tokens", 0) for r in ok)
    decode = [((r["usage"] or {}).get("completion_tokens", 1) - 1) / (r["latency"] - r["ttft"])
              for r in ok if r["ttft"] and r["latency"] > r["ttft"]]
    return {
        "target": target, "concurrency": conc, "requests": n, "errors": n - len(ok),
        "throughput_out_tok_s": round(out_tokens / wall, 1),
        "requests_per_min": round(60 * len(ok) / wall, 1),
        "per_user_decode_tok_s_p50": round(pct(decode, 50), 1) if decode else None,
        "ttft_p50_s": round(pct([r["ttft"] for r in ok], 50) or 0, 2),
        "ttft_p95_s": round(pct([r["ttft"] for r in ok], 95) or 0, 2),
        "latency_p50_s": round(pct([r["latency"] for r in ok], 50) or 0, 2),
        "latency_p95_s": round(pct([r["latency"] for r in ok], 95) or 0, 2),
        "sample_error": next((r["error"] for r in rows if r["error"]), None),
    }


async def main(a):
    cases = [json.loads(line) for line in (ROOT / "data" / "eval.jsonl").open()]
    out = ROOT / "results" / f"load_{a.target}{a.tag}.jsonl"
    async with httpx.AsyncClient(limits=httpx.Limits(max_connections=128)) as http:
        await chat(http, a.target, [{"role": "system", "content": system_prompt()}, {"role": "user", "content": user_prompt(cases[0])}])  # warm-up
        with out.open("w") as f:
            for conc in map(int, a.levels.split(",")):
                r = await level(http, a.target, conc, cases, a.mode)
                f.write(json.dumps(r) + "\n")
                f.flush()
                print(json.dumps(r))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--target", required=True)
    p.add_argument("--levels", default="1,2,4,8,16")
    p.add_argument("--mode", default="prompt")
    p.add_argument("--tag", default="")
    asyncio.run(main(p.parse_args()))
