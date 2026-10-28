"""Hard tier of task 8: the same kind of handbook, but every question needs two or more facts combined
(a maximum across regions, a difference, a count over a threshold, a sum). The answer is one value."""

from __future__ import annotations

import random

from . import long_doc_qa as base

TASK_ID = "long_doc_qa_hard"
TITLE = "Long-document QA with prompt caching (hard)"
DEFAULT_COUNT = 50
TIER = "hard"


def _per_region(handbook_rng_facts: list[dict]) -> dict[str, dict[str, int]]:
    """unit -> region -> value, rebuilt from the numeric facts the handbook states."""
    table: dict[str, dict[str, int]] = {}
    for fact in handbook_rng_facts:
        question = fact["question"]
        if fact["kind"] in ("number", "amount") and question.startswith("In "):
            region, unit = question[3:].split(", what is the ", 1)
            table.setdefault(unit.rstrip("?"), {})[region] = int(fact["answer"])
    return table


def generate(rng: random.Random, count: int):
    handbook, facts = base.build_handbook(random.Random(f"{rng.random()}"))
    table = _per_region(facts)
    units = sorted(table)
    candidates = []
    for unit in units:
        values = table[unit]
        kind = "amount" if "euros" in unit else "number"
        ranked = sorted(values.items(), key=lambda kv: kv[1], reverse=True)
        if ranked[0][1] != ranked[1][1]:
            candidates.append({"kind": "text", "answer": ranked[0][0], "question": f"Which region has the highest {unit}?"})
        if ranked[-1][1] != ranked[-2][1]:
            candidates.append({"kind": "text", "answer": ranked[-1][0], "question": f"Which region has the lowest {unit}?"})
        a, b = rng.sample(sorted(values), 2)
        candidates.append({"kind": kind, "answer": str(abs(values[a] - values[b])),
                           "question": f"What is the difference in the {unit} between {a} and {b}? Give a positive number."})
        threshold = sorted(values.values())[len(values) // 2]
        candidates.append({"kind": "number", "answer": str(sum(1 for v in values.values() if v > threshold)),
                           "question": f"In how many regions is the {unit} greater than {threshold}?"})
        candidates.append({"kind": kind, "answer": str(sum(values.values())),
                           "question": f"What is the sum of the {unit} across all regions?"})
    chosen = rng.sample(candidates, count)
    items = [{"id": f"{TASK_ID}-{index + 1:03d}", "input": {"question": c["question"], "document_ref": "handbook"},
              "expected": {"kind": c["kind"], "answer": c["answer"]}} for index, c in enumerate(chosen)]
    return items, {"handbook": handbook}


def prompt(item: dict, shared: dict) -> dict:
    return {"system": base.SYSTEM_HEAD.replace("or a role title", "a role title or a region name") + shared["handbook"],
            "user": item["input"]["question"], "cache_system": True}


validate = base.validate
reference_output = base.reference_output


def wrong_outputs(item: dict) -> list[str]:
    expected = item["expected"]
    if expected["kind"] == "text":
        other = next(r for r in base.REGIONS if r != expected["answer"])
        return [other, f"{expected['answer']} and {other}"]
    return base.wrong_outputs(item)
