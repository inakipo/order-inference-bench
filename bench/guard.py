"""The workaround: a schema guard in front of any provider.

validate -> on failure, one repair retry with the exact validation error -> on failure, fall back to a target
(prompt mode: in our runs, server-side schema enforcement looped on 4/120 orders). Exposed as an OpenAI-compatible proxy so a customer only changes base_url.

  python guard.py --primary novita --fallback coreweave          # eval through the guard
  uvicorn guard:app --port 8090                                  # run it as a drop-in proxy
"""

import argparse
import asyncio
import json
import os
import time
from pathlib import Path

import httpx

from catalog import system_prompt, user_prompt
from client import chat
from run_eval import summarize
from score import parse, score

ROOT = Path(__file__).parent.parent
PRIMARY = os.environ.get("GUARD_PRIMARY", "novita")
FALLBACK = os.environ.get("GUARD_FALLBACK", "coreweave")


async def guarded(http, messages, primary=PRIMARY, fallback=FALLBACK, mode="prompt", fallback_mode="prompt"):
    t0 = time.perf_counter()
    steps = []
    r = await chat(http, primary, messages, mode=mode)
    obj, stage, err = parse(r["content"]) if not r["error"] else (None, "error", r["error"])
    steps.append({"target": primary, "stage": stage})
    if stage != "ok" and stage != "error":
        repair = messages + [{"role": "assistant", "content": r["content"]},
                             {"role": "user", "content": f"Tu respuesta no es válida: {err}. Devuelve SOLO el JSON corregido, usando SKUs exactos del catálogo."}]
        r = await chat(http, primary, repair, mode=mode)
        obj, stage, err = parse(r["content"]) if not r["error"] else (None, "error", r["error"])
        steps.append({"target": primary, "stage": stage, "repair": True})
    if stage != "ok":
        r = await chat(http, fallback, messages, mode=fallback_mode)
        obj, stage, err = parse(r["content"]) if not r["error"] else (None, "error", r["error"])
        steps.append({"target": fallback, "stage": stage, "fallback": True})
    return {**r, "latency": time.perf_counter() - t0, "steps": steps, "obj": obj, "stage": stage, "parse_error": err}


async def run_eval(a):
    cases = [json.loads(line) for line in (ROOT / "data" / "eval.jsonl").open()][: a.limit]
    sem = asyncio.Semaphore(a.concurrency)
    sys_msg = {"role": "system", "content": system_prompt()}

    async def one(http, c):
        async with sem:
            g = await guarded(http, [sys_msg, {"role": "user", "content": user_prompt(c, a.calendar)}], a.primary, a.fallback)
        return {**g, "target": f"guard({a.primary}->{a.fallback})", "mode": "prompt", "id": c["id"],
                "pred": g["obj"], "gold": c["gold"], "score": score(g["obj"], c["gold"])}

    async with httpx.AsyncClient() as http:
        rows = await asyncio.gather(*(one(http, c) for c in cases))
    for r in rows:
        r["error"] = None if r["stage"] != "error" else r["parse_error"]
    out = ROOT / "results" / f"eval_guard_{a.primary}_{a.fallback}{'_cal' if a.calendar else ''}.jsonl"
    out.write_text("".join(json.dumps(r, ensure_ascii=False, default=str) + "\n" for r in rows))
    s = summarize(rows)
    s["repairs"] = sum(any(st.get("repair") for st in r["steps"]) for r in rows)
    s["fallbacks"] = sum(any(st.get("fallback") for st in r["steps"]) for r in rows)
    with (ROOT / "results" / "summary.jsonl").open("a") as f:
        f.write(json.dumps({**s, "tag": "guard" + ("+calendar" if a.calendar else "")}) + "\n")
    print(json.dumps(s, indent=1))


# --- drop-in proxy -------------------------------------------------------------------------------------------
try:
    from fastapi import FastAPI, Request

    app = FastAPI(title="schema guard")
    _http = httpx.AsyncClient()

    @app.post("/v1/chat/completions")
    async def completions(req: Request):
        body = await req.json()
        g = await guarded(_http, body["messages"])
        content = json.dumps(g["obj"], ensure_ascii=False) if g["stage"] == "ok" else g["content"]
        return {"id": "guard", "object": "chat.completion", "model": body.get("model", "guard"),
                "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": content}}],
                "usage": g["usage"], "guard": {"steps": g["steps"], "final_stage": g["stage"]}}
except ImportError:
    pass


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--primary", default=PRIMARY)
    p.add_argument("--fallback", default=FALLBACK)
    p.add_argument("--concurrency", type=int, default=6)
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--calendar", action="store_true")
    asyncio.run(run_eval(p.parse_args()))
