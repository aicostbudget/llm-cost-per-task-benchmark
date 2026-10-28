"""Task 6: fix one planted bug in a short Python function. Pass = hidden unit tests all pass."""

from __future__ import annotations

import ast
import json
import random
import subprocess
import sys

from ..common import Verdict, strip_fence

TASK_ID = "bug_fix"
TITLE = "Single-function bug fix"
DEFAULT_COUNT = 50
TIMEOUT_SECONDS = 5
ALLOWED_IMPORTS = {"math", "re", "collections", "itertools", "functools", "string", "bisect", "heapq"}

SYSTEM = ("The Python function below has exactly one bug. Its docstring describes the intended behaviour. "
          "Reply with the complete corrected function only, in a single ```python code block, keeping the same "
          "name and signature. Hidden unit tests will run against it.")

# name -> (correct source, [(buggy fragment replaced, by), ...], [(args, expected), ...])
FUNCTIONS: dict[str, tuple[str, list[tuple[str, str]], list[tuple[list, object]]]] = {
    "median": ('''def median(values):
    """Return the median of a non-empty list of numbers."""
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2
''', [("len(ordered) % 2 == 1", "len(ordered) % 2 == 0"), ("ordered = sorted(values)", "ordered = list(values)"),
      ("(ordered[middle - 1] + ordered[middle]) / 2", "(ordered[middle] + ordered[middle + 1]) / 2")],
        [([[3, 1, 2]], 2), ([[4, 1, 3, 2]], 2.5), ([[7]], 7), ([[10, 2, 8, 4]], 6.0), ([[5, 9, 1, 3, 7]], 5)]),
    "chunk": ('''def chunk(items, size):
    """Split a list into consecutive chunks of length size; the last chunk may be shorter."""
    return [items[i:i + size] for i in range(0, len(items), size)]
''', [("range(0, len(items), size)", "range(0, len(items) - size, size)"), ("items[i:i + size]", "items[i:i + size - 1]"),
      ("range(0, len(items), size)", "range(1, len(items), size)")],
        [([[1, 2, 3, 4, 5], 2], [[1, 2], [3, 4], [5]]), ([[1, 2, 3], 3], [[1, 2, 3]]), ([[], 4], []), ([[1, 2, 3, 4], 1], [[1], [2], [3], [4]])]),
    "is_leap_year": ('''def is_leap_year(year):
    """Gregorian leap year rule."""
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
''', [("year % 400 == 0", "year % 400 != 0"), ("year % 100 != 0 or", "year % 100 == 0 or"), ("year % 4 == 0 and", "year % 4 == 0 or")],
        [([2024], True), ([1900], False), ([2000], True), ([2023], False), ([2100], False), ([1996], True)]),
    "word_count": ('''def word_count(text):
    """Count words case-insensitively; words are runs of letters or apostrophes. Return a dict."""
    import re
    counts = {}
    for word in re.findall(r"[a-z']+", text.lower()):
        counts[word] = counts.get(word, 0) + 1
    return counts
''', [("text.lower()", "text"), ("counts.get(word, 0) + 1", "counts.get(word, 1)"), (r'r"[a-z\']+"'.replace("\\", ""), 'r"[a-z]+"')],
        [(["The cat and the hat"], {"the": 2, "cat": 1, "and": 1, "hat": 1}), (["Don't stop, don't"], {"don't": 2, "stop": 1}), ([""], {}),
         (["a A a"], {"a": 3})]),
    "binary_search": ('''def binary_search(values, target):
    """Return the index of target in the sorted list values, or -1 if absent."""
    low, high = 0, len(values) - 1
    while low <= high:
        mid = (low + high) // 2
        if values[mid] == target:
            return mid
        if values[mid] < target:
            low = mid + 1
        else:
            high = mid - 1
    return -1
''', [("while low <= high:", "while low < high:"), ("low = mid + 1", "low = mid"), ("high = mid - 1", "high = mid + 1")],
        [([[1, 3, 5, 7, 9], 7], 3), ([[1, 3, 5, 7, 9], 1], 0), ([[1, 3, 5, 7, 9], 9], 4), ([[1, 3, 5], 4], -1), ([[], 1], -1), ([[2], 2], 0)]),
    "running_total": ('''def running_total(values):
    """Return the cumulative sums of a list of numbers."""
    total = 0
    result = []
    for value in values:
        total += value
        result.append(total)
    return result
''', [("total += value\n        result.append(total)", "result.append(total)\n        total += value"), ("total = 0", "total = values[0] if values else 0"),
      ("total += value", "total = value")],
        [([[1, 2, 3]], [1, 3, 6]), ([[]], []), ([[5]], [5]), ([[2, -2, 4]], [2, 0, 4])]),
    "title_case": ('''def title_case(text, minor=("a", "an", "the", "of", "and", "in")):
    """Capitalise each word except minor words, but always capitalise the first word. Words are split on spaces."""
    words = text.lower().split(" ")
    out = []
    for index, word in enumerate(words):
        if index > 0 and word in minor:
            out.append(word)
        else:
            out.append(word[:1].upper() + word[1:])
    return " ".join(out)
''', [("index > 0 and word in minor", "word in minor"), ("text.lower().split", "text.split"), ("word[:1].upper() + word[1:]", "word.upper()")],
        [(["the lord of the rings"], "The Lord of the Rings"), (["A TALE OF TWO CITIES"], "A Tale of Two Cities"), (["in the mood"], "In the Mood"),
         (["war and peace"], "War and Peace")]),
    "flatten": ('''def flatten(nested):
    """Flatten arbitrarily nested lists into one list, preserving order."""
    out = []
    for element in nested:
        if isinstance(element, list):
            out.extend(flatten(element))
        else:
            out.append(element)
    return out
''', [("out.extend(flatten(element))", "out.extend(element)"), ("out.extend(flatten(element))", "out.append(flatten(element))"),
      ("isinstance(element, list)", "isinstance(element, tuple)")],
        [([[1, [2, [3, [4]]], 5]], [1, 2, 3, 4, 5]), ([[]], []), ([[[], [1]]], [1]), ([[1, 2]], [1, 2])]),
    "dedupe": ('''def dedupe(items):
    """Remove duplicates while keeping the first occurrence order."""
    seen = set()
    out = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out
''', [("if item not in seen:", "if item in seen:"), ("            seen.add(item)\n", ""), ("return out", "return sorted(out)")],
        [([[3, 1, 3, 2, 1]], [3, 1, 2]), ([[]], []), ([["b", "a", "b"]], ["b", "a"]), ([[1, 1, 1]], [1])]),
    "roman": ('''def roman(number):
    """Convert an integer from 1 to 3999 to a Roman numeral."""
    table = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
             (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]
    out = ""
    for value, symbol in table:
        while number >= value:
            out += symbol
            number -= value
    return out
''', [("while number >= value:", "while number > value:"), ('(9, "IX"), ', ""), ('(400, "CD"), ', '(400, "DC"), ')],
        [([1994], "MCMXCIV"), ([4], "IV"), ([9], "IX"), ([3999], "MMMCMXCIX"), ([40], "XL"), ([1], "I"), ([444], "CDXLIV")]),
    "parse_duration": ('''def parse_duration(text):
    """Parse strings like "1h30m", "45m", "2h", "90s" into total seconds."""
    import re
    units = {"h": 3600, "m": 60, "s": 1}
    total = 0
    for amount, unit in re.findall(r"(\\d+)([hms])", text):
        total += int(amount) * units[unit]
    return total
''', [('"m": 60', '"m": 60 * 60'), ("total += int(amount) * units[unit]", "total = int(amount) * units[unit]"), ('r"(\\d+)([hms])"', 'r"(\\d)([hms])"')],
        [(["1h30m"], 5400), (["45m"], 2700), (["2h"], 7200), (["90s"], 90), (["1h1m1s"], 3661), (["12m"], 720)]),
    "clamp": ('''def clamp(value, low, high):
    """Limit value to the inclusive range [low, high]."""
    return max(low, min(value, high))
''', [("max(low, min(value, high))", "min(low, max(value, high))"), ("min(value, high)", "min(value, low)"), ("max(low, ", "max(high, ")],
        [([5, 0, 10], 5), ([-3, 0, 10], 0), ([42, 0, 10], 10), ([0, 0, 10], 0), ([10, 0, 10], 10)]),
    "anagrams": ('''def anagrams(a, b):
    """True if a and b are anagrams, ignoring case and spaces."""
    clean = lambda s: sorted(s.replace(" ", "").lower())
    return clean(a) == clean(b)
''', [('s.replace(" ", "").lower()', 's.lower()'), ("sorted(", "list("), ('.lower()', '')],
        [(["Listen", "Silent"], True), (["Dormitory", "dirty room"], True), (["abc", "abd"], False), (["ab", "ba"], True), (["a b", "ab"], True)]),
    "moving_average": ('''def moving_average(values, window):
    """Averages of each full window of consecutive values, as floats."""
    return [sum(values[i:i + window]) / window for i in range(len(values) - window + 1)]
''', [("len(values) - window + 1", "len(values) - window"), ("/ window", "/ len(values)"), ("values[i:i + window]", "values[i:i + window - 1]")],
        [([[1, 2, 3, 4], 2], [1.5, 2.5, 3.5]), ([[5, 5, 5], 3], [5.0]), ([[1, 2], 3], []), ([[2, 4, 6, 8], 1], [2.0, 4.0, 6.0, 8.0])]),
    "second_largest": ('''def second_largest(values):
    """Second largest distinct value, or None if there are fewer than two distinct values."""
    distinct = sorted(set(values))
    return distinct[-2] if len(distinct) >= 2 else None
''', [("sorted(set(values))", "sorted(values)"), ("distinct[-2]", "distinct[1]"), ("len(distinct) >= 2", "len(distinct) > 2")],
        [([[1, 5, 3]], 3), ([[4, 4, 2]], 2), ([[7, 7]], None), ([[]], None), ([[1, 2, 3, 4, 5]], 4), ([[9, 1]], 1)]),
    "caesar": ('''def caesar(text, shift):
    """Shift ASCII letters by shift positions, preserving case; other characters unchanged."""
    out = []
    for ch in text:
        if "a" <= ch <= "z":
            out.append(chr((ord(ch) - 97 + shift) % 26 + 97))
        elif "A" <= ch <= "Z":
            out.append(chr((ord(ch) - 65 + shift) % 26 + 65))
        else:
            out.append(ch)
    return "".join(out)
''', [("% 26 + 97", "+ 97"), ("(ord(ch) - 65 + shift) % 26 + 65", "(ord(ch) - 97 + shift) % 26 + 97"), ("            out.append(ch)", "            pass")],
        [(["abc", 1], "bcd"), (["xyz", 3], "abc"), (["Hello, World!", 13], "Uryyb, Jbeyq!"), (["ABC", -1], "ZAB")]),
    "merge_intervals": ('''def merge_intervals(intervals):
    """Merge overlapping or touching [start, end] intervals; return them sorted by start."""
    merged = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged
''', [("start <= merged[-1][1]", "start < merged[-1][1]"), ("max(merged[-1][1], end)", "end"), ("sorted(intervals)", "intervals")],
        [([[[1, 3], [2, 6], [8, 10]]], [[1, 6], [8, 10]]), ([[[1, 4], [4, 5]]], [[1, 5]]), ([[[1, 10], [2, 3]]], [[1, 10]]),
         ([[[5, 6], [1, 2]]], [[1, 2], [5, 6]]), ([[]], [])]),
}


def generate(rng: random.Random, count: int):
    pool = []
    for name, (source, mutations, tests) in FUNCTIONS.items():
        for index, (old, new) in enumerate(mutations):
            if old not in source:
                raise ValueError(f"{name} mutation {index}: fragment not found")
            pool.append({"name": name, "buggy": source.replace(old, new, 1), "correct": source, "tests": tests, "mutation": index})
    rng.shuffle(pool)
    items = []
    for index, entry in enumerate(pool[:count]):
        items.append({"id": f"{TASK_ID}-{index + 1:03d}", "input": {"function_name": entry["name"], "source": entry["buggy"]},
                      "expected": {"tests": entry["tests"], "reference": entry["correct"]}})
    return items, {}


def prompt(item: dict, shared: dict | None = None) -> dict:
    return {"system": SYSTEM, "user": "```python\n" + item["input"]["source"] + "```"}


def _check_source(code: str, name: str) -> str | None:
    try:
        tree = ast.parse(code)
    except SyntaxError as error:
        return f"syntax error: {error.msg} (line {error.lineno})"
    if not any(isinstance(node, ast.FunctionDef) and node.name == name for node in tree.body):
        return f"no top-level function named {name}"
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            modules = [alias.name.split(".")[0] for alias in node.names] if isinstance(node, ast.Import) else [(node.module or "").split(".")[0]]
            if any(module not in ALLOWED_IMPORTS for module in modules):
                return f"import not allowed: {', '.join(modules)}"
        if isinstance(node, ast.Name) and node.id in {"open", "exec", "eval", "__import__", "compile", "input"}:
            return f"call not allowed: {node.id}"
    return None


_RUNNER = """
import json, sys
payload = json.loads(sys.stdin.read())
namespace = {}
exec(payload["code"], namespace)
fn = namespace[payload["name"]]
for args, expected in payload["tests"]:
    got = fn(*args)
    if isinstance(got, tuple):
        got = list(got)
    if got != expected:
        print(json.dumps({"ok": False, "reason": f"{payload['name']}{tuple(args)!r} returned {got!r}, expected {expected!r}"}))
        sys.exit(0)
print(json.dumps({"ok": True}))
"""


def run_tests(code: str, name: str, tests: list) -> Verdict:
    problem = _check_source(code, name)
    if problem:
        return Verdict.failed(problem)
    payload = json.dumps({"code": code, "name": name, "tests": tests})
    try:
        completed = subprocess.run([sys.executable, "-I", "-c", _RUNNER], input=payload, capture_output=True, text=True,
                                   timeout=TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        return Verdict.failed(f"timed out after {TIMEOUT_SECONDS}s")
    if completed.returncode != 0:
        last = (completed.stderr.strip().splitlines() or ["crashed"])[-1]
        return Verdict.failed(f"raised: {last[:200]}")
    result = json.loads(completed.stdout.strip().splitlines()[-1])
    return Verdict.passed() if result["ok"] else Verdict.failed(result["reason"][:300])


def validate(item: dict, output: str, shared: dict | None = None) -> Verdict:
    return run_tests(strip_fence(output), item["input"]["function_name"], item["expected"]["tests"])


def reference_output(item: dict) -> str:
    return "```python\n" + item["expected"]["reference"] + "```"


def wrong_outputs(item: dict) -> list[str]:
    name = item["input"]["function_name"]
    return [item["input"]["source"], f"import os\n{item['expected']['reference']}", "def something_else():\n    return 1\n",
            item["expected"]["reference"].replace(f"def {name}(", f"def {name}_fixed(")]
