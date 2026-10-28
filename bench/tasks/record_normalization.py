"""Task 9: normalise messy contact records into canonical formats. Batch-eligible bulk work."""

from __future__ import annotations

import json
import random
from datetime import date

from ..common import Verdict, compare_fields, parse_json_object
from ..fakes import FIRST_NAMES, LAST_NAMES, MONTHS, day_between

TASK_ID = "record_normalization"
TITLE = "Record normalisation (batch)"
DEFAULT_COUNT = 50

FIELDS = {"email": "exact", "phone": "exact", "country": "exact", "birth_date": "exact", "postal_code": "exact"}

SYSTEM = (
    "Normalise the contact record. Reply with one JSON object and nothing else, with exactly these keys:\n"
    "email: lower-case, surrounding spaces removed\n"
    "phone: E.164 (plus sign, country calling code, digits only, no leading trunk 0)\n"
    "country: ISO 3166-1 alpha-2 code, upper-case\n"
    "birth_date: YYYY-MM-DD\n"
    "postal_code: upper-case with the country's standard spacing (GB and CA: one space before the last 3 "
    "characters; NL: one space between digits and letters; others: no spaces)"
)

# country code -> (names as people write them, calling code, national number length, postal code builder)
COUNTRIES = {
    "GB": (["UK", "United Kingdom", "Great Britain", "england"], "44", 10, lambda r: f"{r.choice('BLMS')}{r.choice('ESW')}{r.randint(1, 9)} {r.randint(1, 9)}{r.choice('ABDEFG')}{r.choice('HJLNPQ')}"),
    "DE": (["Germany", "Deutschland", "GERMANY", "germany"], "49", 10, lambda r: f"{r.randint(10000, 99999)}"),
    "FR": (["France", "FRANCE", "france", "République française"], "33", 9, lambda r: f"{r.randint(10000, 95999)}"),
    "NL": (["Netherlands", "Holland", "The Netherlands", "NL"], "31", 9, lambda r: f"{r.randint(1000, 9999)} {r.choice('ABCDEFGHJ')}{r.choice('KLMNPRST')}"),
    "US": (["USA", "United States", "U.S.", "united states of america"], "1", 10, lambda r: f"{r.randint(10000, 99999)}"),
    "CA": (["Canada", "CANADA", "canada", "CA"], "1", 10, lambda r: f"{r.choice('KLMT')}{r.randint(1, 9)}{r.choice('ABCE')} {r.randint(1, 9)}{r.choice('GHJK')}{r.randint(1, 9)}"),
    "ES": (["Spain", "España", "spain", "ESP"], "34", 9, lambda r: f"{r.randint(10000, 52999)}"),
    "JP": (["Japan", "JAPAN", "Nippon", "jp"], "81", 10, lambda r: f"{r.randint(100, 999)}{r.randint(1000, 9999)}"),
}


def _messy_phone(rng: random.Random, calling: str, digits: str) -> str:
    style = rng.randint(0, 3)
    if style == 0:
        return f"+{calling} {digits[:3]} {digits[3:6]} {digits[6:]}"
    if style == 1:
        return f"00{calling}-{digits[:4]}-{digits[4:]}"
    if style == 2 and calling != "1":
        return f"0{digits[:3]} {digits[3:]}"  # national format with trunk 0; country comes from the record
    return f"({calling}) {digits}"


def _messy_postal(rng: random.Random, code: str) -> str:
    variants = [code.lower(), code.replace(" ", ""), f"  {code} ", code]
    return rng.choice(variants)


def generate(rng: random.Random, count: int) -> list[dict]:
    items = []
    codes = list(COUNTRIES)
    for index in range(count):
        country = codes[index % len(codes)]
        names, calling, length, postal = COUNTRIES[country]
        first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
        email = f"{first}.{last}{rng.randint(1, 99)}@example.{rng.choice(['com', 'org', 'net'])}".lower()
        digits = str(rng.randint(2, 9)) + "".join(str(rng.randint(0, 9)) for _ in range(length - 1))
        born = day_between(rng, date(1950, 1, 1), date(2004, 12, 31))
        postal_code = postal(rng).upper()
        birth_text = rng.choice([
            f"{born.day}/{born.month}/{born.year} (day first)", f"{MONTHS[born.month - 1]} {born.day} {born.year}",
            f"{born.day} {MONTHS[born.month - 1].lower()} {born.year}", f"{born.year}.{born.month:02d}.{born.day:02d}",
        ])
        record = {
            "name": f"{first} {last}",
            "email": rng.choice([email.upper(), f" {email} ", email.capitalize()]),
            "phone": _messy_phone(rng, calling, digits),
            "country": rng.choice(names),
            "dob": birth_text,
            "zip": _messy_postal(rng, postal_code),
        }
        expected = {"email": email, "phone": f"+{calling}{digits}", "country": country, "birth_date": born.isoformat(),
                    "postal_code": postal_code}
        items.append({"id": f"{TASK_ID}-{index + 1:03d}", "input": {"record": record}, "expected": expected})
    return items


def prompt(item: dict, shared: dict | None = None) -> dict:
    return {"system": SYSTEM, "user": json.dumps(item["input"]["record"], ensure_ascii=False)}


def validate(item: dict, output: str) -> Verdict:
    data, error = parse_json_object(output)
    if data is None:
        return Verdict.failed(error)
    return compare_fields(item["expected"], data, FIELDS)


def reference_output(item: dict) -> str:
    return json.dumps(item["expected"])


def wrong_outputs(item: dict) -> list[str]:
    good = item["expected"]
    return [
        json.dumps(dict(good, phone=good["phone"].replace("+", "00", 1))),
        json.dumps(dict(good, postal_code=good["postal_code"][:2] + " " + good["postal_code"][2:])),
        json.dumps(dict(good, country=good["country"].lower())),
        json.dumps(dict(good, birth_date=good["birth_date"].replace("-", "/"))),
    ]
