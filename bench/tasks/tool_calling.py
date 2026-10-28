"""Task 7: pick the right tool and arguments for a user request, or no tool when none fits.

The harness sends TOOLS through each provider's native tool-calling API and converts the reply to
{"tool": name, "arguments": {...}} (or {"tool": null} for a plain-text reply) before validation."""

from __future__ import annotations

import json
import random
from datetime import date, timedelta

from ..common import Verdict, norm_amount, norm_iso_date, norm_text, parse_json_object
from ..fakes import FIRST_NAMES, LAST_NAMES, MONTHS, day_between

TASK_ID = "tool_calling"
TITLE = "Tool calling"
DEFAULT_COUNT = 50
REPLY = "tool_call"  # the runner validates the converted tool call, not the reply text

SYSTEM = ("You are an operations assistant. Today is 2026-10-01. Use a tool when the request needs one; "
          "otherwise answer in plain text. Dates are YYYY-MM-DD and times HH:MM (24-hour).")

TOOLS = [
    {"name": "get_weather", "description": "Weather forecast for a city on a date.",
     "parameters": {"type": "object", "required": ["city", "date"], "properties": {
         "city": {"type": "string"}, "date": {"type": "string", "description": "YYYY-MM-DD"},
         "units": {"type": "string", "enum": ["celsius", "fahrenheit"], "default": "celsius"}}}},
    {"name": "create_calendar_event", "description": "Create a calendar event.",
     "parameters": {"type": "object", "required": ["title", "date", "start_time", "duration_minutes"], "properties": {
         "title": {"type": "string"}, "date": {"type": "string"}, "start_time": {"type": "string", "description": "HH:MM"},
         "duration_minutes": {"type": "integer"}, "attendees": {"type": "array", "items": {"type": "string"}, "default": []}}}},
    {"name": "send_invoice_reminder", "description": "Email the customer a reminder for an overdue invoice.",
     "parameters": {"type": "object", "required": ["invoice_number", "days_overdue"], "properties": {
         "invoice_number": {"type": "string"}, "days_overdue": {"type": "integer"}}}},
    {"name": "search_orders", "description": "Find a customer's orders.",
     "parameters": {"type": "object", "required": ["customer_email"], "properties": {
         "customer_email": {"type": "string"}, "status": {"type": "string", "enum": ["any", "open", "shipped", "delivered", "cancelled"], "default": "any"},
         "since": {"type": "string", "description": "YYYY-MM-DD, optional"}}}},
    {"name": "refund_order", "description": "Refund all or part of an order.",
     "parameters": {"type": "object", "required": ["order_id", "amount", "reason"], "properties": {
         "order_id": {"type": "string"}, "amount": {"type": "number"},
         "reason": {"type": "string", "enum": ["damaged", "late", "wrong_item", "other"]}}}},
    {"name": "convert_currency", "description": "Convert an amount between currencies at today's rate.",
     "parameters": {"type": "object", "required": ["amount", "from_currency", "to_currency"], "properties": {
         "amount": {"type": "number"}, "from_currency": {"type": "string", "description": "ISO 4217"},
         "to_currency": {"type": "string", "description": "ISO 4217"}}}},
    {"name": "get_stock_price", "description": "Latest price for a stock ticker.",
     "parameters": {"type": "object", "required": ["ticker"], "properties": {"ticker": {"type": "string"}}}},
    {"name": "book_meeting_room", "description": "Book a meeting room.",
     "parameters": {"type": "object", "required": ["room", "date", "start_time", "end_time"], "properties": {
         "room": {"type": "string", "enum": ["Fjord", "Harbor", "Summit", "Atrium"]}, "date": {"type": "string"},
         "start_time": {"type": "string"}, "end_time": {"type": "string"}}}},
]
TOOL_BY_NAME = {tool["name"]: tool for tool in TOOLS}
# How each argument is compared: text, code (upper), lower, date, time, int, amount, exact, list_text
ARG_RULES = {
    "get_weather": {"city": "text", "date": "date", "units": "exact"},
    "create_calendar_event": {"title": "text", "date": "date", "start_time": "time", "duration_minutes": "int", "attendees": "list_text"},
    "send_invoice_reminder": {"invoice_number": "code", "days_overdue": "int"},
    "search_orders": {"customer_email": "lower", "status": "exact", "since": "date"},
    "refund_order": {"order_id": "code", "amount": "amount", "reason": "exact"},
    "convert_currency": {"amount": "amount", "from_currency": "code", "to_currency": "code"},
    "get_stock_price": {"ticker": "code"},
    "book_meeting_room": {"room": "exact", "date": "date", "start_time": "time", "end_time": "time"},
}
NO_TOOL_REQUESTS = ["Thanks, that's all for today!", "What does the abbreviation ETA stand for?",
                    "Can you explain the difference between a refund and a chargeback in one sentence?",
                    "Who wrote 'Pride and Prejudice'?", "How many minutes are in three and a half hours?",
                    "Please summarise what you can help me with.", "Is it better to say 'data is' or 'data are'?"]
CITIES = ["Lisbon", "Oslo", "Kraków", "Montreal", "Kyoto", "Valencia", "Edinburgh", "Tallinn"]
TITLES = ["Q4 planning", "Vendor review", "Onboarding sync", "Budget check-in", "Design critique", "Incident retro"]
TICKERS = [("Northwind Robotics", "NWRB"), ("Bluepeak Energy", "BPKE"), ("Lumen Health", "LMNH"), ("Kestrel Air", "KSTR")]


def _spoken(day: date) -> str:
    return f"{MONTHS[day.month - 1]} {day.day}"


def _make(rng: random.Random, tool: str) -> tuple[str, dict]:
    day = day_between(rng, date(2026, 10, 2), date(2026, 12, 20))
    if tool == "get_weather":
        city = rng.choice(CITIES)
        units = rng.choice(["celsius", "fahrenheit", None])
        unit_text = {"celsius": " in Celsius", "fahrenheit": " in Fahrenheit", None: ""}[units]
        args = {"city": city, "date": day.isoformat()}
        if units:
            args["units"] = units
        return f"What's the weather going to be in {city} on {_spoken(day)}{unit_text}?", args
    if tool == "create_calendar_event":
        title, hour, minutes = rng.choice(TITLES), rng.randint(8, 17), rng.choice([0, 15, 30, 45])
        duration = rng.choice([15, 30, 45, 60, 90])
        people = rng.sample([f"{n.lower()}@example.com" for n in FIRST_NAMES], rng.randint(0, 2))
        who = f" with {' and '.join(people)}" if people else ""
        args = {"title": title, "date": day.isoformat(), "start_time": f"{hour:02d}:{minutes:02d}", "duration_minutes": duration}
        if people:
            args["attendees"] = people
        clock = f"{(hour - 1) % 12 + 1}:{minutes:02d} {'am' if hour < 12 else 'pm'}"
        return f"Put '{title}' on my calendar for {_spoken(day)} at {clock}, {duration} minutes{who}.", args
    if tool == "send_invoice_reminder":
        number = f"INV-{rng.randint(10000, 99999)}"
        overdue = rng.randint(3, 75)
        return f"Invoice {number} is {overdue} days overdue, nudge the customer please.", {"invoice_number": number, "days_overdue": overdue}
    if tool == "search_orders":
        email = f"{rng.choice(FIRST_NAMES).lower()}.{rng.choice(LAST_NAMES).lower()}@example.com"
        status = rng.choice(["open", "shipped", "delivered", "cancelled", None])
        since = rng.choice([None, (date(2026, 10, 1) - timedelta(days=rng.randint(10, 200)))])
        args = {"customer_email": email}
        text = f"Find {'the ' + status + ' ' if status else 'all '}orders for {email}"
        if status:
            args["status"] = status
        if since:
            args["since"] = since.isoformat()
            text += f" placed since {since.isoformat()}"
        return text + ".", args
    if tool == "refund_order":
        order_id = f"A{rng.randint(100000, 999999)}"
        amount = round(rng.randint(500, 40000) / 100, 2)
        reason, phrase = rng.choice([("damaged", "arrived broken"), ("late", "arrived two weeks late"),
                                     ("wrong_item", "was the wrong item"), ("other", "the customer changed their mind")])
        return f"Refund €{amount:.2f} on order {order_id}, it {phrase}.", {"order_id": order_id, "amount": amount, "reason": reason}
    if tool == "convert_currency":
        amount = rng.choice([50, 120, 999.99, 2500, 18.5])
        pair = rng.choice([("EUR", "USD", "euros", "US dollars"), ("GBP", "JPY", "pounds", "yen"), ("USD", "CAD", "dollars", "Canadian dollars"),
                           ("CHF", "EUR", "Swiss francs", "euros")])
        return f"How much is {amount:g} {pair[2]} in {pair[3]}?", {"amount": amount, "from_currency": pair[0], "to_currency": pair[1]}
    if tool == "get_stock_price":
        name, ticker = rng.choice(TICKERS)
        return f"What's {name} ({ticker}) trading at right now?", {"ticker": ticker}
    room = rng.choice(["Fjord", "Harbor", "Summit", "Atrium"])
    start = rng.randint(8, 16)
    return (f"Book the {room} room on {_spoken(day)} from {start}:00 to {start + 1}:30.",
            {"room": room, "date": day.isoformat(), "start_time": f"{start:02d}:00", "end_time": f"{start + 1:02d}:30"})


def generate(rng: random.Random, count: int):
    items = []
    no_tool = rng.sample(NO_TOOL_REQUESTS, 6)
    names = [tool["name"] for tool in TOOLS]
    for index in range(count):
        if index < len(no_tool):
            request, expected = no_tool[index], {"tool": None, "arguments": {}}
        else:
            name = names[index % len(names)]
            request, args = _make(rng, name)
            expected = {"tool": name, "arguments": args}
        items.append({"id": "", "input": {"request": request}, "expected": expected})
    rng.shuffle(items)
    for index, item in enumerate(items):
        item["id"] = f"{TASK_ID}-{index + 1:03d}"
    return items, {}


def prompt(item: dict, shared: dict | None = None) -> dict:
    return {"system": SYSTEM, "user": item["input"]["request"], "tools": TOOLS}


def _same(rule: str, want: object, got: object) -> bool:
    if rule == "text":
        return isinstance(got, str) and norm_text(got) == norm_text(want)
    if rule == "code":
        return isinstance(got, str) and got.strip().upper() == str(want).upper()
    if rule == "lower":
        return isinstance(got, str) and got.strip().lower() == str(want).lower()
    if rule == "date":
        return norm_iso_date(got) == want
    if rule == "time":
        return isinstance(got, str) and got.strip() == want
    if rule == "int":
        return not isinstance(got, bool) and isinstance(got, (int, float)) and float(got) == float(want)
    if rule == "amount":
        return norm_amount(got) is not None and norm_amount(got) == norm_amount(want)
    if rule == "list_text":
        return isinstance(got, list) and sorted(norm_text(x) for x in got) == sorted(norm_text(x) for x in want)
    return got == want


def validate(item: dict, output: str, shared: dict | None = None) -> Verdict:
    data, error = parse_json_object(output)
    if data is None:
        return Verdict.failed(f"harness output: {error}")
    expected = item["expected"]
    if expected["tool"] is None:
        return Verdict.passed() if data.get("tool") is None else Verdict.failed(f"called {data.get('tool')} but no tool was needed")
    if data.get("tool") != expected["tool"]:
        return Verdict.failed(f"expected tool {expected['tool']}, got {data.get('tool')}")
    actual = data.get("arguments") or {}
    rules = ARG_RULES[expected["tool"]]
    properties = TOOL_BY_NAME[expected["tool"]]["parameters"]["properties"]
    for key, want in expected["arguments"].items():
        if key not in actual:
            return Verdict.failed(f"missing argument {key}")
        if not _same(rules[key], want, actual[key]):
            return Verdict.failed(f"{key}: expected {want!r}, got {actual[key]!r}")
    for key, value in actual.items():
        if key in expected["arguments"] or value is None:
            continue
        if key not in properties:
            return Verdict.failed(f"unknown argument {key}")
        if "default" not in properties[key] or value != properties[key]["default"]:
            return Verdict.failed(f"unrequested argument {key}={value!r}")
    return Verdict.passed()


def reference_output(item: dict) -> str:
    return json.dumps(item["expected"])


def wrong_outputs(item: dict) -> list[str]:
    expected = item["expected"]
    if expected["tool"] is None:
        return [json.dumps({"tool": "get_stock_price", "arguments": {"ticker": "X"}})]
    other = next(t["name"] for t in TOOLS if t["name"] != expected["tool"])
    first_key = next(iter(expected["arguments"]))
    dropped = {k: v for k, v in expected["arguments"].items() if k != first_key}
    return [json.dumps({"tool": None, "arguments": {}}), json.dumps({"tool": other, "arguments": expected["arguments"]}),
            json.dumps({"tool": expected["tool"], "arguments": dropped}),
            json.dumps({"tool": expected["tool"], "arguments": dict(expected["arguments"], surprise=1)})]
