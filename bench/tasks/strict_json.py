"""Task 3: turn a free-text product description into JSON that must pass a strict schema."""

from __future__ import annotations

import json
import random

from ..common import Verdict, compare_fields, parse_json_object
from ..schema import validate as validate_schema

TASK_ID = "strict_json"
TITLE = "Strict JSON schema output"
DEFAULT_COUNT = 50

CATEGORIES = ["audio", "computing", "home", "kitchen", "outdoor", "office", "fitness", "toys"]

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["name", "brand", "category", "price", "in_stock", "colors", "weight_grams"],
    "properties": {
        "name": {"type": "string", "maxLength": 80},
        "brand": {"type": "string"},
        "category": {"type": "string", "enum": CATEGORIES},
        "price": {
            "type": "object",
            "additionalProperties": False,
            "required": ["amount", "currency"],
            "properties": {
                "amount": {"type": "number", "minimum": 0},
                "currency": {"type": "string", "pattern": "^[A-Z]{3}$"},
            },
        },
        "in_stock": {"type": "boolean"},
        "colors": {"type": "array", "minItems": 1, "maxItems": 5, "items": {"type": "string"}},
        "weight_grams": {"type": "integer", "minimum": 0},
    },
}

SYSTEM = (
    "Convert the product description into one JSON object that conforms to this JSON Schema. Reply with the JSON "
    "only. Colors are lower-case English color words. weight_grams is an integer number of grams.\n"
    + json.dumps(SCHEMA, indent=2)
)

PRODUCTS = {
    "audio": ["wireless earbuds", "bookshelf speaker", "studio headphones", "portable radio"],
    "computing": ["mechanical keyboard", "USB-C dock", "27-inch monitor", "wireless mouse"],
    "home": ["table lamp", "air purifier", "throw blanket", "wall clock"],
    "kitchen": ["chef's knife", "pour-over kettle", "cast iron skillet", "spice grinder"],
    "outdoor": ["camping lantern", "trail backpack", "camping stove", "water filter bottle"],
    "office": ["standing desk mat", "label maker", "desk organizer", "whiteboard"],
    "fitness": ["yoga mat", "adjustable dumbbell", "jump rope", "foam roller"],
    "toys": ["wooden train set", "puzzle cube", "building blocks kit", "plush fox"],
}
BRANDS = ["Arvo", "Tindra", "Nok", "Velis", "Brookstead", "Quillo", "Marrow & Pine", "Hexlight", "Solenne", "Kaito"]
COLORS = ["black", "white", "red", "blue", "green", "grey", "yellow", "orange", "pink", "brown", "beige", "navy"]
CURRENCY_TEXT = {"USD": ("${:.2f}", "US dollars"), "EUR": ("€{:.2f}", "euros"), "GBP": ("£{:.2f}", "pounds")}
STOCK_TEXT = {True: ["Ships today.", "In stock and ready to ship.", "Available now."],
              False: ["Currently sold out; restock expected next month.", "Out of stock.", "Back-ordered."]}


def generate(rng: random.Random, count: int) -> list[dict]:
    items = []
    for index in range(count):
        category = CATEGORIES[index % len(CATEGORIES)]
        product = rng.choice(PRODUCTS[category])
        brand = rng.choice(BRANDS)
        colors = rng.sample(COLORS, rng.randint(1, 4))
        currency = rng.choice(list(CURRENCY_TEXT))
        amount = round(rng.randint(399, 49999) / 100, 2)
        in_stock = rng.random() < 0.65
        weight_g = rng.randint(40, 9000)
        weight_text = f"{weight_g / 1000:g} kg" if weight_g >= 1000 and rng.random() < 0.6 else f"{weight_g} g"
        price_format, currency_words = CURRENCY_TEXT[currency]
        price_text = price_format.format(amount) if rng.random() < 0.7 else f"{amount:.2f} {currency_words}"
        name = f"{brand} {product.title()}"
        color_text = ", ".join(colors[:-1]) + (" and " if len(colors) > 1 else "") + colors[-1]
        description = rng.choice([
            f"Meet the {name}. Comes in {color_text}. It weighs {weight_text} and sells for {price_text}. {rng.choice(STOCK_TEXT[in_stock])}",
            f"{rng.choice(STOCK_TEXT[in_stock])} {name} by {brand}: {weight_text}, finishes: {color_text}. Price {price_text}.",
            f"New from {brand}: the {product} ({name}). Price: {price_text}. Weight {weight_text}. Colours available: {color_text}. {rng.choice(STOCK_TEXT[in_stock])}",
        ])
        # The category is stated, not left to judgement: several products fit more than one department.
        description += f" Listed in our {category} department."
        expected = {"name": name, "brand": brand, "category": category, "amount": amount, "currency": currency,
                    "in_stock": in_stock, "colors": sorted(colors), "weight_grams": weight_g}
        items.append({"id": f"{TASK_ID}-{index + 1:03d}", "input": {"description": description}, "expected": expected})
    return items


def prompt(item: dict, shared: dict | None = None) -> dict:
    return {"system": SYSTEM, "user": item["input"]["description"]}


def validate(item: dict, output: str) -> Verdict:
    data, error = parse_json_object(output)
    if data is None:
        return Verdict.failed(error)
    schema_error = validate_schema(data, SCHEMA)
    if schema_error:
        return Verdict.failed(f"schema: {schema_error}")
    expected = item["expected"]
    flat = {"brand": data["brand"], "category": data["category"], "amount": data["price"]["amount"],
            "currency": data["price"]["currency"], "in_stock": data["in_stock"], "weight_grams": data["weight_grams"]}
    verdict = compare_fields(expected, flat, {"brand": "text", "category": "exact", "amount": "amount",
                                              "currency": "exact", "in_stock": "exact", "weight_grams": "exact"})
    if not verdict.ok:
        return verdict
    if sorted(c.strip().lower() for c in data["colors"]) != expected["colors"]:
        return Verdict.failed(f"colors: expected {expected['colors']}, got {data['colors']}")
    return Verdict.passed()


def reference_output(item: dict) -> str:
    e = item["expected"]
    return json.dumps({"name": e["name"], "brand": e["brand"], "category": e["category"],
                       "price": {"amount": e["amount"], "currency": e["currency"]}, "in_stock": e["in_stock"],
                       "colors": e["colors"], "weight_grams": e["weight_grams"]})


def wrong_outputs(item: dict) -> list[str]:
    good = json.loads(reference_output(item))
    extra = dict(good, sku="X1")
    string_price = dict(good, price={"amount": str(good["price"]["amount"]), "currency": good["price"]["currency"]})
    kilos = dict(good, weight_grams=good["weight_grams"] / 1000)
    flipped = dict(good, in_stock=not good["in_stock"])
    return [json.dumps(extra), json.dumps(string_price), json.dumps(kilos), json.dumps(flipped), json.dumps(good)[:-1]]
