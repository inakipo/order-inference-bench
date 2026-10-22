"""Cold vs warm latency on a serverless endpoint: wait longer than the idle timeout so workers scale to zero,
send one request (cold), then a few more right away (warm). Repeat.

  python cold_start.py --target runpod-serverless --rounds 3 --idle 180
"""

import argparse
import asyncio
import json
import statistics
import time
from pathlib import Path

import httpx

from catalog import system_prompt, user_prompt
from client import chat

ROOT = Path(__file__).parent.parent


async def main(a):
    case = json.loads((ROOT / "data" / "eval.jsonl").open().readline())
    msgs = [{"role": "system", "content": system_prompt()}, {"role": "user", "content": user_prompt(case)}]
    rows = []
    async with httpx.AsyncClient(timeout=900) as http:  # a cold start can take minutes; the 5 s default would log every one as an error
        for r in range(a.rounds):
            if r or a.wait_first:
                print(f"round {r + 1}: idling {a.idle}s so workers scale to zero…", flush=True)
                await asyncio.sleep(a.idle)
            t0 = time.time()
            cold = await chat(http, a.target, msgs, max_tokens=120)
            warm = [await chat(http, a.target, msgs, max_tokens=120) for _ in range(a.warm)]
            row = {"round": r + 1, "at": time.strftime("%H:%M:%S", time.localtime(t0)),
                   "cold_ttft_s": cold["ttft"], "cold_total_s": cold["latency"], "cold_error": cold["error"],
                   "warm_ttft_p50_s": statistics.median([w["ttft"] for w in warm if w["ttft"]]) if warm else None,
                   "warm_total_p50_s": statistics.median([w["latency"] for w in warm if not w["error"]]) if warm else None}
            rows.append(row)
            print(json.dumps(row), flush=True)
    out = ROOT / "results" / f"cold_start_{a.target}{a.tag}.json"
    out.write_text(json.dumps(rows, indent=1))
    print("saved", out)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--target", required=True)
    p.add_argument("--rounds", type=int, default=3)
    p.add_argument("--idle", type=int, default=180, help="seconds to wait; must exceed the endpoint's idle timeout")
    p.add_argument("--warm", type=int, default=3)
    p.add_argument("--wait-first", action="store_true")
    p.add_argument("--tag", default="")
    asyncio.run(main(p.parse_args()))
