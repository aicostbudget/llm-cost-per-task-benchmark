"""Hard tier of task 7: the same tools, but requests use relative dates, spoken times and durations,
numbers in words, currencies named by country, and an explicit "not that tool" that points to a
look-alike tool."""

from __future__ import annotations

import random
from datetime import date, timedelta

from . import tool_calling as base

TASK_ID = "tool_calling_hard"
TITLE = "Tool calling (hard)"
DEFAULT_COUNT = 50
TIER = "hard"
REPLY = "tool_call"  # the runner validates the converted tool call, not the reply text

TODAY = date(2026, 10, 1)  # a Thursday; stated in the system prompt
SYSTEM = base.SYSTEM.replace("Today is 2026-10-01.", "Today is Thursday 2026-10-01.")
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
NUMBER_WORDS = {50: "fifty", 120: "a hundred and twenty", 250: "two hundred and fifty", 1500: "one thousand five hundred",
                75: "seventy-five", 900: "nine hundred"}
CURRENCY_BY_COUNTRY = [("Japanese yen", "JPY"), ("Swiss francs", "CHF"), ("Canadian dollars", "CAD"), ("Swedish kronor", "SEK"),
                       ("Australian dollars", "AUD"), ("Mexican pesos", "MXN"), ("Indian rupees", "INR"), ("pounds sterling", "GBP")]
SPOKEN_TIMES = [("half past three in the afternoon", 15, 30), ("quarter to nine in the morning", 8, 45), ("noon", 12, 0),
                ("ten past two in the afternoon", 14, 10), ("quarter past eleven in the morning", 11, 15), ("half past nine in the morning", 9, 30),
                ("twenty to five in the afternoon", 16, 40)]
SPOKEN_DURATIONS = [("an hour and a half", 90), ("three quarters of an hour", 45), ("two hours", 120), ("twenty minutes", 20), ("an hour", 60)]


def _relative_day(rng: random.Random) -> tuple[str, date]:
    choice = rng.randint(0, 5)
    if choice == 0:
        return "tomorrow", TODAY + timedelta(days=1)
    if choice == 1:
        return "the day after tomorrow", TODAY + timedelta(days=2)
    if choice == 2:
        days = rng.choice([10, 12, 15, 20])
        return f"{days} days from today", TODAY + timedelta(days=days)
    if choice == 3:
        return "a week from tomorrow", TODAY + timedelta(days=8)
    weekday = rng.randrange(7)
    ahead = (weekday - TODAY.weekday()) % 7 or 7
    if choice == 4:
        # Today is a Thursday, so "this coming Thursday" alone could mean today; say which.
        return f"this coming {WEEKDAYS[weekday]}" + (" (not today)" if ahead == 7 else ""), TODAY + timedelta(days=ahead)
    return f"{WEEKDAYS[weekday]} of the week after next (weeks start on Monday)", _week_after_next(weekday)


def _week_after_next(weekday: int) -> date:
    monday_this_week = TODAY - timedelta(days=TODAY.weekday())
    return monday_this_week + timedelta(days=14 + weekday)


def _make(rng: random.Random, kind: int) -> tuple[str, dict]:
    if kind == 0:
        phrase, day = _relative_day(rng)
        city = rng.choice(base.CITIES)
        return f"Will I need an umbrella in {city} {phrase}? Temperatures in Fahrenheit please.", \
            {"tool": "get_weather", "arguments": {"city": city, "date": day.isoformat(), "units": "fahrenheit"}}
    if kind == 1:
        phrase, day = _relative_day(rng)
        spoken, hour, minute = rng.choice(SPOKEN_TIMES)
        length, minutes = rng.choice(SPOKEN_DURATIONS)
        title = rng.choice(base.TITLES)
        return (f"Block {length} for '{title}' {phrase} starting at {spoken}. Don't invite anyone yet.",
                {"tool": "create_calendar_event", "arguments": {"title": title, "date": day.isoformat(),
                                                              "start_time": f"{hour:02d}:{minute:02d}", "duration_minutes": minutes}})
    if kind == 2:
        amount = rng.choice(list(NUMBER_WORDS))
        name, code = rng.choice(CURRENCY_BY_COUNTRY)
        source = rng.choice([("euros", "EUR"), ("US dollars", "USD")])
        return (f"Roughly what would {NUMBER_WORDS[amount]} {source[0]} come to in {name}?",
                {"tool": "convert_currency", "arguments": {"amount": amount, "from_currency": source[1], "to_currency": code}})
    if kind == 3:
        phrase, day = _relative_day(rng)
        room = rng.choice(["Fjord", "Harbor", "Summit", "Atrium"])
        spoken, hour, minute = rng.choice(SPOKEN_TIMES[:6])
        length, minutes = rng.choice(SPOKEN_DURATIONS[:3])
        end = hour * 60 + minute + minutes
        return (f"Don't create a calendar event for this, just reserve the {room} room {phrase} from {spoken} for {length}.",
                {"tool": "book_meeting_room", "arguments": {"room": room, "date": day.isoformat(), "start_time": f"{hour:02d}:{minute:02d}",
                                                            "end_time": f"{end // 60:02d}:{end % 60:02d}"}})
    if kind == 4:
        order_id = f"A{rng.randint(100000, 999999)}"
        total = rng.choice([80, 120, 240, 60])
        share, words = rng.choice([(0.5, "half"), (0.25, "a quarter"), (0.1, "ten percent")])
        reason, phrase = rng.choice([("damaged", "the box was crushed and the item broken"), ("late", "it turned up a fortnight late"),
                                     ("wrong_item", "we shipped the blue one instead of the red one")])
        return (f"Order {order_id} cost €{total}. Give the customer {words} of that back because {phrase}.",
                {"tool": "refund_order", "arguments": {"order_id": order_id, "amount": round(total * share, 2), "reason": reason}})
    if kind == 5:
        email = f"{rng.choice(base.FIRST_NAMES).lower()}.{rng.choice(base.LAST_NAMES).lower()}@example.com"
        days = rng.choice([30, 60, 90])
        return (f"Pull up anything {email} ordered in the last {days} days that has already been delivered.",
                {"tool": "search_orders", "arguments": {"customer_email": email, "status": "delivered",
                                                        "since": (TODAY - timedelta(days=days)).isoformat()}})
    number = f"INV-{rng.randint(10000, 99999)}"
    issued = TODAY - timedelta(days=rng.choice([40, 45, 52, 61]))
    terms = 30
    return (f"Invoice {number} was issued on {issued.isoformat()} with 30-day terms and still isn't paid. Chase it, and tell them how many days overdue it is as of today.",
            {"tool": "send_invoice_reminder", "arguments": {"invoice_number": number, "days_overdue": (TODAY - issued).days - terms}})


def generate(rng: random.Random, count: int):
    items = []
    for index in range(count):
        request, expected = _make(rng, index % 7)
        items.append({"id": "", "input": {"request": request}, "expected": expected})
    rng.shuffle(items)
    for index, item in enumerate(items):
        item["id"] = f"{TASK_ID}-{index + 1:03d}"
    return items, {}


def prompt(item: dict, shared: dict | None = None) -> dict:
    return {"system": SYSTEM, "user": item["input"]["request"], "tools": base.TOOLS}


validate = base.validate
reference_output = base.reference_output
wrong_outputs = base.wrong_outputs
