"""Hard tier of task 1: longer invoices with order and delivery dates as decoys, a discount line,
shipping, a deposit already paid, prices that may include VAT, and a due date given only as payment
terms ("Net 30"), so it has to be computed. Ten fields."""

from __future__ import annotations

import json
import random
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from ..common import Verdict, compare_fields, parse_json_object
from ..fakes import address, company, day_between, day_month_year, long_date, person
from .invoice_extraction import CURRENCIES, ITEMS, _money

TASK_ID = "invoice_extraction_hard"
TITLE = "Invoice field extraction (hard)"
DEFAULT_COUNT = 50
TIER = "hard"

FIELDS = {"vendor_name": "text", "invoice_number": "code", "issue_date": "date", "due_date": "date", "currency": "code",
          "net_amount": "amount", "tax": "amount", "total": "amount", "deposit_paid": "amount", "amount_due": "amount"}

SYSTEM = (
    "You extract data from invoices. Reply with one JSON object and nothing else, with exactly these keys: "
    "vendor_name (the company that issued the invoice), invoice_number, issue_date (the invoice date, not the order "
    "or delivery date), due_date (YYYY-MM-DD; if only payment terms are given, count the days from the issue date), "
    "currency (ISO 4217 code), net_amount (after discounts and shipping, before tax), tax, total (net_amount plus tax), "
    "deposit_paid (0 if none), amount_due (total minus deposit_paid). Amounts are numbers without currency symbols; "
    "all dates YYYY-MM-DD."
)

CENT = Decimal("0.01")


def generate(rng: random.Random, count: int):
    items = []
    for index in range(count):
        vendor, buyer = company(rng), company(rng)
        while buyer == vendor:
            buyer = company(rng)
        code, symbol, style = rng.choice(CURRENCIES)
        ordered = day_between(rng, date(2026, 1, 5), date(2026, 8, 31))
        delivered = ordered + timedelta(days=rng.randint(2, 12))
        issued = delivered + timedelta(days=rng.randint(0, 5))
        terms = rng.choice([14, 30, 45, 60])
        due = issued + timedelta(days=terms)
        lines = []
        for _ in range(rng.randint(4, 9)):
            quantity = rng.randint(1, 20)
            unit = Decimal(rng.randint(250, 90000)) / 100
            lines.append((rng.choice(ITEMS), quantity, unit, (unit * quantity).quantize(CENT)))
        goods = sum((line[3] for line in lines), Decimal("0"))
        discount_rate = rng.choice([Decimal("0"), Decimal("0.05"), Decimal("0.1"), Decimal("0.15")])
        discount = (goods * discount_rate).quantize(CENT, rounding=ROUND_HALF_UP)
        shipping = Decimal(rng.choice([0, 0, 1500, 2490, 4900])) / 100
        rate = rng.choice([Decimal("0.07"), Decimal("0.1"), Decimal("0.19"), Decimal("0.2")])
        vat_inclusive = rng.random() < 0.35
        if vat_inclusive:
            gross = goods - discount + shipping
            net = (gross / (1 + rate)).quantize(CENT, rounding=ROUND_HALF_UP)
            tax = gross - net
        else:
            net = goods - discount + shipping
            tax = (net * rate).quantize(CENT, rounding=ROUND_HALF_UP)
        total = net + tax
        deposit = (total * rng.choice([Decimal("0"), Decimal("0"), Decimal("0.2"), Decimal("0.3"), Decimal("0.5")])).quantize(CENT, rounding=ROUND_HALF_UP)
        due_amount = total - deposit
        number = rng.choice(["INV-", "", "F"]) + f"{rng.randint(2026000, 2026999)}" + rng.choice(["", "-B", "/26"])
        fmt = rng.choice([long_date, day_month_year, lambda d: d.isoformat()])
        m = lambda value: _money(value, symbol, style)  # noqa: E731
        street, city, _ = address(rng)
        body = [f"{line[0]:<28} {line[1]:>3} x {m(line[2]):>14} = {m(line[3]):>14}" for line in lines]
        due_text = f"Payment terms: Net {terms} days from invoice date." if rng.random() < 0.6 else f"Please pay by {fmt(due)}."
        totals = [f"Goods total: {m(goods)}"]
        if discount:
            totals.append(f"Loyalty discount {int(discount_rate * 100)}%: -{m(discount)}")
        if shipping:
            totals.append(f"Shipping and handling: {m(shipping)}")
        if vat_inclusive:
            totals += [f"Total incl. VAT: {m(total)}", f"of which VAT {int(rate * 100)}%: {m(tax)}"]
        else:
            totals += [f"Net amount: {m(net)}", f"VAT {int(rate * 100)}%: {m(tax)}", f"Invoice total: {m(total)}"]
        if deposit:
            totals.append(f"Less deposit received on {fmt(ordered)}: -{m(deposit)}")
        totals.append(f"BALANCE DUE: {m(due_amount)} ({code})")
        text = "\n".join([
            f"{vendor} - {street}, {city}", f"Customer: {buyer} (contact {person(rng)})", "",
            f"INVOICE No. {number}", f"Order date: {fmt(ordered)}", f"Delivered: {fmt(delivered)}", f"Invoice date: {fmt(issued)}",
            due_text, "", *body, "", *totals, "",
            f"Late payments after {fmt(due + timedelta(days=7))} incur a fee. Prices {'include' if vat_inclusive else 'exclude'} VAT.",
        ])
        expected = {"vendor_name": vendor, "invoice_number": number, "issue_date": issued.isoformat(), "due_date": due.isoformat(),
                    "currency": code, "net_amount": f"{net:.2f}", "tax": f"{tax:.2f}", "total": f"{total:.2f}",
                    "deposit_paid": f"{deposit:.2f}", "amount_due": f"{due_amount:.2f}"}
        items.append({"id": f"{TASK_ID}-{index + 1:03d}", "input": {"document": text}, "expected": expected})
    return items, {}


def prompt(item: dict, shared: dict | None = None) -> dict:
    return {"system": SYSTEM, "user": item["input"]["document"]}


def validate(item: dict, output: str, shared: dict | None = None) -> Verdict:
    data, error = parse_json_object(output)
    if data is None:
        return Verdict.failed(error)
    return compare_fields(item["expected"], data, FIELDS)


def reference_output(item: dict) -> str:
    expected = dict(item["expected"])
    for key in ("net_amount", "tax", "total", "deposit_paid", "amount_due"):
        expected[key] = float(expected[key])
    return json.dumps(expected)


def wrong_outputs(item: dict) -> list[str]:
    good = json.loads(reference_output(item))
    return [json.dumps(dict(good, issue_date=good["due_date"])),
            json.dumps(dict(good, amount_due=round(good["amount_due"] + 0.01, 2))),
            json.dumps(dict(good, net_amount=round(good["net_amount"] + 1, 2))),
            json.dumps({k: v for k, v in good.items() if k != "deposit_paid"})]
