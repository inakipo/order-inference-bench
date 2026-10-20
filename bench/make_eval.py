"""Generate a synthetic Spanish order-extraction eval set with exact gold labels.

Synthetic on purpose: realistic shapes (emails, WhatsApp, voice-note transcripts, corrections,
relative dates) without any real customer data.
"""

import datetime as dt
import json
import random
import sys
import unicodedata
from pathlib import Path

from catalog import CATALOG

rng = random.Random(7)

# How customers actually name things (several ways per product / format).
NAMES = {
    "JIB100": ["jamón de bellota 100%", "jamón ibérico 100% bellota", "pata negra de bellota 100%"],
    "JIB50": ["jamón de bellota 50%", "jamón ibérico de bellota cincuenta por ciento"],
    "JIC": ["jamón de cebo", "jamón ibérico de cebo"],
    "JSG": ["jamón serrano gran reserva", "serrano gran reserva"],
    "PIB": ["paleta de bellota", "paleta ibérica de bellota"],
    "PICB": ["paleta de cebo", "paleta ibérica de cebo"],
    "LIB": ["lomo de bellota", "lomo ibérico"],
    "CHI": ["chorizo ibérico", "chorizo"],
    "SAI": ["salchichón ibérico", "salchichón"],
    "QMC": ["manchego curado", "queso manchego curado"],
    "QMS": ["manchego semicurado", "queso semi"],
    "QOR": ["queso al romero", "queso de oveja al romero"],
    "AOP": ["aceite picual", "AOVE picual"],
    "AOA": ["aceite arbequina", "AOVE arbequina"],
    "VRC": ["Ribera crianza", "tinto Ribera crianza"],
    "VRR": ["Rioja reserva", "tinto Rioja reserva"],
    "VBA": ["Albariño", "blanco Albariño"],
    "CBN": ["cava brut nature", "cava"],
    "PPA": ["picos de pan", "picos artesanos"],
    "ALM": ["almendras marcona", "marconas fritas"],
    "ACG": ["aceitunas gordal", "gordales"],
    "ANC": ["anchoas del Cantábrico", "anchoas"],
    "BON": ["bonito del norte", "bonito en aceite"],
    "MTO": ["mermelada de tomate", "mermelada de tomate casera"],
}
FORMAT_SAY = {
    "PZ": ["piezas enteras de {p}", "{p}, piezas enteras", "patas de {p}"],
    "DH": ["{p} deshuesado", "{p} sin hueso"],
    "L80": ["sobres de 80 g de {p}", "{p} loncheado en sobres de 80", "sobres de {p} de 80 gramos"],
    "L100": ["sobres de 100 g de {p}", "{p} loncheado de 100 gramos", "sobres de cien gramos de {p}"],
    "MP": ["medias piezas de {p}", "{p}, media pieza"],
    "C250": ["cuñas de 250 de {p}", "{p} en cuñas de 250 g"],
    "MQ": ["medios quesos de {p}", "{p}, medio queso"],
    "E3": ["quesos enteros de {p}", "{p} entero de 3 kilos"],
    "B500": ["botellas de medio litro de {p}", "{p} en botella de 500"],
    "L25": ["latas de 2,5 litros de {p}", "{p} en lata de dos litros y medio"],
    "G5": ["garrafas de 5 litros de {p}", "{p} en garrafa de 5L"],
    "B75": ["botellas de {p}", "{p}, botellas sueltas"],
    "C6": ["cajas de 6 de {p}", "{p} en cajas de seis"],
    "UD": ["unidades de {p}", "{p} sueltos"],
    "C12": ["cajas de 12 de {p}", "{p} en caja de doce"],
}
WORDS = {1: "una", 2: "dos", 3: "tres", 4: "cuatro", 5: "cinco", 6: "media docena de", 10: "diez", 12: "una docena de"}
CUSTOMERS = ["Bar La Esquina", "Restaurante Casa Paco", "Gastrobar El Olivo", "Hotel Miramar", "Delicias del Sur",
             "Catering Sabores", "Taberna Los Arcos", "Vinoteca La Cepa", "Mesón El Cruce", "Ultramarinos Lola",
             "Club de Tenis Sierra", "Asador Peñalta"]
PEOPLE = ["Marta", "Javi", "Lucía", "Antonio", "Carmen", "Rubén", "Elena", "Paco", "Nuria", "Sergio"]
CITIES = ["Sevilla", "Madrid", "Valencia", "Bilbao", "Málaga", "Zaragoza", "Granada", "A Coruña"]
DAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def qty_text(q, informal):
    if informal and q in WORDS and rng.random() < 0.5:
        return WORDS[q]
    return str(q)


def item_text(item, informal):
    p = rng.choice(NAMES[item["code"]])
    phrase = rng.choice(FORMAT_SAY[item["fcode"]]).format(p=p)
    return f"{qty_text(item['quantity'], informal)} {phrase}"


def date_phrase(today):
    """Return (phrase, gold ISO date or None)."""
    r = rng.random()
    if r < 0.15:
        return None, None
    if r < 0.30:
        return "mañana", today + dt.timedelta(days=1)
    if r < 0.40:
        return "pasado mañana", today + dt.timedelta(days=2)
    if r < 0.65:
        wd = rng.choice([0, 1, 2, 3, 4])
        delta = (wd - today.weekday()) % 7 or 7
        return f"el {DAYS[wd]}", today + dt.timedelta(days=delta)
    target = today + dt.timedelta(days=rng.randint(3, 20))
    if rng.random() < 0.5:
        return f"el {target.day} de {MONTHS[target.month - 1]}", target
    return f"el {target.day}/{target.month}", target


def make_case(i):
    today = dt.date(2026, 10, 1) + dt.timedelta(days=rng.randint(0, 45))
    style = rng.choice(["email", "whatsapp", "whatsapp", "voice", "correction"])
    customer, person = rng.choice(CUSTOMERS), rng.choice(PEOPLE)
    n_items = rng.choice([1, 1, 2, 2, 3, 4])
    items = []
    for c in rng.sample(CATALOG, n_items):
        items.append({**c, "quantity": rng.choice([1, 2, 2, 3, 4, 5, 6, 10, 12, 20])})
    city = rng.choice(CITIES) if rng.random() < 0.85 else None
    dphrase, gold_date = date_phrase(today)
    urgent = rng.random() < 0.25
    informal = style != "email"
    texts = [item_text(it, informal) for it in items]

    if style == "email":
        lines = "\n".join(f"- {t}" for t in texts)
        when = f"para el {dphrase.removeprefix('el ')}" if dphrase and dphrase.startswith("el ") else (dphrase or "")
        where = f" en nuestro local de {city}" if city else ""
        msg = f"Buenos días,\n\nOs escribo de {customer} para haceros el siguiente pedido:\n{lines}\n\n"
        if dphrase or city:
            msg += f"Lo necesitaríamos {when}{where}.".replace("  ", " ") + "\n"
        if urgent:
            msg += "Es bastante urgente, os agradecería que lo priorizarais.\n"
        msg += f"\nUn saludo,\n{person}\n{customer}"
    elif style in ("whatsapp", "correction"):
        body = ", ".join(texts[:-1]) + (" y " if len(texts) > 1 else "") + texts[-1]
        msg = f"hola!! soy {person} de {customer}. ponme {body}"
        if dphrase:
            msg += f" pa {dphrase}"
        if city:
            msg += f", a {city} como siempre"
        msg += "."
        if urgent:
            msg += " es urgente porfa!!"
        if style == "correction":
            it = rng.choice(items)
            old = it["quantity"]
            new = rng.choice([q for q in [1, 2, 3, 4, 5, 6, 8, 10] if q != old])
            it["quantity"] = new
            p = rng.choice(NAMES[it["code"]])
            msg += f"\nperdona, del {p} mejor {new} en vez de {old}"
        if rng.random() < 0.5:
            msg = strip_accents(msg.lower())
    else:  # voice note transcript
        body = "... y ".join(texts)
        msg = f"vale apunta eh soy {person} de {customer}... necesito {body}"
        if dphrase:
            msg += f"... lo quiero para {dphrase}"
        if city:
            msg += f" aquí en {city}"
        if urgent:
            msg += "... y oye que lo necesitamos cuanto antes vale"
        msg += "... gracias"

    gold = {
        "customer": customer,
        "items": sorted([{"sku": it["sku"], "quantity": it["quantity"]} for it in items], key=lambda x: x["sku"]),
        "delivery_date": gold_date.isoformat() if gold_date else None,
        "delivery_city": city,
        "urgent": urgent,
    }
    return {"id": f"o{i:03d}", "style": style, "today": today.isoformat(), "weekday": DAYS[today.weekday()], "message": msg, "gold": gold}


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    out = Path(__file__).parent.parent / "data" / "eval.jsonl"
    with out.open("w") as f:
        for i in range(n):
            f.write(json.dumps(make_case(i), ensure_ascii=False) + "\n")
    print(f"wrote {n} cases to {out}")
