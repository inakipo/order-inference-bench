"""Product catalog of a (fictional) Spanish gourmet distributor, the prompt, and the output schema."""

from typing import Literal, Optional

from pydantic import BaseModel, Field

FORMATS = {
    "ham": [("PZ", "pieza entera"), ("DH", "deshuesado"), ("L80", "loncheado, sobre 80 g"), ("L100", "loncheado, sobre 100 g")],
    "cured": [("PZ", "pieza"), ("MP", "media pieza"), ("L100", "loncheado, sobre 100 g")],
    "cheese": [("C250", "cuña 250 g"), ("MQ", "medio queso"), ("E3", "queso entero 3 kg")],
    "oil": [("B500", "botella 500 ml"), ("L25", "lata 2,5 L"), ("G5", "garrafa 5 L")],
    "wine": [("B75", "botella 75 cl"), ("C6", "caja 6 botellas")],
    "pantry": [("UD", "unidad"), ("C12", "caja 12 unidades")],
}

PRODUCTS = [
    ("JIB100", "Jamón ibérico de bellota 100%", "ham"),
    ("JIB50", "Jamón ibérico de bellota 50%", "ham"),
    ("JIC", "Jamón ibérico de cebo", "ham"),
    ("JSG", "Jamón serrano gran reserva", "ham"),
    ("PIB", "Paleta ibérica de bellota", "ham"),
    ("PICB", "Paleta ibérica de cebo", "ham"),
    ("LIB", "Lomo ibérico de bellota", "cured"),
    ("CHI", "Chorizo ibérico", "cured"),
    ("SAI", "Salchichón ibérico", "cured"),
    ("QMC", "Queso manchego curado", "cheese"),
    ("QMS", "Queso manchego semicurado", "cheese"),
    ("QOR", "Queso de oveja al romero", "cheese"),
    ("AOP", "Aceite de oliva virgen extra picual", "oil"),
    ("AOA", "Aceite de oliva virgen extra arbequina", "oil"),
    ("VRC", "Vino tinto Ribera del Duero crianza", "wine"),
    ("VRR", "Vino tinto Rioja reserva", "wine"),
    ("VBA", "Vino blanco Albariño", "wine"),
    ("CBN", "Cava brut nature", "wine"),
    ("PPA", "Picos de pan artesanos", "pantry"),
    ("ALM", "Almendras marcona fritas", "pantry"),
    ("ACG", "Aceitunas gordal", "pantry"),
    ("ANC", "Anchoas del Cantábrico", "pantry"),
    ("BON", "Bonito del norte en aceite", "pantry"),
    ("MTO", "Mermelada de tomate", "pantry"),
]

CATALOG = [
    {"sku": f"{code}-{fcode}", "product": name, "format": fdesc, "code": code, "fcode": fcode, "kind": kind}
    for code, name, kind in PRODUCTS
    for fcode, fdesc in FORMATS[kind]
]
SKUS = [c["sku"] for c in CATALOG]


class Item(BaseModel):
    sku: str
    quantity: int = Field(ge=1)


class Order(BaseModel):
    customer: str
    items: list[Item]
    delivery_date: Optional[str] = Field(description="YYYY-MM-DD or null")
    delivery_city: Optional[str]
    urgent: bool


def json_schema(enum_skus: bool = True) -> dict:
    """Plain JSON schema (no $refs) so every provider can read it. enum_skus pins items to real SKUs."""
    sku = {"type": "string", "enum": SKUS} if enum_skus else {"type": "string"}
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["customer", "items", "delivery_date", "delivery_city", "urgent"],
        "properties": {
            "customer": {"type": "string"},
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["sku", "quantity"],
                    "properties": {"sku": sku, "quantity": {"type": "integer", "minimum": 1}},
                },
            },
            "delivery_date": {"type": ["string", "null"]},
            "delivery_city": {"type": ["string", "null"]},
            "urgent": {"type": "boolean"},
        },
    }


def system_prompt() -> str:
    # Stable prefix on purpose: no dates or per-request data here, so prefix caching can reuse it.
    lines = "\n".join(f"{c['sku']} | {c['product']} | {c['format']}" for c in CATALOG)
    return f"""Eres el sistema de entrada de pedidos de un distribuidor gourmet. Recibes mensajes de clientes (emails, WhatsApp, notas de voz transcritas) y devuelves el pedido como JSON.

Reglas:
- customer: nombre del negocio que pide (no el de la persona).
- items: cada producto con su SKU exacto del catálogo y la cantidad (entero). Si el cliente corrige una cantidad, usa la última.
- delivery_date: fecha de entrega en formato YYYY-MM-DD, calculada a partir de la fecha de hoy que viene en el mensaje. null si no la dicen.
- delivery_city: ciudad de entrega, o null si no la dicen.
- urgent: true solo si el cliente dice que es urgente o que lo necesita cuanto antes.
- Responde SOLO con el JSON, sin texto antes ni después.

Formato:
{{"customer": "...", "items": [{{"sku": "...", "quantity": 1}}], "delivery_date": "YYYY-MM-DD" | null, "delivery_city": "..." | null, "urgent": false}}

Ejemplos:
Fecha de hoy: 2026-09-14 (lunes)
Mensaje: "buenas soy ana del bar central, mandame 3 sobres de 80 de jamon de bellota 100% y una garrafa de aceite arbequina pal jueves a cadiz"
{{"customer": "Bar Central", "items": [{{"sku": "JIB100-L80", "quantity": 3}}, {{"sku": "AOA-G5", "quantity": 1}}], "delivery_date": "2026-09-17", "delivery_city": "Cádiz", "urgent": false}}

Fecha de hoy: 2026-09-18 (viernes)
Mensaje: "Hola, de parte de Hotel Las Dunas: dos cajas de 6 de cava. Lo necesitamos cuanto antes. Gracias."
{{"customer": "Hotel Las Dunas", "items": [{{"sku": "CBN-C6", "quantity": 2}}], "delivery_date": null, "delivery_city": null, "urgent": true}}

Fecha de hoy: 2026-09-21 (lunes)
Mensaje: "soy pedro de vinos y tapas, ponme 4 medios quesos de manchego curado para mañana en Toledo. perdona, mejor 5 en vez de 4"
{{"customer": "Vinos y Tapas", "items": [{{"sku": "QMC-MQ", "quantity": 5}}], "delivery_date": "2026-09-22", "delivery_city": "Toledo", "urgent": false}}

Catálogo (SKU | producto | formato):
{lines}"""


DAYS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def calendar(today_iso: str) -> str:
    """Workaround for weak date arithmetic: resolve relative dates in code, let the model only pick one."""
    import datetime as dt

    today = dt.date.fromisoformat(today_iso)
    lines = [f"mañana = {today + dt.timedelta(days=1)}", f"pasado mañana = {today + dt.timedelta(days=2)}"]
    for wd, name in enumerate(DAYS_ES):
        delta = (wd - today.weekday()) % 7 or 7
        lines.append(f"el {name} (el próximo) = {today + dt.timedelta(days=delta)}")
    return "Calendario de referencia (ya calculado, úsalo tal cual):\n" + "\n".join(lines)


def user_prompt(case: dict, with_calendar: bool = False) -> str:
    cal = f"\n{calendar(case['today'])}\n" if with_calendar else ""
    return f"Fecha de hoy: {case['today']} ({case['weekday']})\n{cal}\nMensaje del cliente:\n{case['message']}"


Mode = Literal["prompt", "json_schema"]
