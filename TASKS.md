# Tasks

Each task lives in `bench/tasks/<task>.py` with four functions: `generate` (seeded inputs and expected
answers), `prompt`, `validate` (the pass/fail check), and `reference_output` / `wrong_outputs`, which only the
self-test uses. Token figures below are rough per-attempt sizes.

## Rules every validator follows

- The verdict is decided by code only. No model judges another model.
- The reply is parsed as an application would parse it. One surrounding Markdown code fence is removed;
  leading prose ("Here is the JSON: ...") is a failure.
- Normalisation is documented and narrow: amounts compare to 2 decimal places (both `1,234.50` and
  `1.234,50` are read correctly), text compares case-folded with whitespace collapsed, dates must be ISO
  `YYYY-MM-DD` because the prompt asks for it.
- Code the model writes (SQL, Python, regex) runs isolated: SQL on a read-only in-memory SQLite database with
  a step limit; Python and regex in a separate process with a 5-second limit; Python may only import
  `math`, `re`, `collections`, `itertools`, `functools`, `string`, `bisect`, `heapq`.

## 1. `invoice_extraction` (50 items, ~200 in / 150 out)

Plain-text invoices in three layouts, five currencies and three date styles, with a buyer company and line
items as decoys. The model returns 8 fields: vendor name, invoice number, issue and due date, currency,
subtotal, tax, total. Pass when all 8 match. The most common back-office LLM job.

## 2. `receipt_vision` (30 items, image ~1,500 in / 80 out)

PNG receipts rendered with Pillow, slightly rotated and blurred, each with decoy amounts (subtotal, tax,
cash given, change). The model returns merchant, date and total. Pass when all three match. Shows what image
input does to cost. Models without image input skip it.

## 3. `strict_json` (50 items, ~370 in / 250 out)

A product description becomes JSON for a schema with `additionalProperties: false`, an enum, a nested price
object, an integer weight in grams (descriptions sometimes say kilograms) and a colour list. Pass when the
output validates and brand, category, price, currency, stock flag, weight and colours match. Every app that
parses model output pays for malformed JSON.

## 4. `text_to_sql` (50 items, ~220 in / 120 out)

Questions over three generated SQLite databases (a shop, an HR system, a library). Pass when the query's
result set equals the reference query's, ignoring row order unless the question asks for an order; floats
are rounded to 2 places. A task where a cheaper model's lower success rate can erase its price advantage.

## 5. `intent_classification` (50 items, ~385 in / 10 out)

Customer messages written from templates in varied styles, labelled with one of 20 banking support intents.
Pass on the exact label. Tiny output and input dominated by the label list: the case where the cheapest
model usually wins.

## 6. `bug_fix` (50 items, ~130 in / 300 out)

17 short Python functions, each with up to three different planted bugs (the self-test proves every buggy
version fails its tests). The model returns the corrected function. Pass when all hidden unit tests pass.

## 7. `tool_calling` (50 items, ~710 in / 80 out)

Requests against 8 tool definitions, plus requests that need no tool. The runner sends the tools through each
provider's native tool-calling API and converts the reply to `{"tool": name, "arguments": {...}}`. Pass on
the right tool (or none) with matching arguments; an argument nobody asked for is only allowed at its
documented default.

## 8. `long_doc_qa` (50 items, ~30,000 in mostly cached / 40 out)

One generated employee handbook of about 30K tokens with 15 policies, each stating values per region, an
owner and an effective date. Questions ask for one value. The handbook is the same system prompt on every
call, so this task measures prompt caching as well as accuracy.

## 9. `record_normalization` (50 items, ~155 in / 150 out)

Messy contact records in eight countries: phone numbers in national and international formats, country
names in several spellings, birth dates in four styles, postal codes in any case and spacing. Pass when
email, E.164 phone, ISO country code, ISO birth date and postal code are all canonical. Bulk work that suits
batch pricing.

## 10. `regex_from_examples` (50 items, ~100 in / 60 out)

A spec plus four strings that must match and four that must not. Pass when the regex, used with Python's
`re.fullmatch`, classifies 12 hidden strings correctly. The task most likely to need retries.

## Hard tier (`--tier hard`)

Six harder variants reuse the validators and normalisation rules above, so a pass means the same thing.

- `invoice_extraction_hard` (50): ten fields — vendor, number, issue date, due date, currency, net amount,
  tax, total, deposit paid, amount due. Invoices carry order and delivery dates as decoys, optional discount
  and shipping lines, a deposit, prices that may include VAT (so net and tax must be split back out), and
  often only "Net N days" terms, so the due date has to be computed.
- `strict_json_hard` (50): a nested schema with stock quantity, dimensions in millimetres and colour/SKU
  variants. Weights arrive in lb or oz and sizes in inches, converted with the stated factors and rounded
  half up; the price is the current one of a "was/now" pair; stock is written in words or as "sold out".
- `text_to_sql_hard` (30): 15 templates over the same three databases needing window functions (ROW_NUMBER,
  LAG), HAVING, NOT EXISTS, julianday arithmetic, self-joins and percentages. Questions whose LIMIT 1
  answer would be a tie are skipped, and questions that list names say how to treat two people sharing one.
- `tool_calling_hard` (50): the same tools, with today stated as Thursday 2026-10-01. Requests use relative
  dates ("Friday of the week after next"), spoken times and durations ("quarter to nine", "three quarters
  of an hour"), amounts in words, currencies named by country, "don't create a calendar event" decoys, a
  refund share to compute and days overdue from issue date and terms.
- `long_doc_qa_hard` (50): the same cached handbook, with questions that combine sections: highest or
  lowest region, the difference between two figures, how many items exceed a threshold, a sum.
- `regex_from_examples_hard` (40): 42 spec families such as binary multiples of 3, calendar dates with leap
  years, Roman numerals, thousands separators, MAC addresses with one consistent separator, IPv6, semver
  with prerelease, password rules and counting constraints. Most negatives are well-formed near misses.

## Reproducibility

`registry.SEED` (20261028) is mixed with each task id, so the same seed always gives the same items.
`data/manifest.json` lists every generated file's SHA-256. `python generate.py --check` fails if any text
file in `data/` differs from what the generators produce now, or if a receipt PNG differs from its recorded
hash. The PNGs are rendered once and committed, because Pillow's text rendering and PNG encoding vary
slightly between platforms; `--rerender-images` overwrites them and updates their hashes.
