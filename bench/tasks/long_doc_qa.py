"""Task 8: answer short factual questions about one long handbook. The handbook is the same cached
prefix on every call, so this task measures prompt-caching behaviour as well as accuracy."""

from __future__ import annotations

import random
import re
from datetime import date

from ..common import Verdict, norm_amount, norm_iso_date, norm_text, strip_fence
from ..fakes import day_between

TASK_ID = "long_doc_qa"
TITLE = "Long-document QA with prompt caching"
DEFAULT_COUNT = 50
TARGET_CHARACTERS = 120_000  # about 30K tokens of English text

COMPANY = "Halvorsen & Quist Engineering"
REGIONS = ["Nordics", "Iberia", "Benelux", "Central Europe", "North America", "Asia Pacific"]
ROLES = ["Head of People", "Facilities Lead", "Regional Finance Controller", "Chief Information Security Officer",
         "Travel Desk Coordinator", "Health and Safety Officer", "Payroll Manager", "Procurement Lead",
         "Data Protection Officer", "Office Manager"]
TOPICS = [
    ("Annual leave", "days of paid annual leave per calendar year", 20, 34),
    ("Parental leave top-up", "weeks of parental leave paid at full salary", 6, 26),
    ("Remote work", "days per week employees may work remotely", 1, 4),
    ("Home office stipend", "one-off home office stipend in euros", 250, 1200),
    ("Training budget", "annual training budget per employee in euros", 600, 3500),
    ("Notice period", "days of notice required for resignation after probation", 30, 90),
    ("Probation", "months of probation for new hires", 3, 6),
    ("Expense claims", "days within which expense claims must be submitted", 14, 60),
    ("Hotel cap", "maximum hotel rate per night in euros", 110, 260),
    ("Meal allowance", "daily meal allowance during business travel in euros", 28, 75),
    ("Equipment refresh", "months before a laptop may be replaced", 24, 48),
    ("Sick leave certificate", "consecutive sick days after which a medical certificate is required", 2, 5),
    ("On-call compensation", "euros paid per on-call weekend", 120, 480),
    ("Bike lease", "maximum bike lease value in euros", 1500, 5000),
    ("Gym subsidy", "monthly gym subsidy in euros", 15, 60),
]
FILLER_SUBJECTS = ["The policy", "This section", "The procedure", "The guidance", "The committee", "Each team",
                   "The process", "The handbook", "Line management", "The review board"]
FILLER_VERBS = ["applies to", "is reviewed alongside", "should be read with", "replaces earlier guidance on",
                "is coordinated with", "takes precedence over local notes on", "is audited together with"]
FILLER_OBJECTS = ["regional employment law", "the code of conduct", "collective agreements where they exist",
                  "the travel booking process", "the annual budget cycle", "the onboarding checklist",
                  "information security standards", "the whistleblowing procedure", "local works council agreements",
                  "insurance requirements", "the records retention schedule"]

SYSTEM_HEAD = ("You answer questions about the employee handbook below. Answer with the value only: a number, "
               "an amount, a date as YYYY-MM-DD, or a role title, exactly as asked. No explanation.\n\n")


def _filler(rng: random.Random, sentences: int) -> str:
    return " ".join(f"{rng.choice(FILLER_SUBJECTS)} {rng.choice(FILLER_VERBS)} {rng.choice(FILLER_OBJECTS)}."
                    for _ in range(sentences))


def build_handbook(rng: random.Random) -> tuple[str, list[dict]]:
    """Return the handbook text and every fact it states, each fact a possible question."""
    facts: list[dict] = []
    sections: list[str] = [f"{COMPANY} Employee Handbook, edition 2026.2\n"]
    number = 1
    for title, unit, low, high in TOPICS:
        owner = rng.choice(ROLES)
        effective = day_between(rng, date(2025, 1, 1), date(2026, 6, 30))
        lines = [f"Section {number}. {title}", _filler(rng, 6),
                 f"This policy is owned by the {owner} and has been effective since {effective.isoformat()}."]
        facts.append({"kind": "text", "answer": owner, "question": f"Which role owns the {title.lower()} policy?"})
        facts.append({"kind": "date", "answer": effective.isoformat(),
                      "question": f"Since what date has the {title.lower()} policy been effective?"})
        for region in REGIONS:
            value = rng.randint(low, high)
            lines.append(f"In {region}, the {unit} is {value}. {_filler(rng, 2)}")
            kind = "amount" if "euros" in unit else "number"
            facts.append({"kind": kind, "answer": str(value),
                          "question": f"In {region}, what is the {unit}?"})
        lines.append(_filler(rng, 8))
        sections.append("\n".join(lines))
        number += 1
    body = "\n\n".join(sections)
    appendix = 1
    while len(body) < TARGET_CHARACTERS:
        body += f"\n\nAppendix {appendix}. General provisions\n{_filler(rng, 40)}"
        appendix += 1
    return body, facts


def generate(rng: random.Random, count: int) -> list[dict]:
    handbook, facts = build_handbook(rng)
    chosen = rng.sample(facts, count)
    items = []
    for index, fact in enumerate(chosen):
        items.append({"id": f"{TASK_ID}-{index + 1:03d}", "input": {"question": fact["question"], "document_ref": "handbook"},
                      "expected": {"kind": fact["kind"], "answer": fact["answer"]}})
    return items, {"handbook": handbook}


def prompt(item: dict, shared: dict) -> dict:
    return {"system": SYSTEM_HEAD + shared["handbook"], "user": item["input"]["question"], "cache_system": True}


def validate(item: dict, output: str) -> Verdict:
    answer = strip_fence(output).strip().rstrip(".")
    expected = item["expected"]
    kind = expected["kind"]
    if kind == "text":
        same = norm_text(re.sub(r"^the\s+", "", answer, flags=re.I)) == norm_text(expected["answer"])
    elif kind == "date":
        same = norm_iso_date(answer) == expected["answer"]
    else:
        numbers = re.findall(r"\d[\d,]*(?:\.\d+)?", answer)
        if len(numbers) != 1:
            return Verdict.failed(f"expected one number, got {answer[:60]!r}")
        if kind == "amount":
            same = norm_amount(numbers[0]) == norm_amount(expected["answer"])
        else:
            same = numbers[0].replace(",", "") == expected["answer"]
    return Verdict.passed() if same else Verdict.failed(f"expected {expected['answer']!r}, got {answer[:60]!r}")


def reference_output(item: dict) -> str:
    expected = item["expected"]
    if expected["kind"] == "amount":
        return f"€{expected['answer']}"
    if expected["kind"] == "number":
        return f"{expected['answer']}"
    return expected["answer"]


def wrong_outputs(item: dict) -> list[str]:
    expected = item["expected"]
    if expected["kind"] in ("number", "amount"):
        return [str(int(expected["answer"]) + 1), f"{expected['answer']} or {int(expected['answer']) + 2}"]
    if expected["kind"] == "date":
        return [expected["answer"].replace("-", "/"), "2024-01-01"]
    return ["Someone Else", f"{expected['answer']} and the Office Manager"]
