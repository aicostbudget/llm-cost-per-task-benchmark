"""Hard tier of task 3: a deeper schema, imperial units to convert, a was/now price, stock given in
words, and variants with SKUs."""

from __future__ import annotations

import json
import random
from decimal import ROUND_HALF_UP, Decimal

from ..common import Verdict, compare_fields, parse_json_object
from ..schema import validate as validate_schema
from .strict_json import BRANDS, CATEGORIES, COLORS, PRODUCTS

TASK_ID = "strict_json_hard"
TITLE = "Strict JSON schema output (hard)"
DEFAULT_COUNT = 50
TIER = "hard"

GRAMS_PER_LB = Decimal("453.59237")
GRAMS_PER_OZ = Decimal("28.349523125")
MM_PER_IN = Decimal("25.4")

SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["name", "brand", "category", "price", "stock_quantity", "weight_grams", "dimensions_mm", "variants"],
    "properties": {
        "name": {"type": "string"},
        "brand": {"type": "string"},
        "category": {"type": "string", "enum": CATEGORIES},
        "price": {"type": "object", "additionalProperties": False, "required": ["amount", "currency"],
                  "properties": {"amount": {"type": "number", "minimum": 0}, "currency": {"type": "string", "pattern": "^[A-Z]{3}$"}}},
        "stock_quantity": {"type": "integer", "minimum": 0},
        "weight_grams": {"type": "integer", "minimum": 0},
        "dimensions_mm": {"type": "object", "additionalProperties": False, "required": ["length", "width", "height"],
                          "properties": {k: {"type": "integer", "minimum": 0} for k in ("length", "width", "height")}},
        "variants": {"type": "array", "minItems": 1, "maxItems": 5, "items": {
            "type": "object", "additionalProperties": False, "required": ["color", "sku"],
            "properties": {"color": {"type": "string"}, "sku": {"type": "string"}}}},
    },
}

SYSTEM = (
    "Convert the product listing into one JSON object that conforms to this JSON Schema. Reply with the JSON only. "
    "price is the current selling price. stock_quantity is the number of units in stock (0 if none). Convert pounds "
    "and ounces to grams and inches to millimetres (1 lb = 453.59237 g, 1 oz = 28.349523125 g, 1 in = 25.4 mm) and "
    "round each result to the nearest whole number. Dimensions are given as length x width x height. Colors are "
    "lower-case.\n" + json.dumps(SCHEMA, indent=2)
)

CURRENCY_SYMBOL = {"USD": "$", "GBP": "£", "CAD": "CA$"}


def _round(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def generate(rng: random.Random, count: int):
    items = []
    for index in range(count):
        category = CATEGORIES[index % len(CATEGORIES)]
        product = rng.choice(PRODUCTS[category])
        brand = rng.choice(BRANDS)
        name = f"{brand} {product.title()}"
        currency = rng.choice(list(CURRENCY_SYMBOL))
        symbol = CURRENCY_SYMBOL[currency]
        was = Decimal(rng.randint(1999, 39999)) / 100
        now = (was * Decimal(rng.choice(["0.7", "0.75", "0.8", "0.85", "1"]))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if rng.random() < 0.5:
            pounds = Decimal(rng.randint(5, 180)) / 10
            weight_text, grams = f"{pounds} lb", _round(pounds * GRAMS_PER_LB)
        else:
            ounces = Decimal(rng.randint(3, 60))
            weight_text, grams = f"{ounces} oz", _round(ounces * GRAMS_PER_OZ)
        dims_in = [Decimal(rng.randint(20, 400)) / 10 for _ in range(3)]
        dims_mm = [_round(d * MM_PER_IN) for d in dims_in]
        stock = rng.choice([0, 0, 2, 3, 7, 12, 40])
        stock_text = {0: rng.choice(["Sold out for now.", "Currently out of stock, back in three weeks."]),
                      2: "Only 2 left!", 3: "Hurry, just three left in stock."}.get(stock, f"{stock} units in stock.")
        colors = rng.sample(COLORS, rng.randint(1, 4))
        stem = f"{brand[:2].upper()}-{rng.randint(1000, 9999)}"
        variants = [{"color": c, "sku": f"{stem}-{c[:2].upper()}{i}"} for i, c in enumerate(colors)]
        variant_text = "; ".join(f"{v['color']} (SKU {v['sku']})" for v in variants)
        price_text = f"{symbol}{now:.2f} (was {symbol}{was:.2f})" if now != was else f"{symbol}{now:.2f}"
        description = rng.choice([
            f"{name} - {price_text}. Weight: {weight_text}. Size: {dims_in[0]} x {dims_in[1]} x {dims_in[2]} in (L x W x H). Variants: {variant_text}. {stock_text}",
            f"{stock_text} The {name} from {brand} measures {dims_in[0]} in long, {dims_in[1]} in wide and {dims_in[2]} in high, weighs {weight_text} and sells for {price_text}. Available as {variant_text}.",
        ]) + f" Listed in our {category} department."
        expected = {"brand": brand, "category": category, "amount": f"{now:.2f}", "currency": currency, "stock_quantity": stock,
                    "weight_grams": grams, "dimensions_mm": {"length": dims_mm[0], "width": dims_mm[1], "height": dims_mm[2]},
                    "variants": sorted([v["color"], v["sku"]] for v in variants), "name": name}
        items.append({"id": f"{TASK_ID}-{index + 1:03d}", "input": {"description": description}, "expected": expected})
    return items, {}


def prompt(item: dict, shared: dict | None = None) -> dict:
    return {"system": SYSTEM, "user": item["input"]["description"]}


def validate(item: dict, output: str, shared: dict | None = None) -> Verdict:
    data, error = parse_json_object(output)
    if data is None:
        return Verdict.failed(error)
    problem = validate_schema(data, SCHEMA)
    if problem:
        return Verdict.failed(f"schema: {problem}")
    e = item["expected"]
    flat = {"brand": data["brand"], "category": data["category"], "amount": data["price"]["amount"], "currency": data["price"]["currency"],
            "stock_quantity": data["stock_quantity"], "weight_grams": data["weight_grams"]}
    verdict = compare_fields(e, flat, {"brand": "text", "category": "exact", "amount": "amount", "currency": "exact",
                                       "stock_quantity": "exact", "weight_grams": "exact"})
    if not verdict.ok:
        return verdict
    if data["dimensions_mm"] != e["dimensions_mm"]:
        return Verdict.failed(f"dimensions_mm: expected {e['dimensions_mm']}, got {data['dimensions_mm']}")
    got = sorted([v["color"].strip().lower(), v["sku"].strip().upper()] for v in data["variants"])
    if got != e["variants"]:
        return Verdict.failed(f"variants: expected {e['variants']}, got {got}")
    return Verdict.passed()


def reference_output(item: dict) -> str:
    e = item["expected"]
    return json.dumps({"name": e["name"], "brand": e["brand"], "category": e["category"],
                       "price": {"amount": float(e["amount"]), "currency": e["currency"]}, "stock_quantity": e["stock_quantity"],
                       "weight_grams": e["weight_grams"], "dimensions_mm": e["dimensions_mm"],
                       "variants": [{"color": c, "sku": s} for c, s in e["variants"]]})


def wrong_outputs(item: dict) -> list[str]:
    good = json.loads(reference_output(item))
    swapped = dict(good, dimensions_mm={"length": good["dimensions_mm"]["width"], "width": good["dimensions_mm"]["length"], "height": good["dimensions_mm"]["height"]})
    out = [json.dumps(dict(good, weight_grams=good["weight_grams"] + 1)), json.dumps(dict(good, stock_quantity=good["stock_quantity"] + 1)),
           json.dumps(dict(good, variants=good["variants"][:-1] or [{"color": "x", "sku": "y"}]))]
    if swapped["dimensions_mm"] != good["dimensions_mm"]:
        out.append(json.dumps(swapped))
    return out
