"""Training set for the LoRA: same generator as the eval, different seed, and no message that also appears in the eval set."""
import json
import random
import sys
from pathlib import Path

import make_eval
from catalog import system_prompt, user_prompt

ROOT = Path(__file__).parent.parent

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1500
    make_eval.rng = random.Random(2026)
    eval_msgs = {json.loads(l)["message"] for l in (ROOT / "data" / "eval.jsonl").open()}
    sys_msg = system_prompt()
    rows, i = [], 0
    while len(rows) < n:
        case = make_eval.make_case(10_000 + i); i += 1
        if case["message"] in eval_msgs:
            continue
        answer = json.dumps(case["gold"], ensure_ascii=False)
        rows.append({"messages": [{"role": "system", "content": sys_msg},
                                  {"role": "user", "content": user_prompt(case, with_calendar=True)},
                                  {"role": "assistant", "content": answer}]})
    out = ROOT / "data" / "train.jsonl"
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    print(f"wrote {len(rows)} training examples to {out} (skipped {i - len(rows)} that matched eval messages)")
