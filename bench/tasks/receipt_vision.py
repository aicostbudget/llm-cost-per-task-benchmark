"""Task 2: read merchant, date and total from a receipt image (vision input).

Receipts are rendered by our own generator, so there is no licence question and no chance the
images are in a training set. Each one has decoy amounts (subtotal, tax, cash given, change)."""

from __future__ import annotations

import io
import json
import random
from datetime import date

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from ..common import Verdict, compare_fields, parse_json_object
from ..fakes import COMPANY_PARTS_A, day_between, day_month_year

TASK_ID = "receipt_vision"
TITLE = "Receipt image extraction (vision)"
DEFAULT_COUNT = 30

FIELDS = {"merchant": "text", "date": "date", "total": "amount"}
SYSTEM = ("Read the receipt image. Reply with one JSON object and nothing else: "
          '{"merchant": the store name printed at the top, "date": YYYY-MM-DD, "total": the amount paid as a number}.')

SHOP_KINDS = ["Market", "Bakery", "Pharmacy", "Hardware", "Books", "Deli", "Garden Centre", "Cafe"]
GOODS = ["Sourdough loaf", "Oat milk 1L", "Batteries AA x4", "Notebook A5", "Tomatoes 500g", "Coffee beans",
         "Hand soap", "Light bulb E27", "Seed mix", "Croissant", "Olive oil", "Paper towels", "Apples 1kg", "Tape"]


def _font(size: int) -> ImageFont.ImageFont:
    return ImageFont.load_default(size=size)


def render(rng: random.Random, merchant: str, day: date, lines: list[tuple[str, float]], tax_rate: float) -> tuple[bytes, float]:
    subtotal = round(sum(price for _, price in lines), 2)
    tax = round(subtotal * tax_rate, 2)
    total = round(subtotal + tax, 2)
    cash = float(int(total // 10 + 1) * 10)
    width = 420
    rows: list[tuple[str, str, int]] = [(merchant.upper(), "", 26), (f"{rng.randint(1, 200)} Market Street", "", 16), ("", "", 10)]
    date_text = rng.choice([day.strftime("%b %d, %Y"), day_month_year(day), day.isoformat()])
    rows.append((f"Date: {date_text}", f"Till {rng.randint(1, 9)}", 16))
    rows.append(("-" * 44, "", 16))
    rows += [(name, f"{price:.2f}", 18) for name, price in lines]
    rows.append(("-" * 44, "", 16))
    rows += [("Subtotal", f"{subtotal:.2f}", 18), (f"VAT {int(tax_rate * 100)}%", f"{tax:.2f}", 18), ("TOTAL", f"{total:.2f}", 24),
             ("Cash", f"{cash:.2f}", 18), ("Change", f"{cash - total:.2f}", 18), ("", "", 10), ("Thank you for shopping local!", "", 16)]
    height = sum(size + 10 for _, _, size in rows) + 40
    image = Image.new("L", (width, height), color=rng.randint(235, 252))
    draw = ImageDraw.Draw(image)
    y = 20
    for left, right, size in rows:
        font = _font(size)
        ink = rng.randint(10, 60)
        draw.text((20, y), left, fill=ink, font=font)
        if right:
            right_width = draw.textlength(right, font=font)
            draw.text((width - 20 - right_width, y), right, fill=ink, font=font)
        y += size + 10
    image = image.rotate(rng.uniform(-2.5, 2.5), expand=True, fillcolor=255).filter(ImageFilter.GaussianBlur(rng.uniform(0, 0.6)))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue(), total


def generate(rng: random.Random, count: int):
    items, files = [], {}
    for index in range(count):
        merchant = f"{rng.choice(COMPANY_PARTS_A)} {rng.choice(SHOP_KINDS)}"
        day = day_between(rng, date(2026, 1, 1), date(2026, 9, 30))
        lines = [(name, round(rng.randint(80, 2400) / 100, 2)) for name in rng.sample(GOODS, rng.randint(2, 7))]
        png, total = render(rng, merchant, day, lines, rng.choice([0.0, 0.07, 0.1, 0.2]))
        item_id = f"{TASK_ID}-{index + 1:03d}"
        path = f"images/{item_id}.png"
        files[path] = png
        items.append({"id": item_id, "input": {"image": path},
                      "expected": {"merchant": merchant, "date": day.isoformat(), "total": f"{total:.2f}"}})
    return items, {"files": files}


def prompt(item: dict, shared: dict | None = None) -> dict:
    return {"system": SYSTEM, "user": "Extract the fields from this receipt.", "images": [item["input"]["image"]]}


def validate(item: dict, output: str, shared: dict | None = None) -> Verdict:
    data, error = parse_json_object(output)
    if data is None:
        return Verdict.failed(error)
    return compare_fields(item["expected"], data, FIELDS)


def reference_output(item: dict) -> str:
    return json.dumps(dict(item["expected"], total=float(item["expected"]["total"])))


def wrong_outputs(item: dict) -> list[str]:
    good = json.loads(reference_output(item))
    return [json.dumps(dict(good, total=round(good["total"] - 0.01, 2))), json.dumps(dict(good, merchant="Receipt")),
            json.dumps({k: v for k, v in good.items() if k != "date"})]
