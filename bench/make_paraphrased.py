"""Out-of-template check: the eval orders rewritten by a different model (gpt-oss-120b on Groq) in other words, same facts.
A fine-tune trained on the generator's templates could just learn the templates; this set tells the difference.
Rewrites that drop the customer, the city or the exact date phrase are discarded, so the gold labels stay valid."""
import asyncio
import json
import os
import re
import unicodedata
from pathlib import Path

import httpx

ROOT = Path(__file__).parent.parent
PROMPT = """Reescribe este pedido como lo escribiría OTRA persona real de hostelería española: otras palabras, otro orden, otro tono \
(puede ser más seco, más largo, con saludos distintos, con alguna muletilla). Mantén EXACTAMENTE los mismos hechos:
- el mismo cliente (nombre del negocio tal cual: "{customer}")
- los mismos productos y cantidades (puedes nombrar los productos de otra forma si sigue siendo inequívoco; si hay una corrección de cantidad, mantenla como corrección)
- la expresión de fecha copiada literalmente si la hay: "{date_phrase}"
- la misma ciudad si la hay: "{city}"
- {urgent}
Mismo canal ({style}). Devuelve solo el mensaje reescrito, sin comillas ni explicaciones.

Mensaje original:
{message}"""


def norm(s):
    s = unicodedata.normalize("NFKD", s.lower())
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", "".join(c for c in s if not unicodedata.combining(c))).split())


def date_phrase(msg):
    m = re.search(r"(pasado mañana|pasado manana|mañana|manana|el (lunes|martes|miércoles|miercoles|jueves|viernes|sábado|sabado|domingo)|el \d{1,2}/\d{1,2}|el \d{1,2} de [a-záéíóú]+)", msg, re.I)
    return m.group(0) if m else ""


async def one(http, sem, case):
    g = case["gold"]
    dp = date_phrase(case["message"]) if g["delivery_date"] else ""
    p = PROMPT.format(customer=g["customer"], date_phrase=dp or "(no hay fecha: no añadas ninguna)", city=g["delivery_city"] or "(no hay ciudad: no añadas ninguna)",
                      urgent="que se note que es urgente" if g["urgent"] else "sin decir que es urgente", style=case["style"], message=case["message"])
    async with sem:
        for attempt in range(10):
            r = await http.post("https://api.groq.com/openai/v1/chat/completions", headers={"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"},
                                json={"model": "openai/gpt-oss-120b", "temperature": 0.7, "messages": [{"role": "user", "content": p}]}, timeout=120)
            if r.status_code == 200:
                break
            await asyncio.sleep(float(r.headers.get("retry-after", 5 * (attempt + 1))))
        else:
            return {**case, "kept_facts": False}
    text = r.json()["choices"][0]["message"]["content"].strip()
    n = norm(text)
    ok = norm(g["customer"]) in n and (not g["delivery_city"] or norm(g["delivery_city"]) in n) and (not dp or norm(dp) in n)
    return {**case, "message": text, "original_message": case["message"], "kept_facts": ok}


async def main():
    cases = [json.loads(l) for l in (ROOT / "data" / "eval.jsonl").open()]
    sem = asyncio.Semaphore(2)
    async with httpx.AsyncClient() as http:
        rows = await asyncio.gather(*(one(http, sem, c) for c in cases))
    kept = [r for r in rows if r["kept_facts"]]
    (ROOT / "data" / "eval_paraphrased.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in kept))
    print(f"kept {len(kept)}/{len(rows)} rewrites")


asyncio.run(main())
