"""Turn a model's raw text into an order and score it field by field against the gold label."""

import json
import re
import unicodedata

from pydantic import ValidationError

from catalog import SKUS, Order

SKU_SET = set(SKUS)


def norm(s):
    if s is None:
        return None
    s = "".join(c for c in unicodedata.normalize("NFD", str(s)) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()


def parse(text: str):
    """-> (obj or None, stage reached: 'no_json' | 'bad_schema' | 'unknown_sku' | 'ok', error)"""
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None, "no_json", "no JSON object in output"
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError as e:
        return None, "no_json", f"invalid JSON: {e}"
    try:
        order = Order.model_validate(obj)
    except ValidationError as e:
        return obj, "bad_schema", str(e.errors()[0])[:200]
    bad = [i.sku for i in order.items if i.sku not in SKU_SET]
    if bad:
        return obj, "unknown_sku", f"SKUs not in catalog: {bad}"
    return obj, "ok", None


def score(obj, gold) -> dict:
    if not isinstance(obj, dict):
        return {"customer": 0, "items_exact": 0, "items_f1": 0.0, "date": 0, "city": 0, "urgent": 0, "all": 0}
    pred_items = {(i.get("sku"), i.get("quantity")) for i in obj.get("items") or [] if isinstance(i, dict)}
    gold_items = {(i["sku"], i["quantity"]) for i in gold["items"]}
    tp = len(pred_items & gold_items)
    p = tp / len(pred_items) if pred_items else 0
    r = tp / len(gold_items) if gold_items else 0
    s = {
        "customer": int(norm(obj.get("customer")) == norm(gold["customer"])),
        "items_exact": int(pred_items == gold_items),
        "items_f1": round(2 * p * r / (p + r), 3) if p + r else 0.0,
        "date": int(obj.get("delivery_date") == gold["delivery_date"]),
        "city": int(norm(obj.get("delivery_city")) == norm(gold["delivery_city"])),
        "urgent": int(obj.get("urgent") == gold["urgent"]),
    }
    s["all"] = int(all(s[k] for k in ("customer", "items_exact", "date", "city", "urgent")))
    return s
