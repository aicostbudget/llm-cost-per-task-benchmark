"""Task 1: pull eight fields out of a plain-text invoice."""

from __future__ import annotations

import json
import random
from datetime import date, timedelta
from decimal import Decimal

from ..common import Verdict, compare_fields, parse_json_object
from ..fakes import address, company, day_between, day_month_year, long_date, person

TASK_ID = "invoice_extraction"
TITLE = "Invoice field extraction"
DEFAULT_COUNT = 50

FIELDS = {
    "vendor_name": "text",
    "invoice_number": "code",
    "issue_date": "date",
    "due_date": "date",
    "currency": "code",
    "subtotal": "amount",
    "tax": "amount",
    "total": "amount",
}

SYSTEM = (
    "You extract data from invoices. Reply with one JSON object and nothing else, with exactly these keys: "
    "vendor_name (the company that issued the invoice), invoice_number, issue_date, due_date (both YYYY-MM-DD), "
    "currency (ISO 4217 code), subtotal, tax, total (numbers, no currency symbols)."
)

ITEMS = ["Consulting hours", "Cloud hosting (monthly)", "A4 paper, 5 boxes", "Laptop stand", "Freight surcharge",
         "Annual support plan", "Label printer ribbons", "Workshop facilitation", "Data cleanup", "Office chairs",
         "Catering, team offsite", "Domain renewal", "Packaging tape (case)", "Site survey", "License seats"]
CURRENCIES = [("USD", "$", "en"), ("EUR", "€", "eu"), ("GBP", "£", "en"), ("CAD", "CA$", "en"), ("AUD", "A$", "en")]


def _money(amount: Decimal, symbol: str, style: str) -> str:
    whole, cents = f"{amount:.2f}".split(".")
    grouped = f"{int(whole):,}"
    if style == "eu":
        return f"{grouped.replace(',', '.')},{cents} {symbol}"
    return f"{symbol}{grouped}.{cents}"


def generate(rng: random.Random, count: int) -> list[dict]:
    items = []
    for index in range(count):
        vendor = company(rng)
        buyer = company(rng)
        while buyer == vendor:
            buyer = company(rng)
        code, symbol, style = rng.choice(CURRENCIES)
        issued = day_between(rng, date(2026, 1, 5), date(2026, 9, 30))
        due = issued + timedelta(days=rng.choice([14, 15, 30, 45, 60]))
        lines = []
        for _ in range(rng.randint(2, 6)):
            quantity = rng.randint(1, 12)
            unit = Decimal(rng.randint(500, 250000)) / 100
            lines.append((rng.choice(ITEMS), quantity, unit, unit * quantity))
        subtotal = sum((line[3] for line in lines), Decimal("0"))
        rate = rng.choice([Decimal("0"), Decimal("0.05"), Decimal("0.08"), Decimal("0.1"), Decimal("0.19"), Decimal("0.2")])
        tax = (subtotal * rate).quantize(Decimal("0.01"))
        total = subtotal + tax
        number = rng.choice(["INV-", "", "No. ", "F"]) + f"{rng.randint(2026000, 2026999)}" + rng.choice(["", "-A", "/26"])
        street, city, _country = address(rng)
        date_style = rng.choice([long_date, day_month_year, lambda d: d.isoformat()])
        layout = rng.randint(0, 2)
        body_lines = [f"{line[0]:<28} {line[1]:>3} x {_money(line[2], symbol, style):>14} = {_money(line[3], symbol, style):>14}"
                      for line in lines]
        rate_label = f"{int(rate * 100)}%"
        if layout == 0:
            text = "\n".join([
                vendor.upper(), f"{street}, {city}", "", f"INVOICE {number}",
                f"Date of issue: {date_style(issued)}", f"Payment due: {date_style(due)}",
                f"Bill to: {buyer}, attn. {person(rng)}", "", *body_lines, "",
                f"Subtotal: {_money(subtotal, symbol, style)}", f"Tax ({rate_label}): {_money(tax, symbol, style)}",
                f"TOTAL DUE: {_money(total, symbol, style)}", f"All amounts in {code}.",
            ])
        elif layout == 1:
            text = "\n".join([
                f"Bill to: {buyer}", f"From: {vendor}", f"Invoice #: {number}",
                f"Issued {date_style(issued)} | Due {date_style(due)}", "-" * 40, *body_lines, "-" * 40,
                f"Net {_money(subtotal, symbol, style)}", f"VAT {rate_label} {_money(tax, symbol, style)}",
                f"Gross {_money(total, symbol, style)} ({code})",
                f"Questions? Contact {person(rng)} at {vendor}.",
            ])
        else:
            text = "\n".join([
                f"{vendor} | {street} | {city}",
                f"Customer: {buyer}",
                f"Reference {number}; invoice date {date_style(issued)}; please pay by {date_style(due)}.",
                "", "Item | Qty | Unit | Amount", *[" | ".join([l[0], str(l[1]), _money(l[2], symbol, style), _money(l[3], symbol, style)]) for l in lines],
                "", f"Amount before tax {_money(subtotal, symbol, style)}; sales tax {_money(tax, symbol, style)}; "
                f"amount payable {_money(total, symbol, style)} [{code}]",
            ])
        expected = {
            "vendor_name": vendor, "invoice_number": number, "issue_date": issued.isoformat(), "due_date": due.isoformat(),
            "currency": code, "subtotal": f"{subtotal:.2f}", "tax": f"{tax:.2f}", "total": f"{total:.2f}",
        }
        items.append({"id": f"{TASK_ID}-{index + 1:03d}", "input": {"document": text}, "expected": expected})
    return items


def prompt(item: dict, shared: dict | None = None) -> dict:
    return {"system": SYSTEM, "user": item["input"]["document"]}


def validate(item: dict, output: str) -> Verdict:
    data, error = parse_json_object(output)
    if data is None:
        return Verdict.failed(error)
    return compare_fields(item["expected"], data, FIELDS)


def reference_output(item: dict) -> str:
    expected = dict(item["expected"])
    for key in ("subtotal", "tax", "total"):
        expected[key] = float(expected[key])
    return json.dumps(expected)


def wrong_outputs(item: dict) -> list[str]:
    good = json.loads(reference_output(item))
    swapped = dict(good, issue_date=good["due_date"], due_date=good["issue_date"])
    off_by_cent = dict(good, total=round(good["total"] + 0.01, 2))
    buyer_as_vendor = dict(good, vendor_name="Someone Else Ltd")
    missing = {k: v for k, v in good.items() if k != "tax"}
    return [json.dumps(swapped), json.dumps(off_by_cent), json.dumps(buyer_as_vendor), json.dumps(missing),
            "Here is the data: " + json.dumps(good)]
