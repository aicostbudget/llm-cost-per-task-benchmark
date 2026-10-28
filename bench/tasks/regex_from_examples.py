"""Task 10: write a Python regular expression from a spec and examples. Pass = it classifies every hidden
test string correctly with re.fullmatch. The task most likely to need validator-feedback retries."""

from __future__ import annotations

import json
import random
import string
import subprocess
import sys

from ..common import Verdict, strip_fence

TASK_ID = "regex_from_examples"
TITLE = "Regex from examples"
DEFAULT_COUNT = 50
TIMEOUT_SECONDS = 5
SHOWN = 4
HIDDEN = 12

SYSTEM = ("Write one Python regular expression for the spec. It will be used with re.fullmatch, so it must match "
          "the whole string. Reply with the pattern only: no quotes, no slashes, no flags, no explanation.")


def _digits(rng, n):
    return "".join(rng.choice(string.digits) for _ in range(n))


def _int_no_leading_zero(rng, low, high):
    return str(rng.randint(low, high))


def _family_specs() -> list[dict]:
    specs = []
    for n in range(3, 11):
        specs.append({"spec": f"Exactly {n} digits (0-9) and nothing else.",
                      "check": lambda s, n=n: len(s) == n and s.isascii() and s.isdigit(),
                      "make": lambda r, n=n: _digits(r, n), "alphabet": string.digits + "a "})
    for first, last in [("b", "s"), ("c", "e"), ("d", "y"), ("m", "n"), ("p", "t"), ("r", "d"), ("s", "k"), ("t", "o"),
                        ("w", "l"), ("g", "r"),
                        ("h", "p"), ("l", "g"), ("n", "m"), ("k", "e"), ("v", "s"), ("j", "a")]:
        specs.append({"spec": f"A single lower-case English word (letters a-z only) that starts with '{first}' and ends with '{last}', at least 2 letters long.",
                      "check": lambda s, f=first, l=last: len(s) >= 2 and s.isascii() and s.isalpha() and s.islower() and s[0] == f and s[-1] == l,
                      "make": lambda r, f=first, l=last: f + "".join(r.choice(string.ascii_lowercase) for _ in range(r.randint(0, 6))) + l,
                      "alphabet": string.ascii_lowercase + "A1"})
    for longest in (6, 8, 10, 12, 16, 20):
        specs.append({"spec": f"A programming identifier: starts with a letter or underscore, then letters, digits or underscores; total length 1 to {longest}.",
                      "check": lambda s, m=longest: 1 <= len(s) <= m and s.isascii() and (s[0].isalpha() or s[0] == "_") and all(c.isalnum() or c == "_" for c in s),
                      "make": lambda r, m=longest: r.choice(string.ascii_letters + "_") + "".join(r.choice(string.ascii_letters + string.digits + "_") for _ in range(r.randint(0, m - 1))),
                      "alphabet": string.ascii_letters + string.digits + "_-$ "})
    for low, high in [(2, 4), (3, 5), (4, 7), (5, 8), (6, 9), (1, 3), (2, 6), (3, 3), (7, 10), (4, 4)]:
        specs.append({"spec": f"Between {low} and {high} upper-case letters A-Z, inclusive.",
                      "check": lambda s, a=low, b=high: a <= len(s) <= b and s.isascii() and s.isalpha() and s.isupper(),
                      "make": lambda r, a=low, b=high: "".join(r.choice(string.ascii_uppercase) for _ in range(r.randint(a, b))),
                      "alphabet": string.ascii_uppercase + "a1"})

    def hex_color(r):
        n = r.choice([3, 6])
        return "#" + "".join(r.choice("0123456789abcdefABCDEF") for _ in range(n))
    specs.append({"spec": "A CSS hex color: '#' followed by exactly 3 or exactly 6 hex digits (either case).",
                  "check": lambda s: len(s) in (4, 7) and s[0] == "#" and all(c in string.hexdigits for c in s[1:]),
                  "make": hex_color, "alphabet": "#0123456789abcdefABCDEFgG"})
    specs.append({"spec": "A date as YYYY-MM-DD where MM is 01-12 and DD is 01-31 (do not check days per month).",
                  "check": lambda s: len(s) == 10 and s[4] == "-" and s[7] == "-" and s[:4].isdigit() and s[5:7].isdigit() and s[8:].isdigit()
                  and 1 <= int(s[5:7]) <= 12 and 1 <= int(s[8:]) <= 31 and s.isascii(),
                  "make": lambda r: f"{r.randint(1900, 2099)}-{r.randint(1, 12):02d}-{r.randint(1, 31):02d}", "alphabet": string.digits + "-/"})
    specs.append({"spec": "A US ZIP code: 5 digits, optionally followed by a hyphen and 4 digits.",
                  "check": lambda s: s.isascii() and ((len(s) == 5 and s.isdigit()) or (len(s) == 10 and s[5] == "-" and s[:5].isdigit() and s[6:].isdigit())),
                  "make": lambda r: _digits(r, 5) + (("-" + _digits(r, 4)) if r.random() < 0.5 else ""), "alphabet": string.digits + "- "})
    specs.append({"spec": "A semantic version MAJOR.MINOR.PATCH: three non-negative integers separated by dots, no leading zeros (0 itself is fine).",
                  "check": lambda s: len(s.split(".")) == 3 and all(p.isascii() and p.isdigit() and (p == "0" or p[0] != "0") for p in s.split(".")),
                  "make": lambda r: ".".join(_int_no_leading_zero(r, 0, 120) for _ in range(3)), "alphabet": string.digits + ".v"})
    specs.append({"spec": "A 24-hour time HH:MM from 00:00 to 23:59, always two digits each.",
                  "check": lambda s: len(s) == 5 and s[2] == ":" and s[:2].isdigit() and s[3:].isdigit() and int(s[:2]) <= 23 and int(s[3:]) <= 59 and s.isascii(),
                  "make": lambda r: f"{r.randint(0, 23):02d}:{r.randint(0, 59):02d}", "alphabet": string.digits + ":"})
    specs.append({"spec": "An IPv4 address: four numbers 0-255 separated by dots, no leading zeros (0 itself is fine).",
                  "check": lambda s: len(s.split(".")) == 4 and all(p.isascii() and p.isdigit() and (p == "0" or p[0] != "0") and int(p) <= 255 for p in s.split(".")),
                  "make": lambda r: ".".join(str(r.choice([r.randint(0, 255), 0, 255, 10, 192])) for _ in range(4)), "alphabet": string.digits + "."})
    specs.append({"spec": "A string of the letters a and b only (at least one letter) that never contains 'aa'.",
                  "check": lambda s: len(s) >= 1 and set(s) <= {"a", "b"} and "aa" not in s,
                  "make": lambda r: "".join(r.choice(["b", "ab", "ba", "bb"]) for _ in range(r.randint(1, 5))).replace("aa", "aba"), "alphabet": "ab"})
    specs.append({"spec": "A decimal amount: optional leading '-', one or more digits with no leading zeros (0 is fine), optionally a dot and exactly 2 digits.",
                  "check": lambda s: _is_amount(s),
                  "make": lambda r: ("-" if r.random() < 0.3 else "") + _int_no_leading_zero(r, 0, 99999) + (f".{r.randint(0, 99):02d}" if r.random() < 0.6 else ""),
                  "alphabet": string.digits + "-.,+"})
    specs.append({"spec": "One to three lower-case words (a-z) separated by a comma and a single space, like 'red, green'.",
                  "check": lambda s: 1 <= len(s.split(", ")) <= 3 and all(w.isascii() and w.isalpha() and w.islower() for w in s.split(", ")),
                  "make": lambda r: ", ".join("".join(r.choice(string.ascii_lowercase) for _ in range(r.randint(1, 6))) for _ in range(r.randint(1, 3))),
                  "alphabet": string.ascii_lowercase + ", "})
    specs.append({"spec": "A simple email: local part of lower-case letters, digits and dots (not starting or ending with a dot), '@', a lower-case domain name of letters, then '.com', '.org' or '.net'.",
                  "check": lambda s: _is_email(s),
                  "make": lambda r: "".join(r.choice(string.ascii_lowercase) for _ in range(r.randint(1, 5))) + r.choice(["", "." + "".join(r.choice(string.ascii_lowercase + string.digits) for _ in range(r.randint(1, 4)))])
                  + "@" + "".join(r.choice(string.ascii_lowercase) for _ in range(r.randint(2, 7))) + r.choice([".com", ".org", ".net"]),
                  "alphabet": string.ascii_lowercase + string.digits + ".@_-A"})
    return specs


def _is_amount(s: str) -> bool:
    body = s[1:] if s.startswith("-") else s
    whole, _, fraction = body.partition(".")
    if not whole or not whole.isascii() or not whole.isdigit() or (len(whole) > 1 and whole[0] == "0"):
        return False
    if "." in body:
        return len(fraction) == 2 and fraction.isdigit()
    return True


def _is_email(s: str) -> bool:
    if s.count("@") != 1:
        return False
    local, domain = s.split("@")
    allowed = set(string.ascii_lowercase + string.digits + ".")
    if not local or set(local) - allowed or local[0] == "." or local[-1] == ".":
        return False
    for tld in (".com", ".org", ".net"):
        if domain.endswith(tld):
            name = domain[: -len(tld)]
            return bool(name) and name.isascii() and name.isalpha() and name.islower()
    return False


def _mutate(rng: random.Random, text: str, alphabet: str) -> str:
    choice = rng.randint(0, 2)
    position = rng.randint(0, len(text))
    if choice == 0:
        return text[:position] + rng.choice(alphabet) + text[position:]
    if choice == 1 and text:
        position = min(position, len(text) - 1)
        return text[:position] + text[position + 1:]
    position = min(position, max(len(text) - 1, 0))
    return text[:position] + rng.choice(alphabet) + text[position + 1:]


def _examples(rng: random.Random, spec: dict, positives: int, negatives: int, exclude: set[str]) -> tuple[list[str], list[str]]:
    pos, neg = [], []
    for _ in range(4000):
        if len(pos) >= positives and len(neg) >= negatives:
            break
        candidate = spec["make"](rng)
        if rng.random() < 0.55:
            candidate = _mutate(rng, candidate, spec["alphabet"])
        if candidate in exclude or candidate in pos or candidate in neg:
            continue
        if spec["check"](candidate):
            if len(pos) < positives:
                pos.append(candidate)
        elif len(neg) < negatives:
            neg.append(candidate)
    if len(pos) < positives or len(neg) < negatives:
        raise RuntimeError(f"could not build examples for: {spec['spec']}")
    return pos, neg


def generate(rng: random.Random, count: int):
    specs = _family_specs()
    rng.shuffle(specs)
    items = []
    for index, spec in enumerate(specs[:count]):
        shown_pos, shown_neg = _examples(rng, spec, SHOWN, SHOWN, set())
        hidden_pos, hidden_neg = _examples(rng, spec, HIDDEN // 2, HIDDEN // 2, set(shown_pos) | set(shown_neg))
        hidden = [[s, True] for s in hidden_pos] + [[s, False] for s in hidden_neg]
        rng.shuffle(hidden)
        items.append({"id": f"{TASK_ID}-{index + 1:03d}",
                      "input": {"spec": spec["spec"], "match": shown_pos, "no_match": shown_neg},
                      "expected": {"tests": hidden}})
    if len(items) < count:
        raise RuntimeError(f"only {len(items)} regex specs available, {count} requested")
    return items, {}


def prompt(item: dict, shared: dict | None = None) -> dict:
    data = item["input"]
    user = (f"Spec: {data['spec']}\nMust match: {json.dumps(data['match'])}\nMust not match: {json.dumps(data['no_match'])}")
    return {"system": SYSTEM, "user": user}


_RUNNER = """
import json, re, sys
payload = json.loads(sys.stdin.read())
try:
    pattern = re.compile(payload["pattern"])
except re.error as error:
    print(json.dumps({"ok": False, "reason": f"does not compile: {error}"})); sys.exit(0)
for text, should in payload["tests"]:
    if bool(pattern.fullmatch(text)) != should:
        print(json.dumps({"ok": False, "reason": f"{text!r} should {'match' if should else 'not match'}"})); sys.exit(0)
print(json.dumps({"ok": True}))
"""


def check_pattern(pattern: str, tests: list) -> Verdict:
    if "\n" in pattern:
        return Verdict.failed("pattern spans several lines")
    try:
        completed = subprocess.run([sys.executable, "-I", "-c", _RUNNER], input=json.dumps({"pattern": pattern, "tests": tests}),
                                   capture_output=True, text=True, timeout=TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        return Verdict.failed(f"timed out after {TIMEOUT_SECONDS}s (catastrophic backtracking?)")
    result = json.loads(completed.stdout.strip().splitlines()[-1])
    return Verdict.passed() if result["ok"] else Verdict.failed(result["reason"])


def validate(item: dict, output: str, shared: dict | None = None) -> Verdict:
    return check_pattern(strip_fence(output).strip(), item["expected"]["tests"])


# Reference patterns are only used by the self-test, keyed by the start of each spec.
def reference_output(item: dict) -> str:
    spec = item["input"]["spec"]
    if spec.startswith("Exactly"):
        return r"\d{%s}" % spec.split()[1]
    if spec.startswith("A single lower-case"):
        first, last = spec.split("'")[1], spec.split("'")[3]
        return f"{first}[a-z]*{last}"
    if spec.startswith("A programming identifier"):
        longest = int(spec.rstrip(".").split()[-1])
        return r"[A-Za-z_][A-Za-z0-9_]{0,%d}" % (longest - 1)
    if spec.startswith("Between"):
        words = spec.split()
        return "[A-Z]{%s,%s}" % (words[1], words[3])
    return {
        "A CSS hex color": r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})",
        "A date as YYYY-MM-DD": r"\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])",
        "A US ZIP code": r"\d{5}(?:-\d{4})?",
        "A semantic version": r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)",
        "A 24-hour time": r"(?:[01]\d|2[0-3]):[0-5]\d",
        "An IPv4 address": r"(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)",
        "A string of the letters a and b": r"(?!$)b*(?:ab+)*a?",
        "A decimal amount": r"-?(?:0|[1-9]\d*)(?:\.\d{2})?",
        "One to three lower-case words": r"[a-z]+(?:, [a-z]+){0,2}",
        "A simple email": r"[a-z0-9](?:[a-z0-9.]*[a-z0-9])?@[a-z]+\.(?:com|org|net)",
    }[next(key for key in ("A CSS hex color", "A date as YYYY-MM-DD", "A US ZIP code", "A semantic version", "A 24-hour time",
                          "An IPv4 address", "A string of the letters a and b", "A decimal amount", "One to three lower-case words",
                          "A simple email") if spec.startswith(key))]


def wrong_outputs(item: dict) -> list[str]:
    return [".*", "(", "/" + reference_output(item) + "/", "a^"]
