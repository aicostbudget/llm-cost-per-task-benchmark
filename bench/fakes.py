"""Synthetic names and places. Everything here is invented; no real people or companies are intended."""

from __future__ import annotations

import random
from datetime import date, timedelta

COMPANY_PARTS_A = ["Northwind", "Bluepeak", "Ironleaf", "Silvergate", "Copperline", "Brightfield", "Oakridge", "Harborview",
                   "Redstone", "Clearwater", "Summitreach", "Pinecrest", "Lumen", "Granite", "Westbrook", "Kestrel"]
COMPANY_PARTS_B = ["Supply", "Logistics", "Analytics", "Print Works", "Consulting", "Hardware", "Labs", "Freight",
                   "Office Goods", "Cloud Services", "Packaging", "Electrical", "Media", "Catering"]
COMPANY_SUFFIX = ["Ltd", "LLC", "GmbH", "Inc.", "B.V.", "S.A.S.", "Pty Ltd", "AB"]
FIRST_NAMES = ["Alex", "Jordan", "Sam", "Taylor", "Morgan", "Casey", "Riley", "Jamie", "Robin", "Avery", "Quinn",
               "Noor", "Mateo", "Lena", "Kofi", "Yuki", "Priya", "Lars", "Ines", "Tomas"]
LAST_NAMES = ["Fenwick", "Okafor", "Lindqvist", "Moreau", "Tanaka", "Castillo", "Brennan", "Haddad", "Novak",
              "Albrecht", "Sato", "Delgado", "Whitlow", "Kowalczyk", "Rahman", "Vasquez", "Ostrowski", "Mbeki"]
STREETS = ["Harbor Road", "Linden Street", "Mill Lane", "Station Avenue", "Quarry Way", "Elm Court", "Canal Street",
           "Market Square", "Orchard Drive", "Bridge Row"]
CITIES = [("Leeds", "GB"), ("Lyon", "FR"), ("Graz", "AT"), ("Utrecht", "NL"), ("Porto", "PT"), ("Aarhus", "DK"),
          ("Austin", "US"), ("Denver", "US"), ("Toronto", "CA"), ("Perth", "AU"), ("Osaka", "JP"), ("Malmo", "SE")]
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]


def company(rng: random.Random) -> str:
    return f"{rng.choice(COMPANY_PARTS_A)} {rng.choice(COMPANY_PARTS_B)} {rng.choice(COMPANY_SUFFIX)}"


def person(rng: random.Random) -> str:
    return f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"


def address(rng: random.Random) -> tuple[str, str, str]:
    city, country = rng.choice(CITIES)
    return f"{rng.randint(2, 240)} {rng.choice(STREETS)}", city, country


def day_between(rng: random.Random, start: date, end: date) -> date:
    return start + timedelta(days=rng.randint(0, (end - start).days))


def long_date(value: date) -> str:
    return f"{MONTHS[value.month - 1]} {value.day}, {value.year}"


def day_month_year(value: date) -> str:
    return f"{value.day:02d} {MONTHS[value.month - 1][:3]} {value.year}"
