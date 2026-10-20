"""Run the eval set against one target and mode. Writes per-case results and prints a summary row.

  python run_eval.py --target groq --mode json_schema --concurrency 8
"""

import argparse
import asyncio
import json
import statistics
from pathlib import Path

import httpx

from catalog import system_prompt, user_prompt
from client import chat
from score import parse, score

ROOT = Path(__file__).parent.parent


def pct(xs, q):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    return xs[min(len(xs) - 1, int(round(q / 100 * (len(xs) - 1))))]


def summarize(rows):
    n = len(rows)
    ok = [r for r in rows if not r["error"]]
    usage = [r["usage"] or {} for r in ok]
    cost = sum((u.get("cost") or 0) for u in usage)
    return {
        "target": rows[0]["target"], "mode": rows[0]["mode"], "n": n,
        "errors": n - len(ok),
        "valid_json_%": round(100 * sum(r["stage"] != "no_json" for r in ok) / n, 1),
        "valid_order_%": round(100 * sum(r["stage"] == "ok" for r in ok) / n, 1),
        "all_fields_correct_%": round(100 * sum(r["score"]["all"] for r in rows) / n, 1),
        "items_exact_%": round(100 * sum(r["score"]["items_exact"] for r in rows) / n, 1),
        "date_%": round(100 * sum(r["score"]["date"] for r in rows) / n, 1),
        "ttft_p50_s": pct([r["ttft"] for r in ok], 50), "ttft_p95_s": pct([r["ttft"] for r in ok], 95),
        "latency_p50_s": pct([r["latency"] for r in ok], 50), "latency_p95_s": pct([r["latency"] for r in ok], 95),
        "prompt_tokens_avg": round(statistics.mean(u.get("prompt_tokens", 0) for u in usage), 0) if usage else None,
        "completion_tokens_avg": round(statistics.mean(u.get("completion_tokens", 0) for u in usage), 0) if usage else None,
        "usd_per_1k_orders": round(1000 * cost / len(ok), 4) if ok and cost else None,
    }


async def main(a):
    cases = [json.loads(line) for line in (ROOT / "data" / "eval.jsonl").open()][: a.limit]
    sem = asyncio.Semaphore(a.concurrency)
    sys_msg = {"role": "system", "content": system_prompt()}

    async def one(http, case):
        async with sem:
            r = await chat(http, a.target, [sys_msg, {"role": "user", "content": user_prompt(case, a.calendar)}], mode=a.mode)
        obj, stage, err = parse(r["content"]) if not r["error"] else (None, "error", r["error"])
        return {**r, "id": case["id"], "style": case["style"], "stage": stage, "parse_error": err,
                "pred": obj, "gold": case["gold"], "score": score(obj, case["gold"])}

    async with httpx.AsyncClient(http2=False, limits=httpx.Limits(max_connections=64)) as http:
        rows = await asyncio.gather(*(one(http, c) for c in cases))

    out = ROOT / "results" / f"eval_{a.target}_{a.mode}{a.tag}.jsonl"
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    s = summarize(rows)
    with (ROOT / "results" / "summary.jsonl").open("a") as f:
        f.write(json.dumps({**s, "tag": a.tag}) + "\n")
    print(json.dumps(s, indent=1))
    errs = [r["error"] for r in rows if r["error"]][:3]
    if errs:
        print("sample errors:", *errs, sep="\n  ")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--target", required=True)
    p.add_argument("--mode", default="prompt", choices=["prompt", "json_schema"])
    p.add_argument("--concurrency", type=int, default=4)
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--tag", default="")
    p.add_argument("--calendar", action="store_true", help="resolve relative dates in code (workaround)")
    asyncio.run(main(p.parse_args()))
