"""Hard tier of task 4: questions that need window functions, HAVING, NULL handling, date arithmetic,
per-group top-N or percentages. Same three databases, same validator."""

from __future__ import annotations

import random

from . import text_to_sql as base

TASK_ID = "text_to_sql_hard"
TITLE = "Text-to-SQL (hard)"
DEFAULT_COUNT = 30  # the 15 templates allow about 33 distinct, non-empty questions on these databases
TIER = "hard"

REVENUE = "SUM(oi.quantity * oi.unit_price)"
VALID = "o.status NOT IN ('cancelled', 'refunded')"

TEMPLATES = [
    ("shop", "For each product category, which product had the highest revenue in {year}? Return category, product name and revenue rounded to 2 decimals; one row per category.",
     f"WITH r AS (SELECT p.category, p.name, ROUND({REVENUE}, 2) AS rev, ROW_NUMBER() OVER (PARTITION BY p.category ORDER BY {REVENUE} DESC) AS rn "
     f"FROM orders o JOIN order_items oi ON oi.order_id = o.id JOIN products p ON p.id = oi.product_id WHERE {VALID} AND substr(o.order_date, 1, 4) = '{{year}}' GROUP BY p.id) "
     "SELECT category, name, rev FROM r WHERE rn = 1", False, lambda r: {"year": r.choice(["2024", "2025"])}),
    ("shop", "Which customers placed at least {n} non-cancelled, non-refunded orders in {year}? Return customer name and order count, most orders first, then name A to Z.",
     f"SELECT c.name, COUNT(*) FROM customers c JOIN orders o ON o.customer_id = c.id WHERE {VALID} AND substr(o.order_date, 1, 4) = '{{year}}' "
     "GROUP BY c.id HAVING COUNT(*) >= {n} ORDER BY COUNT(*) DESC, c.name ASC", True,
     lambda r: {"year": r.choice(["2024", "2025"]), "n": r.choice([3, 4, 5])}),
    ("shop", "What share of all orders placed in {year} were cancelled or refunded? Return a percentage rounded to 1 decimal (e.g. 12.5).",
     "SELECT ROUND(100.0 * SUM(CASE WHEN status IN ('cancelled', 'refunded') THEN 1 ELSE 0 END) / COUNT(*), 1) FROM orders WHERE substr(order_date, 1, 4) = '{year}'", False,
     lambda r: {"year": r.choice(["2024", "2025"])}),
    ("shop", "List every month of {year} (YYYY-MM) with its revenue rounded to 2 decimals and the change from the previous month's rounded revenue (NULL for the first month), in month order.",
     f"WITH m AS (SELECT substr(o.order_date, 1, 7) AS month, ROUND({REVENUE}, 2) AS rev FROM orders o JOIN order_items oi ON oi.order_id = o.id "
     f"WHERE {VALID} AND substr(o.order_date, 1, 4) = '{{year}}' GROUP BY month) SELECT month, rev, ROUND(rev - LAG(rev) OVER (ORDER BY month), 2) FROM m ORDER BY month", True,
     lambda r: {"year": r.choice(["2024", "2025"])}),
    ("shop", "How many customers signed up in {year} but never placed an order that was not cancelled or refunded?",
     f"SELECT COUNT(*) FROM customers c WHERE substr(c.signup_date, 1, 4) = '{{year}}' AND NOT EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.id AND {VALID})", False,
     lambda r: {"year": r.choice(["2023", "2024", "2025"])}),
    ("shop", "What is the average number of days between a customer's signup and their first order of any status, rounded to 1 decimal, over customers who have ordered?",
     "SELECT ROUND(AVG(julianday(f.first) - julianday(c.signup_date)), 1) FROM customers c JOIN (SELECT customer_id, MIN(order_date) AS first FROM orders GROUP BY customer_id) f ON f.customer_id = c.id", False,
     lambda r: {}),
    ("hr", "For each department, return its name, the number of employees whose salary is above that department's average salary, and that average rounded to the nearest euro.",
     "WITH a AS (SELECT department_id, AVG(salary) AS avg_s FROM employees GROUP BY department_id) SELECT d.name, "
     "(SELECT COUNT(*) FROM employees e WHERE e.department_id = d.id AND e.salary > a.avg_s), ROUND(a.avg_s) FROM departments d JOIN a ON a.department_id = d.id", False,
     lambda r: {}),
    ("hr", "Which employees had a lower rating in {year} than in {prev}? Return their names, A to Z, one row per employee (two employees can share a name).",
     "SELECT e.name FROM employees e JOIN reviews r1 ON r1.employee_id = e.id AND r1.year = {year} JOIN reviews r2 ON r2.employee_id = e.id AND r2.year = {prev} "
     "WHERE r1.rating < r2.rating ORDER BY e.name", True, lambda r: (lambda y: {"year": y, "prev": y - 1})(r.choice([2024, 2025]))),
    ("hr", "Name the department head whose team (the employees reporting to them) has the highest average {year} rating. Return the head's name and that average rounded to 2 decimals.",
     "SELECT m.name, ROUND(AVG(r.rating), 2) FROM employees m JOIN employees e ON e.manager_id = m.id JOIN reviews r ON r.employee_id = e.id AND r.year = {year} "
     "GROUP BY m.id ORDER BY AVG(r.rating) DESC LIMIT 1", False, lambda r: {"year": r.choice([2023, 2024, 2025])}),
    ("hr", "How many employees have no review at all for {year}?",
     "SELECT COUNT(*) FROM employees e WHERE NOT EXISTS (SELECT 1 FROM reviews r WHERE r.employee_id = e.id AND r.year = {year})", False,
     lambda r: {"year": r.choice([2023, 2024, 2025])}),
    ("library", "As of {day}, how many loans are still not returned and were taken out more than {days} days before that date?",
     "SELECT COUNT(*) FROM loans WHERE return_date IS NULL AND loan_date <= '{day}' AND julianday('{day}') - julianday(loan_date) > {days}", False,
     lambda r: {"day": "2026-10-01", "days": r.choice([30, 60, 90])}),
    ("library", "For each genre, how many distinct members borrowed at least one book of that genre in {year}? Return genre and count, highest count first, then genre A to Z.",
     "SELECT b.genre, COUNT(DISTINCT l.member_id) FROM loans l JOIN books b ON b.id = l.book_id WHERE substr(l.loan_date, 1, 4) = '{year}' GROUP BY b.genre "
     "ORDER BY COUNT(DISTINCT l.member_id) DESC, b.genre ASC", True, lambda r: {"year": r.choice(["2025", "2026"])}),
    ("library", "What is the average loan length in days, rounded to 1 decimal, for returned loans of books published before {year}?",
     "SELECT ROUND(AVG(julianday(l.return_date) - julianday(l.loan_date)), 1) FROM loans l JOIN books b ON b.id = l.book_id WHERE l.return_date IS NOT NULL AND b.published_year < {year}", False,
     lambda r: {"year": r.choice([1980, 1995, 2005])}),
    ("library", "Which authors have books in at least {n} different genres? Return author name and genre count, most genres first, then name A to Z.",
     "SELECT a.name, COUNT(DISTINCT b.genre) FROM authors a JOIN books b ON b.author_id = a.id GROUP BY a.id HAVING COUNT(DISTINCT b.genre) >= {n} "
     "ORDER BY COUNT(DISTINCT b.genre) DESC, a.name ASC", True, lambda r: {"n": r.choice([3, 4])}),
    ("library", "Which members borrowed the same book more than once? Return member name and book title, member A to Z then title A to Z.",
     "SELECT DISTINCT m.name, b.title FROM loans l JOIN members m ON m.id = l.member_id JOIN books b ON b.id = l.book_id GROUP BY l.member_id, l.book_id HAVING COUNT(*) > 1 "
     "ORDER BY m.name, b.title", True, lambda r: {}),
]


def generate(rng: random.Random, count: int):
    scripts = base.build_databases(random.Random(f"{rng.random()}"))
    connections = {name: base._connect(script) for name, script in scripts.items()}
    items, seen, attempts = [], set(), 0
    while len(items) < count:
        attempts += 1
        if attempts > count * 60:
            raise RuntimeError("could not build enough distinct, non-empty hard SQL items")
        database, question, sql, ordered, pick = TEMPLATES[len(items) % len(TEMPLATES)] if attempts <= count else rng.choice(TEMPLATES)
        params = pick(rng)
        q, reference = question.format(**params), sql.format(**params)
        if q in seen:
            continue
        rows = base._rows(connections[database], reference)
        if not rows or rows == [(0,)] or rows == [(None,)]:
            continue
        if not ordered and "LIMIT 1" in reference:
            # A LIMIT 1 answer must be unique: skip parameter choices with a tie for first place.
            tie_check = reference.replace("LIMIT 1", "LIMIT 2")
            two = base._rows(connections[database], tie_check)
            if len(two) == 2 and two[0][1:] == two[1][1:]:
                continue
        seen.add(q)
        items.append({"id": f"{TASK_ID}-{len(items) + 1:03d}", "input": {"database": database, "question": q},
                      "expected": {"sql": reference, "ordered": ordered, "rows": rows}})
    return items, {"databases": scripts}


prompt = base.prompt
validate = base.validate
reference_output = base.reference_output
wrong_outputs = base.wrong_outputs
