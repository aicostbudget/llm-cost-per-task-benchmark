# LLM cost per successful task

[![check](https://github.com/aicostbudget/llm-cost-per-task-benchmark/actions/workflows/check.yml/badge.svg)](https://github.com/aicostbudget/llm-cost-per-task-benchmark/actions/workflows/check.yml)
[![code: MIT](https://img.shields.io/badge/code-MIT-blue)](LICENSE-CODE)
[![data: CC BY 4.0](https://img.shields.io/badge/data-CC%20BY%204.0-blue)](LICENSE-DATA)

This measures what one correct LLM answer costs: everything you paid across all attempts, divided by the
answers that passed a check written in code.

Price per million tokens covers a single call. In practice failed answers get retried, reasoning tokens are
billed even though you never see them, and now and then a reply comes back empty. All of that ends up in the
cost per success.

There are 16 tasks (10 everyday, 6 hard) with fixed inputs and a pass/fail check in plain Python, no LLM
judge. The runner supports OpenAI, Anthropic, Google Gemini and DeepSeek and takes prices from the open
[AI API pricing dataset](https://github.com/aicostbudget/ai-api-pricing-data). You use your own API keys, and
nothing is sent anywhere except to the providers you pick. No key? [Try it free with Gemini](#trying-it-for-free-with-gemini).

## First results

So far only DeepSeek has been run, once per model, on about $1.40 of credit. Full write-up and caveats:
[results/2026-10-29-deepseek.md](results/2026-10-29-deepseek.md).

| Per 1M successful tasks (list price) | deepseek-flash | deepseek-v4-pro | |
|---|---:|---:|---:|
| Standard tier, 9 tasks | $347 | $1,698 | 4.9× |
| Hard tier, 6 tasks | $596 | $5,478 | 9.2× |
| Success within 3 attempts | 100% | 100% | |

Both models got every item right within 3 attempts. V4 Pro's output price is 3.3× flash's, but it wrote up
to 4.3× more output tokens, nearly all of them reasoning. Three times it hit the 16K output limit and
returned nothing, and those calls were billed too.

Because both models scored 100%, these tasks don't separate them on accuracy yet. If you have task ideas
that are cheap to check in code but still trip models up, [issue #2](https://github.com/aicostbudget/llm-cost-per-task-benchmark/issues/2)
is the place.

The DeepSeek and Gemini adapters have been run against the live APIs. The OpenAI and Anthropic ones haven't
yet, so expect rough edges there.

## Quick start

Python 3.11 or newer.

```
git clone https://github.com/aicostbudget/llm-cost-per-task-benchmark
cd llm-cost-per-task-benchmark
pip install -r requirements.txt -r requirements-runner.txt

python runner.py --estimate                                   # what a run would cost, no API calls
export ANTHROPIC_API_KEY=...                                  # only the providers you will use
python runner.py --run --models claude-haiku-5-5 --limit 1 --budget 1     # smoke test: 1 item per task
python runner.py --run --models claude-haiku-5-5 --budget 3 --run-id haiku
```

On Windows PowerShell set keys with `$env:ANTHROPIC_API_KEY = "..."`. Keys are read from `OPENAI_API_KEY`,
`ANTHROPIC_API_KEY`, `GEMINI_API_KEY` and `DEEPSEEK_API_KEY` and never written to disk.

The run prints a table and writes `runs/<run-id>/report.md`:

- first-attempt success rate and success within 3 attempts
- mean attempts per item
- cost per successful task with 1 attempt and with up to 3 attempts
- the measured token counts, cached-input share, success rate and retry rate to paste into the
  [model switch cost calculator](https://aicostbudget.com/en/model-switch-cost-calculator?utm_source=github&utm_medium=referral&utm_campaign=cost-per-task-benchmark&utm_content=readme)
  with "Success rate source: Measured with my own eval"

`--budget` is a hard cap: the runner stops before any attempt that could take spend past it. Re-running with
the same `--run-id` resumes where it stopped; items that only hit API errors are tried again.

### Trying it for free with Gemini

A free [Google AI Studio](https://aistudio.google.com) key (no billing account needed) is enough for a smoke
test. Free-tier quotas are per model and per day and can be small (we saw 20 requests a day on
`gemini-3.8-flash`), so test one item per task on a lite model and slow down to the per-minute limit:

```
python runner.py --run --models gemini-3.5-flash-lite --limit 1 --pace 7 --budget 1 --run-id free-smoke
```

Costs in the report are what the run would cost at paid prices, which is the number the benchmark is about;
on the free tier nothing is billed. A 429 "quota exceeded" is not retried, because retries would count
against the daily quota; resume the same `--run-id` the next day.

## The tasks

| Task | Items | What the model does | Pass means |
|---|---:|---|---|
| `invoice_extraction` | 50 | Pull 8 fields from a plain-text invoice | every field equal after normalisation |
| `receipt_vision` | 30 | Read merchant, date and total from a receipt image | all three equal |
| `strict_json` | 50 | Turn a product description into JSON for a strict schema | schema-valid and key fields equal |
| `text_to_sql` | 50 | Write SQLite for a question over one of 3 databases | same result set as the reference query |
| `intent_classification` | 50 | Label a support message with one of 20 intents | exact label |
| `bug_fix` | 50 | Fix one planted bug in a short Python function | hidden unit tests pass |
| `tool_calling` | 50 | Pick a tool and arguments, or no tool | right tool and arguments |
| `long_doc_qa` | 50 | Answer from a ~30K-token handbook sent as a cacheable prefix | short answer equal |
| `record_normalization` | 50 | Normalise messy contact records | 5 fields in canonical form |
| `regex_from_examples` | 50 | Write a regex from a spec and examples | 12 hidden strings classified correctly |

Details, normalisation rules and why each task is in the set: [TASKS.md](TASKS.md).

### Hard tier

Strong models pass nearly every standard item on the first try, so the cost per success there mostly
measures price and token use. `--tier hard` runs six harder variants instead (`--tier all` runs both):

| Task | Items | What is harder |
|---|---:|---|
| `invoice_extraction_hard` | 50 | 10 fields; discount, shipping, deposit, VAT-inclusive prices, due date from "Net N" terms, order and delivery dates as decoys |
| `strict_json_hard` | 50 | nested schema with dimensions and variant SKUs; lb, oz and inch conversions; was/now prices; stock in words |
| `text_to_sql_hard` | 30 | window functions, HAVING, NOT EXISTS, date arithmetic, per-group top-N, percentages |
| `tool_calling_hard` | 50 | relative dates, spoken times and durations, numbers in words, currencies named by country, "not that tool" decoys, computed arguments |
| `long_doc_qa_hard` | 50 | multi-hop questions over the same handbook: comparisons, differences, counts and sums across sections |
| `regex_from_examples_hard` | 40 | dates with leap years, Roman numerals, IPv6, backreferences, lookaheads, counting constraints; negatives that look valid |

```
python runner.py --estimate --tier hard
python runner.py --run --tier hard --models deepseek-flash --budget 1 --run-id flash-hard
```

Every input is generated by code in this repository from a fixed seed: names, companies, receipts and
databases are invented, nothing comes from a public dataset a model may have trained on. `python generate.py
--check` regenerates every text file and proves `data/` matches byte for byte; the receipt PNGs, whose
rendering differs slightly between platforms, are checked against the hashes in `data/manifest.json`.

## How a run works

- Same system prompt and user prompt for every model. Provider defaults are kept: no temperature, no
  reasoning or effort setting, no automatic fallback to another model. A refusal counts as a failed attempt.
- Up to 3 attempts per item. After a failed check, the validator's reason is sent back as the next user
  message, the way an application would retry.
- API errors (rate limits, 5xx, timeouts) are retried by the provider SDK and, if they persist, logged
  separately; they never count as model failures.
- Every attempt is a line in `runs/<run-id>/attempts.jsonl`: uncached input, cached input, cache-write,
  output and reasoning tokens, cost, verdict, reason and the model's output.
- Caching is measured as each provider reports it. Anthropic gets an explicit cache breakpoint on the
  system prompt; OpenAI and DeepSeek cache automatically; Gemini's implicit caching is best effort and the
  runner creates no explicit Gemini cache, so `long_doc_qa` on Gemini may show no cached tokens.
- Prices are downloaded from the pricing dataset pinned to its current commit, which is recorded in
  `runs/<run-id>/run.json`. Use `--pricing <path>` for a local copy.

## Adding a model

Add an entry to `models.json`: `model_id` as it appears in the pricing dataset, `provider` (`openai`,
`anthropic`, `google-gemini`, `deepseek`), `api_model` as the provider's API expects it, and whether it takes
images. `reasoning_allowance` only affects `--estimate`.

## Checking the harness itself

```
python selftest.py       # every reference answer passes and every planted wrong answer fails
python test_runner.py    # cost math, retries, resume and the budget stop, with a fake provider
```

## Sharing results

Published runs are in [results/](results/), starting with
[DeepSeek flash vs V4 Pro on both tiers](results/2026-10-29-deepseek.md).

Open an issue with your `report.md` and the `run.json` next to it. Please do not post `attempts.jsonl` if you
changed prompts or data; results are only comparable on the unmodified task set.

## Licence

Code: MIT ([LICENSE-CODE](LICENSE-CODE)). Generated task data in `data/`: CC BY 4.0
([LICENSE-DATA](LICENSE-DATA)).
