"""Task 4: write a SQLite query that answers a question. Pass = same result set as the reference query."""

from __future__ import annotations

import random
import sqlite3
from collections import Counter
from datetime import date, timedelta

from ..common import Verdict, strip_fence
from ..fakes import CITIES, FIRST_NAMES, LAST_NAMES, company, day_between

TASK_ID = "text_to_sql"
TITLE = "Text-to-SQL"
DEFAULT_COUNT = 50
MAX_VM_STEPS = 5_000_000

SCHEMAS = {
    "shop": """
CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT NOT NULL, country TEXT NOT NULL, signup_date TEXT NOT NULL);
CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL, price REAL NOT NULL);
CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL REFERENCES customers(id), order_date TEXT NOT NULL, status TEXT NOT NULL);
CREATE TABLE order_items (order_id INTEGER NOT NULL REFERENCES orders(id), product_id INTEGER NOT NULL REFERENCES products(id), quantity INTEGER NOT NULL, unit_price REAL NOT NULL);
""",
    "hr": """
CREATE TABLE departments (id INTEGER PRIMARY KEY, name TEXT NOT NULL, location TEXT NOT NULL);
CREATE TABLE employees (id INTEGER PRIMARY KEY, name TEXT NOT NULL, department_id INTEGER NOT NULL REFERENCES departments(id), hire_date TEXT NOT NULL, salary INTEGER NOT NULL, manager_id INTEGER REFERENCES employees(id));
CREATE TABLE reviews (employee_id INTEGER NOT NULL REFERENCES employees(id), year INTEGER NOT NULL, rating INTEGER NOT NULL);
""",
    "library": """
CREATE TABLE authors (id INTEGER PRIMARY KEY, name TEXT NOT NULL, birth_year INTEGER NOT NULL, country TEXT NOT NULL);
CREATE TABLE books (id INTEGER PRIMARY KEY, title TEXT NOT NULL, author_id INTEGER NOT NULL REFERENCES authors(id), published_year INTEGER NOT NULL, genre TEXT NOT NULL, pages INTEGER NOT NULL);
CREATE TABLE members (id INTEGER PRIMARY KEY, name TEXT NOT NULL, joined TEXT NOT NULL);
CREATE TABLE loans (id INTEGER PRIMARY KEY, book_id INTEGER NOT NULL REFERENCES books(id), member_id INTEGER NOT NULL REFERENCES members(id), loan_date TEXT NOT NULL, return_date TEXT);
""",
}
NOTES = {
    "shop": "Dates are TEXT in YYYY-MM-DD. orders.status is one of 'paid', 'shipped', 'cancelled', 'refunded'. "
            "Revenue means SUM(quantity * unit_price) over order_items of orders that are not cancelled or refunded.",
    "hr": "Dates are TEXT in YYYY-MM-DD. salary is yearly in euros. rating is 1 to 5. manager_id is NULL for department heads.",
    "library": "Dates are TEXT in YYYY-MM-DD. return_date is NULL while a book is still on loan.",
}

CATEGORIES = ["books", "electronics", "garden", "kitchen", "toys", "sports"]
STATUSES = ["paid", "shipped", "shipped", "shipped", "cancelled", "refunded"]
DEPARTMENTS = [("Engineering", "Oslo"), ("Sales", "Madrid"), ("Finance", "Vienna"), ("Support", "Porto"),
               ("Marketing", "Madrid"), ("Operations", "Oslo")]
GENRES = ["mystery", "science fiction", "history", "poetry", "biography", "fantasy"]
TITLE_WORDS = ["Silent", "River", "Glass", "Northern", "Winter", "Paper", "Iron", "Hidden", "Last", "Amber", "Orchard", "Signal"]


def _quote(value: object) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    return repr(value)


def _inserts(table: str, rows: list[tuple]) -> str:
    return "\n".join(f"INSERT INTO {table} VALUES ({', '.join(_quote(v) for v in row)});" for row in rows)


def build_databases(rng: random.Random) -> dict[str, str]:
    scripts = {}
    countries = sorted({country for _, country in CITIES})

    customers = [(i, f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}", rng.choice(countries),
                  day_between(rng, date(2023, 1, 1), date(2025, 12, 31)).isoformat()) for i in range(1, 61)]
    products = [(i, f"{rng.choice(TITLE_WORDS)} {rng.choice(['Lamp', 'Kit', 'Set', 'Pack', 'Board', 'Tool', 'Case'])} {i}",
                 CATEGORIES[i % len(CATEGORIES)], round(rng.randint(299, 19999) / 100, 2)) for i in range(1, 41)]
    orders, order_items = [], []
    for i in range(1, 301):
        orders.append((i, rng.randint(1, 60), day_between(rng, date(2024, 1, 1), date(2026, 6, 30)).isoformat(), rng.choice(STATUSES)))
        for product in rng.sample(products, rng.randint(1, 4)):
            order_items.append((i, product[0], rng.randint(1, 5), product[3]))
    scripts["shop"] = SCHEMAS["shop"] + "\n".join([_inserts("customers", customers), _inserts("products", products),
                                                   _inserts("orders", orders), _inserts("order_items", order_items)])

    departments = [(i + 1, name, city) for i, (name, city) in enumerate(DEPARTMENTS)]
    employees = []
    for department in departments:
        head_id = len(employees) + 1
        employees.append((head_id, f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}", department[0],
                          day_between(rng, date(2012, 1, 1), date(2018, 12, 31)).isoformat(), rng.randint(95, 150) * 1000, None))
        for _ in range(rng.randint(5, 11)):
            employees.append((len(employees) + 1, f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}", department[0],
                              day_between(rng, date(2016, 1, 1), date(2026, 3, 31)).isoformat(), rng.randint(38, 98) * 1000, head_id))
    reviews = [(e[0], year, rng.randint(1, 5)) for e in employees for year in (2023, 2024, 2025) if e[3] < f"{year}-07-01"]
    scripts["hr"] = SCHEMAS["hr"] + "\n".join([_inserts("departments", departments), _inserts("employees", employees),
                                               _inserts("reviews", reviews)])

    authors = [(i, f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}", rng.randint(1920, 1990), rng.choice(countries)) for i in range(1, 26)]
    books = [(i, f"The {rng.choice(TITLE_WORDS)} {rng.choice(TITLE_WORDS)}", rng.randint(1, 25), rng.randint(1960, 2025),
              rng.choice(GENRES), rng.randint(90, 820)) for i in range(1, 121)]
    members = [(i, f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}", day_between(rng, date(2019, 1, 1), date(2025, 12, 31)).isoformat())
               for i in range(1, 51)]
    loans = []
    for i in range(1, 401):
        loaned = day_between(rng, date(2025, 1, 1), date(2026, 9, 30))
        returned = None if rng.random() < 0.12 else (loaned + timedelta(days=rng.randint(3, 45))).isoformat()
        loans.append((i, rng.randint(1, 120), rng.randint(1, 50), loaned.isoformat(), returned))
    scripts["library"] = SCHEMAS["library"] + "\n".join([_inserts("authors", authors), _inserts("books", books),
                                                         _inserts("members", members), _inserts("loans", loans)])
    return scripts


REVENUE = "SUM(oi.quantity * oi.unit_price)"
VALID = "o.status NOT IN ('cancelled', 'refunded')"

# Each template: (database, question, reference SQL, ordered, parameter picker)
TEMPLATES = [
    ("shop", "How many customers are from {country}?", "SELECT COUNT(*) FROM customers WHERE country = '{country}'", False,
     lambda r: {"country": r.choice(sorted({c for _, c in CITIES}))}),
    ("shop", "What was the total revenue in {year}? Round to 2 decimals.",
     f"SELECT ROUND({REVENUE}, 2) FROM orders o JOIN order_items oi ON oi.order_id = o.id WHERE {VALID} AND substr(o.order_date, 1, 4) = '{{year}}'", False,
     lambda r: {"year": r.choice(["2024", "2025"])}),
    ("shop", "List the names of the 5 customers with the highest revenue, highest first.",
     f"SELECT c.name FROM customers c JOIN orders o ON o.customer_id = c.id JOIN order_items oi ON oi.order_id = o.id WHERE {VALID} GROUP BY c.id ORDER BY {REVENUE} DESC LIMIT 5", True,
     lambda r: {}),
    ("shop", "How many orders have status '{status}'?", "SELECT COUNT(*) FROM orders WHERE status = '{status}'", False,
     lambda r: {"status": r.choice(["paid", "shipped", "cancelled", "refunded"])}),
    ("shop", "What is the revenue per product category in {year}? Return category and revenue rounded to 2 decimals.",
     f"SELECT p.category, ROUND({REVENUE}, 2) FROM orders o JOIN order_items oi ON oi.order_id = o.id JOIN products p ON p.id = oi.product_id WHERE {VALID} AND substr(o.order_date, 1, 4) = '{{year}}' GROUP BY p.category", False,
     lambda r: {"year": r.choice(["2024", "2025"])}),
    ("shop", "Which products in the '{category}' category have never been ordered? Return product names.",
     "SELECT name FROM products WHERE category = '{category}' AND id NOT IN (SELECT product_id FROM order_items)", False,
     lambda r: {"category": r.choice(CATEGORIES)}),
    ("shop", "How many distinct customers placed at least one order in {month} (YYYY-MM)?",
     "SELECT COUNT(DISTINCT customer_id) FROM orders WHERE substr(order_date, 1, 7) = '{month}'", False,
     lambda r: {"month": f"{r.choice([2024, 2025])}-{r.randint(1, 12):02d}"}),
    ("hr", "What is the average salary in the {department} department, rounded to the nearest euro?",
     "SELECT ROUND(AVG(e.salary)) FROM employees e JOIN departments d ON d.id = e.department_id WHERE d.name = '{department}'", False,
     lambda r: {"department": r.choice(DEPARTMENTS)[0]}),
    ("hr", "How many employees were hired after {day}?", "SELECT COUNT(*) FROM employees WHERE hire_date > '{day}'", False,
     lambda r: {"day": f"{r.randint(2019, 2024)}-{r.randint(1, 12):02d}-01"}),
    ("hr", "List the names of employees who report to {manager}.",
     "SELECT e.name FROM employees e JOIN employees m ON m.id = e.manager_id WHERE m.name = '{manager}'", False,
     None),
    ("hr", "Which departments are located in {city}? Return department names.", "SELECT name FROM departments WHERE location = '{city}'", False,
     lambda r: {"city": r.choice(["Oslo", "Madrid", "Vienna", "Porto"])}),
    ("hr", "For each department, how many employees got a rating of 5 in {year}? Return department name and count; include departments with zero.",
     "SELECT d.name, COUNT(r.employee_id) FROM departments d LEFT JOIN employees e ON e.department_id = d.id LEFT JOIN reviews r ON r.employee_id = e.id AND r.year = {year} AND r.rating = 5 GROUP BY d.id", False,
     lambda r: {"year": r.choice([2023, 2024, 2025])}),
    ("hr", "Who has the highest salary among employees who are not department heads? Return their name(s); include everyone tied for the highest.",
     "SELECT name FROM employees WHERE manager_id IS NOT NULL AND salary = (SELECT MAX(salary) FROM employees WHERE manager_id IS NOT NULL)", False, lambda r: {}),
    ("library", "How many books in the '{genre}' genre were published before {year}?",
     "SELECT COUNT(*) FROM books WHERE genre = '{genre}' AND published_year < {year}", False,
     lambda r: {"genre": r.choice(GENRES), "year": r.choice([1980, 1995, 2005, 2015])}),
    ("library", "How many loans are currently not returned?", "SELECT COUNT(*) FROM loans WHERE return_date IS NULL", False, lambda r: {}),
    ("library", "List the titles of the 3 most borrowed books, most borrowed first; break ties by title A to Z.",
     "SELECT b.title FROM books b JOIN loans l ON l.book_id = b.id GROUP BY b.id ORDER BY COUNT(*) DESC, b.title ASC LIMIT 3", True, lambda r: {}),
    ("library", "Which authors from {country} have written at least one book? Return author names.",
     "SELECT DISTINCT a.name FROM authors a JOIN books b ON b.author_id = a.id WHERE a.country = '{country}'", False,
     lambda r: {"country": r.choice(sorted({c for _, c in CITIES}))}),
    ("library", "What is the average number of pages of books borrowed in {month} (YYYY-MM)? Round to 1 decimal.",
     "SELECT ROUND(AVG(b.pages), 1) FROM loans l JOIN books b ON b.id = l.book_id WHERE substr(l.loan_date, 1, 7) = '{month}'", False,
     lambda r: {"month": f"2025-{r.randint(1, 12):02d}"}),
]


def _connect(script: str) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.executescript(script)
    connection.execute("PRAGMA query_only = ON")
    return connection


def _rows(connection: sqlite3.Connection, sql: str) -> list[tuple]:
    steps = {"n": 0}

    def guard() -> int:
        steps["n"] += 1000
        return 1 if steps["n"] > MAX_VM_STEPS else 0

    connection.set_progress_handler(guard, 1000)
    rows = connection.execute(sql).fetchall()
    return [tuple(round(v, 2) if isinstance(v, float) else v for v in row) for row in rows]


def generate(rng: random.Random, count: int):
    scripts = build_databases(rng)
    connections = {name: _connect(script) for name, script in scripts.items()}
    managers = [row[0] for row in connections["hr"].execute("SELECT name FROM employees WHERE manager_id IS NULL")]
    items, seen = [], set()
    attempts = 0
    while len(items) < count:
        attempts += 1
        if attempts > count * 50:
            raise RuntimeError("could not build enough distinct, non-empty SQL items")
        database, question, sql, ordered, pick = TEMPLATES[len(items) % len(TEMPLATES)] if attempts <= count else rng.choice(TEMPLATES)
        params = {"manager": rng.choice(managers)} if pick is None else pick(rng)
        q, reference = question.format(**params), sql.format(**params)
        if q in seen:
            continue
        rows = _rows(connections[database], reference)
        if not rows or rows == [(0,)] or rows == [(None,)]:
            continue
        seen.add(q)
        items.append({"id": f"{TASK_ID}-{len(items) + 1:03d}", "input": {"database": database, "question": q},
                      "expected": {"sql": reference, "ordered": ordered, "rows": rows}})
    return items, {"databases": scripts}


def prompt(item: dict, shared: dict | None = None) -> dict:
    database = item["input"]["database"]
    system = ("Write one SQLite query that answers the question. Reply with the SQL only, no explanation. "
              "Return only the columns the question asks for, in that order.\n\n"
              f"Schema:\n{SCHEMAS[database].strip()}\n\nNotes: {NOTES[database]}")
    return {"system": system, "user": item["input"]["question"]}


def validate(item: dict, output: str, shared: dict) -> Verdict:
    sql = strip_fence(output).strip().rstrip(";").strip()
    if ";" in sql:
        return Verdict.failed("more than one statement")
    if not sql.lower().startswith(("select", "with")):
        return Verdict.failed("not a SELECT query")
    connection = _connect(shared["databases"][item["input"]["database"]])
    try:
        rows = _rows(connection, sql)
    except sqlite3.Error as error:
        return Verdict.failed(f"SQL error: {error}")
    finally:
        connection.close()
    expected = [tuple(row) for row in item["expected"]["rows"]]
    if rows and expected and len(rows[0]) != len(expected[0]):
        return Verdict.failed(f"expected {len(expected[0])} column(s), got {len(rows[0])}")
    same = rows == expected if item["expected"]["ordered"] else Counter(rows) == Counter(expected)
    if not same:
        return Verdict.failed(f"result differs: expected {len(expected)} row(s), got {len(rows)}; first {rows[:2]!r}")
    return Verdict.passed()


def reference_output(item: dict) -> str:
    return item["expected"]["sql"]


def wrong_outputs(item: dict) -> list[str]:
    return ["DELETE FROM orders", "SELECT 1; SELECT 2", item["expected"]["sql"] + " LIMIT 0", "SELECT nonsense FROM nowhere"]
