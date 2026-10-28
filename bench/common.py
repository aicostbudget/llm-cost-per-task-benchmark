"""Shared helpers: parsing model output and normalising values before exact comparison.

Every validator in this package is deterministic: the same output always gets the same verdict,
and no model is asked to judge another model.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation


@dataclass(frozen=True)
class Verdict:
    ok: bool
    reason: str = ""

    @staticmethod
    def passed() -> "Verdict":
        return Verdict(True, "")

    @staticmethod
    def failed(reason: str) -> "Verdict":
        return Verdict(False, reason)


_FENCE = re.compile(r"^\s*```[a-zA-Z0-9_-]*\s*\n(.*?)\n\s*```\s*$", re.S)


def strip_fence(text: str) -> str:
    """Remove one surrounding Markdown code fence, which many models add even when told not to."""
    match = _FENCE.match(text)
    return match.group(1) if match else text.strip()


def parse_json_object(text: str) -> tuple[dict | None, str]:
    """Parse the output as one JSON object. Leading prose is not accepted: apps parse the raw reply."""
    body = strip_fence(text)
    try:
        value = json.loads(body)
    except json.JSONDecodeError as error:
        return None, f"output is not valid JSON ({error.msg} at line {error.lineno} column {error.colno})"
    if not isinstance(value, dict):
        return None, f"output is JSON {type(value).__name__}, expected an object"
    return value, ""


def norm_text(value: object) -> str:
    """Case-fold, trim and collapse inner whitespace."""
    return re.sub(r"\s+", " ", str(value)).strip().casefold()


def norm_amount(value: object) -> Decimal | None:
    """Money to 2 decimal places. Accepts numbers or strings like "1,234.50", "$1234.5", "1.234,50 €"."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        raw = repr(value) if isinstance(value, float) else str(value)
    else:
        raw = re.sub(r"[^\d,.\-]", "", str(value))
        if raw.count(",") and raw.count("."):
            # The separator that appears last is the decimal separator.
            if raw.rfind(",") > raw.rfind("."):
                raw = raw.replace(".", "").replace(",", ".")
            else:
                raw = raw.replace(",", "")
        elif raw.count(",") == 1 and len(raw.split(",")[1]) == 2:
            raw = raw.replace(",", ".")
        else:
            raw = raw.replace(",", "")
    try:
        return Decimal(raw).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return None


def norm_iso_date(value: object) -> str | None:
    """Only ISO YYYY-MM-DD is accepted: the prompts ask for it, and accepting other formats would hide failures."""
    text = str(value).strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return None
    try:
        date.fromisoformat(text)
    except ValueError:
        return None
    return text


def compare_fields(expected: dict, actual: dict, rules: dict[str, str]) -> Verdict:
    """Compare required fields with a normaliser per field: text, amount, date, exact, code (upper-case trimmed)."""
    missing = [name for name in rules if name not in actual]
    if missing:
        return Verdict.failed(f"missing field(s): {', '.join(missing)}")
    for name, rule in rules.items():
        want, got = expected[name], actual[name]
        if rule == "text":
            same = norm_text(got) == norm_text(want)
        elif rule == "amount":
            parsed = norm_amount(got)
            same = parsed is not None and parsed == norm_amount(want)
        elif rule == "date":
            same = norm_iso_date(got) == want
        elif rule == "code":
            same = str(got).strip().upper() == str(want).upper()
        elif rule == "exact":
            same = got == want
        else:
            raise ValueError(f"unknown rule {rule}")
        if not same:
            return Verdict.failed(f"{name}: expected {want!r}, got {got!r}")
    return Verdict.passed()
