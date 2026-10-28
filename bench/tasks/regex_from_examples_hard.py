"""Hard tier of task 10: specs that need lookaheads, backreferences, modular counting or calendar rules
(valid dates with leap years, Roman numerals, binary multiples of 3, consistent separators)."""

from __future__ import annotations

import calendar
import random
import re
import string
from datetime import date, timedelta

from . import regex_from_examples as base

TASK_ID = "regex_from_examples_hard"
TITLE = "Regex from examples (hard)"
DEFAULT_COUNT = 40
TIER = "hard"
HEX = "0123456789abcdefABCDEF"


def _roman(n: int) -> str:
    table = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"), (50, "L"), (40, "XL"), (10, "X"),
             (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]
    out = ""
    for value, symbol in table:
        while n >= value:
            out, n = out + symbol, n - value
    return out


ROMANS = {_roman(n) for n in range(1, 4000)}


def _valid_date(y: str, m: str, d: str) -> bool:
    if not (y.isdigit() and m.isdigit() and d.isdigit() and len(y) == 4 and len(m) == 2 and len(d) == 2 and y.isascii()):
        return False
    year, month, day = int(y), int(m), int(d)
    return 1900 <= year <= 2099 and 1 <= month <= 12 and 1 <= day <= calendar.monthrange(year, month)[1]


def _grouped(s: str, sep: str) -> bool:
    if s == "0":
        return True
    parts = s.split(sep)
    return (parts[0].isdigit() and parts[0].isascii() and 1 <= len(parts[0]) <= 3 and parts[0][0] != "0"
            and all(len(p) == 3 and p.isdigit() and p.isascii() for p in parts[1:]))


def _email(s: str) -> bool:
    if s.count("@") != 1:
        return False
    local, domain = s.split("@")
    name, plus, tag = local.partition("+")
    ok_chars = lambda t: bool(t) and all(c in string.ascii_lowercase + string.digits for c in t)  # noqa: E731
    if not ok_chars(name) or (plus and not ok_chars(tag)):
        return False
    labels = domain.split(".")
    return len(labels) >= 2 and all(ok_chars(l) for l in labels[:-1]) and 2 <= len(labels[-1]) <= 6 and labels[-1].isalpha() \
        and labels[-1].isascii() and labels[-1].islower()


def _spec(text, check, make, alphabet, reference, decoy=None):
    """decoy, when given, builds well-formed strings that break the hard rule (Feb 30, IIII, 1,23,456), so the
    hidden negatives are not only malformed strings."""
    if decoy is not None:
        positive = make
        make = lambda r: decoy(r) if r.random() < 0.6 else positive(r)  # noqa: E731
    return {"spec": text, "check": check, "make": make, "alphabet": alphabet, "reference": reference}


def _bad_iso_date(r: random.Random) -> str:
    year = r.choice([1900, 1901, 2023, 2025, 2026, 2100, 1899, 2019])
    month, day = r.choice([(2, 29), (2, 30), (2, 31), (4, 31), (6, 31), (9, 31), (11, 31), (13, 1), (0, 10), (5, 0), (12, 32)])
    return f"{year:04d}-{month:02d}-{day:02d}"


BAD_ROMANS = ["IIII", "VV", "IC", "IL", "XM", "VX", "MMMM", "CCCC", "XXXX", "LL", "DD", "IIV", "XCX", "CMC", "IXI", "VIV"]


def _specs() -> list[dict]:
    specs = [
        _spec("A binary number (digits 0 and 1, no leading zeros except the number 0 itself) whose value is a multiple of 3.",
              lambda s: bool(s) and set(s) <= {"0", "1"} and (s == "0" or s[0] == "1") and int(s, 2) % 3 == 0,
              lambda r: bin(3 * r.randint(0, 400))[2:], "01", r"0|(?=1)(?:0|1(?:01*0)*1)+",
              decoy=lambda r: bin(3 * r.randint(1, 400) + r.choice([1, 2]))[2:] if r.random() < 0.8 else "0" + bin(3 * r.randint(1, 50))[2:]),
        _spec("A date as YYYY-MM-DD that exists on the calendar, years 1900 to 2099 (Feb 29 only in leap years).",
              lambda s: len(s) == 10 and s[4] == s[7] == "-" and _valid_date(s[:4], s[5:7], s[8:]),
              lambda r: (date(1900, 1, 1) + timedelta(days=r.randint(0, 73000))).isoformat() if r.random() < 0.8 else f"{r.choice([1904, 1996, 2000, 2024, 2096])}-02-29",
              string.digits + "-",
              r"(?:19|20)\d\d-(?:(?:0[13578]|1[02])-(?:0[1-9]|[12]\d|3[01])|(?:0[469]|11)-(?:0[1-9]|[12]\d|30)|02-(?:0[1-9]|1\d|2[0-8]))"
              r"|(?:19|20)(?:0[48]|[2468][048]|[13579][26])-02-29|2000-02-29", decoy=_bad_iso_date),
        _spec("A date as DD/MM/YYYY that exists on the calendar, years 1900 to 2099 (29/02 only in leap years).",
              lambda s: len(s) == 10 and s[2] == s[5] == "/" and _valid_date(s[6:], s[3:5], s[:2]),
              lambda r: (lambda d: d.strftime("%d/%m/%Y"))(date(1900, 1, 1) + timedelta(days=r.randint(0, 73000))) if r.random() < 0.8 else f"29/02/{r.choice([1904, 1996, 2000, 2024])}",
              string.digits + "/",
              r"(?:(?:0[1-9]|[12]\d|3[01])/(?:0[13578]|1[02])|(?:0[1-9]|[12]\d|30)/(?:0[469]|11)|(?:0[1-9]|1\d|2[0-8])/02)/(?:19|20)\d\d"
              r"|29/02/(?:(?:19|20)(?:0[48]|[2468][048]|[13579][26])|2000)",
              decoy=lambda r: (lambda y, m, d: f"{d}/{m}/{y}")(*_bad_iso_date(r).split("-"))),
        _spec("A Roman numeral for a number from 1 to 3999 in standard form (upper-case, e.g. XIV, MCMXCIV).",
              lambda s: s in ROMANS, lambda r: _roman(r.randint(1, 3999)), "MDCLXVI",
              r"(?=[MDCLXVI])M{0,3}(?:CM|CD|D?C{0,3})(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3})",
              decoy=lambda r: r.choice(["", "M", "MC", "X"]) + r.choice(BAD_ROMANS)),
        _spec("A whole number with commas as thousands separators in the right places, no leading zeros (e.g. 7, 1,234, 12,345,678).",
              lambda s: _grouped(s, ","), lambda r: f"{r.choice([r.randint(0, 999), r.randint(1000, 10**9)]):,}", string.digits + ",",
              r"0|[1-9]\d{0,2}(?:,\d{3})*",
              decoy=lambda r: r.choice(["1,23,456", "12,3456", "1234,567", "0,123", "1,2345", ",123", "123,", "01,234", "12,34,567"])),
        _spec("An amount with commas as thousands separators in the right places, no leading zeros, optionally followed by a dot and exactly 2 digits.",
              lambda s: _grouped(s.split(".")[0], ",") and (s.count(".") == 0 or (s.count(".") == 1 and len(s.split(".")[1]) == 2 and s.split(".")[1].isdigit())),
              lambda r: f"{r.randint(0, 10**8):,}" + (f".{r.randint(0, 99):02d}" if r.random() < 0.6 else ""), string.digits + ",.",
              r"(?:0|[1-9]\d{0,2}(?:,\d{3})*)(?:\.\d{2})?",
              decoy=lambda r: r.choice(["1,23,456.00", "12,345.5", "1,234.567", "1234,567.89", "0,500.00", "1,000.", ".50"])),
        _spec("A European-style amount: dots as thousands separators in the right places, no leading zeros, optionally a comma and exactly 2 digits.",
              lambda s: _grouped(s.split(",")[0], ".") and (s.count(",") == 0 or (s.count(",") == 1 and len(s.split(",")[1]) == 2 and s.split(",")[1].isdigit())),
              lambda r: f"{r.randint(0, 10**8):,}".replace(",", ".") + (f",{r.randint(0, 99):02d}" if r.random() < 0.6 else ""), string.digits + ",.",
              r"(?:0|[1-9]\d{0,2}(?:\.\d{3})*)(?:,\d{2})?",
              decoy=lambda r: r.choice(["1.23.456,00", "12.345,5", "1.234,567", "1234.567,89", "1,234.56", "1.000,", ",50"])),
        _spec("A MAC address: six pairs of hex digits (either case) separated by ':' or by '-', using the same separator throughout.",
              lambda s: len(s) == 17 and s[2] in ":-" and all(s[i] == s[2] for i in (5, 8, 11, 14)) and all(c in HEX for c in s.replace(s[2], "")),
              lambda r: r.choice(":-").join("".join(r.choice(HEX) for _ in range(2)) for _ in range(6)), HEX + ":-",
              r"[0-9A-Fa-f]{2}([:-])(?:[0-9A-Fa-f]{2}\1){4}[0-9A-Fa-f]{2}"),
        _spec('A double-quoted string literal: starts and ends with ", and inside, a backslash may only appear as \\" or \\\\; an unescaped " cannot appear inside.',
              lambda s: bool(re.fullmatch(r'"(?:[^"\\]|\\["\\])*"', s)),
              lambda r: '"' + "".join(r.choice(["a", "b", " ", "1", '\\"', "\\\\", "x"]) for _ in range(r.randint(0, 8))) + '"', 'ab "\\x',
              r'"(?:[^"\\]|\\["\\])*"'),
        _spec("A non-empty lower-case word whose letters are in alphabetical order (repeats allowed), e.g. 'abbey', 'ost'.",
              lambda s: bool(s) and s.isascii() and s.isalpha() and s.islower() and list(s) == sorted(s),
              lambda r: "".join(sorted(r.choice(string.ascii_lowercase) for _ in range(r.randint(1, 7)))), string.ascii_lowercase,
              r"(?=.)a*b*c*d*e*f*g*h*i*j*k*l*m*n*o*p*q*r*s*t*u*v*w*x*y*z*"),
        _spec("A snake_case identifier: lower-case words of letters and digits joined by single underscores; each word starts with a letter.",
              lambda s: bool(s) and all(w and w[0] in string.ascii_lowercase and all(c in string.ascii_lowercase + string.digits for c in w) for w in s.split("_")),
              lambda r: "_".join(r.choice(string.ascii_lowercase) + "".join(r.choice(string.ascii_lowercase + string.digits) for _ in range(r.randint(0, 4))) for _ in range(r.randint(1, 3))),
              string.ascii_lowercase + string.digits + "_A", r"[a-z][a-z0-9]*(?:_[a-z][a-z0-9]*)*"),
        _spec("A camelCase identifier: starts with a lower-case letter, only ASCII letters and digits, and never two upper-case letters in a row.",
              lambda s: bool(s) and s[0] in string.ascii_lowercase and all(c in string.ascii_letters + string.digits for c in s) and not any(a.isupper() and b.isupper() for a, b in zip(s, s[1:])),
              lambda r: r.choice(string.ascii_lowercase) + "".join(r.choice(string.ascii_lowercase * 3 + string.ascii_uppercase + string.digits) for _ in range(r.randint(0, 8))),
              string.ascii_letters + string.digits + "_", r"[a-z](?:[a-z0-9]|[A-Z](?![A-Z]))*"),
        _spec("A kebab-case slug: starts with a lower-case letter, then groups of lower-case letters or digits separated by single hyphens; no leading, trailing or double hyphens.",
              lambda s: bool(s) and s[0] in string.ascii_lowercase and all(g and all(c in string.ascii_lowercase + string.digits for c in g) for g in s.split("-")),
              lambda r: r.choice(string.ascii_lowercase) + "".join(r.choice(string.ascii_lowercase + string.digits) for _ in range(r.randint(0, 3)))
              + "".join("-" + "".join(r.choice(string.ascii_lowercase + string.digits) for _ in range(r.randint(1, 4))) for _ in range(r.randint(0, 3))),
              string.ascii_lowercase + string.digits + "-_", r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*"),
        _spec("A full IPv6 address: exactly eight groups of 1 to 4 hex digits (either case) separated by ':' (no '::' shortening).",
              lambda s: len(s.split(":")) == 8 and all(1 <= len(g) <= 4 and all(c in HEX for c in g) for g in s.split(":")),
              lambda r: ":".join("".join(r.choice(HEX) for _ in range(r.randint(1, 4))) for _ in range(8)), HEX + ":g",
              r"[0-9a-fA-F]{1,4}(?::[0-9a-fA-F]{1,4}){7}"),
        _spec("A CSS hex color: '#' followed by exactly 3, 4, 6 or 8 hex digits (either case).",
              lambda s: len(s) in (4, 5, 7, 9) and s[0] == "#" and all(c in HEX for c in s[1:]),
              lambda r: "#" + "".join(r.choice(HEX) for _ in range(r.choice([3, 4, 6, 8]))), HEX + "#g",
              r"#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})"),
        _spec("A US phone number as '(AAA) BBB-CCCC' or 'AAA-BBB-CCCC', where the area code AAA does not start with 0 or 1.",
              lambda s: bool(re.fullmatch(r"(?:\([2-9]\d{2}\) |[2-9]\d{2}-)\d{3}-\d{4}", s)) and s.isascii(),
              lambda r: (lambda a: (f"({a}) " if r.random() < 0.5 else f"{a}-") + f"{r.randint(0, 999):03d}-{r.randint(0, 9999):04d}")(str(r.randint(200, 999))),
              string.digits + "()- ", r"(?:\([2-9]\d{2}\) |[2-9]\d{2}-)\d{3}-\d{4}"),
        _spec("A semantic version MAJOR.MINOR.PATCH (non-negative integers, no leading zeros) optionally followed by '-' and dot-separated pre-release identifiers of ASCII letters and digits (e.g. 1.4.0-rc.2).",
              lambda s: bool(re.fullmatch(r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)(?:-[0-9A-Za-z]+(?:\.[0-9A-Za-z]+)*)?", s)) and s.isascii(),
              lambda r: ".".join(str(r.randint(0, 30)) for _ in range(3)) + (("-" + ".".join(r.choice(["alpha", "beta", "rc", "1", "2", "x7"]) for _ in range(r.randint(1, 3)))) if r.random() < 0.6 else ""),
              string.digits + ".-abcrx", r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)(?:-[0-9A-Za-z]+(?:\.[0-9A-Za-z]+)*)?"),
        _spec("An email address: local part of lower-case letters and digits, optionally '+' and a tag of lower-case letters and digits; '@'; one or more domain labels of lower-case letters and digits, each followed by a dot; then a top-level domain of 2 to 6 lower-case letters.",
              _email,
              lambda r: "".join(r.choice(string.ascii_lowercase + string.digits) for _ in range(r.randint(1, 6))) + (("+" + "".join(r.choice(string.ascii_lowercase) for _ in range(r.randint(1, 4)))) if r.random() < 0.5 else "")
              + "@" + ".".join("".join(r.choice(string.ascii_lowercase + string.digits) for _ in range(r.randint(1, 6))) for _ in range(r.randint(1, 3))) + "." + "".join(r.choice(string.ascii_lowercase) for _ in range(r.randint(2, 6))),
              string.ascii_lowercase + string.digits + "+@.-", r"[a-z0-9]+(?:\+[a-z0-9]+)?@(?:[a-z0-9]+\.)+[a-z]{2,6}"),
    ]
    for x, o in [("a", "b"), ("x", "y"), ("1", "0"), ("p", "q")]:
        specs.append(_spec(f"A non-empty string of the characters '{x}' and '{o}' only, containing an even number of '{x}' (zero counts as even).",
                           lambda s, x=x, o=o: bool(s) and set(s) <= {x, o} and s.count(x) % 2 == 0,
                           lambda r, x=x, o=o: (lambda t: t + (x if t.count(x) % 2 else "") or o)("".join(r.choice([x, o]) for _ in range(r.randint(1, 9)))),
                           x + o, f"(?=.)(?:{o}*{x}{o}*{x})*{o}*"))
    for x, o in [("a", "b"), ("1", "0")]:
        specs.append(_spec(f"A non-empty string of the characters '{x}' and '{o}' only, in which the number of '{x}' is a multiple of 3 (zero counts).",
                           lambda s, x=x, o=o: bool(s) and set(s) <= {x, o} and s.count(x) % 3 == 0,
                           lambda r, x=x, o=o: (lambda t: (t + x * ((3 - t.count(x) % 3) % 3)) or o)("".join(r.choice([x, o]) for _ in range(r.randint(1, 9)))),
                           x + o, f"(?=.)(?:{o}*{x}{o}*{x}{o}*{x})*{o}*"))
    for letters in ("ab", "abc", "01", "abcd", "xyz"):
        specs.append(_spec(f"A non-empty string using only the characters {', '.join(repr(c) for c in letters)}, in which no character appears twice in a row.",
                           lambda s, L=letters: bool(s) and set(s) <= set(L) and all(a != b for a, b in zip(s, s[1:])),
                           lambda r, L=letters: _no_repeat(r, L),
                           letters, f"(?!.*(.)\\1)[{re.escape(letters)}]+"))
    for low, high in [(8, 16), (10, 20), (6, 12), (12, 32), (8, 64), (4, 8)]:
        specs.append(_spec(f"A password of {low} to {high} characters using only ASCII letters and digits, with at least one upper-case letter, one lower-case letter and one digit.",
                           lambda s, a=low, b=high: a <= len(s) <= b and all(c in string.ascii_letters + string.digits for c in s) and any(c.isupper() for c in s) and any(c.islower() for c in s) and any(c.isdigit() for c in s),
                           lambda r, a=low, b=high: _password(r, a, b, ""), string.ascii_letters + string.digits + "!_ ",
                           r"(?=.*[A-Z])(?=.*[a-z])(?=.*\d)[A-Za-z\d]{%d,%d}" % (low, high)))
    for low, high in [(8, 20), (10, 16)]:
        specs.append(_spec(f"A password of {low} to {high} characters using only ASCII letters, digits and the symbols !@#$%, with at least one upper-case letter, one lower-case letter, one digit and one of those symbols.",
                           lambda s, a=low, b=high: a <= len(s) <= b and all(c in string.ascii_letters + string.digits + "!@#$%" for c in s) and any(c.isupper() for c in s) and any(c.islower() for c in s) and any(c.isdigit() for c in s) and any(c in "!@#$%" for c in s),
                           lambda r, a=low, b=high: _password(r, a, b, "!@#$%"), string.ascii_letters + string.digits + "!@#$%& ",
                           r"(?=.*[A-Z])(?=.*[a-z])(?=.*\d)(?=.*[!@#$%])[A-Za-z\d!@#$%]" + f"{{{low},{high}}}"))
    for k in (2, 3, 4, 5, 6):
        specs.append(_spec(f"A non-empty string of digits whose length is a multiple of {k}.",
                           lambda s, k=k: bool(s) and s.isascii() and s.isdigit() and len(s) % k == 0,
                           lambda r, k=k: base._digits(r, k * r.randint(1, 4)), string.digits + "a", r"(?:\d{%d})+" % k))
    return specs


def _no_repeat(r: random.Random, letters: str) -> str:
    out = r.choice(letters)
    for _ in range(r.randint(0, 8)):
        out += r.choice([c for c in letters if c != out[-1]])
    return out


def _password(r: random.Random, low: int, high: int, symbols: str) -> str:
    required = [r.choice(string.ascii_uppercase), r.choice(string.ascii_lowercase), r.choice(string.digits)] + ([r.choice(symbols)] if symbols else [])
    pool = string.ascii_letters + string.digits + symbols
    chars = required + [r.choice(pool) for _ in range(r.randint(low, high) - len(required))]
    r.shuffle(chars)
    return "".join(chars)


SYSTEM = base.SYSTEM


def generate(rng: random.Random, count: int):
    specs = _specs()
    if count > len(specs):
        raise RuntimeError(f"only {len(specs)} hard regex specs, {count} requested")
    rng.shuffle(specs)
    items = []
    for index, spec in enumerate(specs[:count]):
        shown_pos, shown_neg = base._examples(rng, spec, base.SHOWN, base.SHOWN, set())
        hidden_pos, hidden_neg = base._examples(rng, spec, base.HIDDEN // 2, base.HIDDEN // 2, set(shown_pos) | set(shown_neg))
        hidden = [[s, True] for s in hidden_pos] + [[s, False] for s in hidden_neg]
        rng.shuffle(hidden)
        items.append({"id": f"{TASK_ID}-{index + 1:03d}", "input": {"spec": spec["spec"], "match": shown_pos, "no_match": shown_neg},
                      "expected": {"tests": hidden, "reference": spec["reference"]}})
    return items, {}


prompt = base.prompt
validate = base.validate


def reference_output(item: dict) -> str:
    return item["expected"]["reference"]


def wrong_outputs(item: dict) -> list[str]:
    return [".*", "(", "/" + item["expected"]["reference"] + "/"]
