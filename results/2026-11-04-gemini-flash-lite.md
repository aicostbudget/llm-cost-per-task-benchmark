# Gemini 3.5 Flash-Lite, 2026-11-02 to 11-04

One model, both tiers, one run, provider defaults, using a free Google AI Studio key. The free quota is about
500 requests a day, so the run took three days and requests went out about 7.5 seconds apart. Nothing was
billed. Costs below are what the logged tokens would cost at Google's paid list prices, from the pricing
dataset at commit `edbff84`.

| Price per million tokens | Input | Cached input | Output |
|---|---:|---:|---:|
| gemini-3.5-flash-lite | $0.30 | $0.03 | $2.50 |
| deepseek-flash (Peak, for comparison) | $0.30 | $0.006 | $1.20 |

**Read this before quoting the totals.** Google's pricing page lists context caching as "Not available" on the
free tier for this model. The API still reported some cached tokens, but we cannot say the hit rate below is
what a paid key gets. The runner creates no explicit Gemini cache. See "Cache range" for what the totals look
like at other hit rates.

DeepSeek figures are from [the 2026-10-29 run](2026-10-29-deepseek.md). That run skipped `receipt_vision`, so
comparison totals here leave it out too.

## Standard tier (10 tasks, 480 items)

| Task | Items | 1st try | Within 3 | Flash-Lite $/success | deepseek-flash $/success |
|---|---:|---:|---:|---:|---:|
| invoice_extraction | 50 | 100% | 100% | $0.00042 | $0.00028 |
| strict_json | 50 | 100% | 100% | $0.00041 | $0.00032 |
| text_to_sql | 50 | 94% | 100% | $0.00018 | $0.00021 |
| intent_classification | 50 | 100% | 100% | $0.00012 | $0.00011 |
| bug_fix | 50 | 98% | 100% | $0.00027 | $0.00078 |
| tool_calling | 50 | 100% | 100% | $0.00036 | $0.00019 |
| long_doc_qa | 50 | 100% | 100% | $0.00604 | $0.00023 |
| record_normalization | 50 | 100% | 100% | $0.00026 | $0.00074 |
| regex_from_examples | 50 | 86% | 100% | $0.00009 | $0.00025 |
| receipt_vision | 30 | 100% | 100% | $0.00044 | not run |
| **total spend, 9 shared tasks (450 items)** | | | | **$0.4071** | **$0.156** |

## Hard tier (6 tasks, 270 items)

| Task | Items | 1st try | Within 3 | Flash-Lite $/success | deepseek-flash $/success |
|---|---:|---:|---:|---:|---:|
| invoice_extraction_hard | 50 | 98% | 100% | $0.00059 | $0.00079 |
| strict_json_hard | 50 | 94% | 100% | $0.00080 | $0.00057 |
| text_to_sql_hard | 30 | 100% | 100% | $0.00034 | $0.00053 |
| tool_calling_hard | 50 | 94% | 100% | $0.00038 | $0.00024 |
| long_doc_qa_hard | 50 | 82% | 100% | $0.00626 | $0.00027 |
| regex_from_examples_hard | 40 | 75% | 85% | $0.00023 | $0.00129 |
| **total spend, 264 of 270 correct** | | | | **$0.4194** | **$0.161** |

## Totals

| Per 1M correct answers | Flash-Lite | deepseek-flash |
|---|---:|---:|
| Standard, 9 shared tasks | $905 | $347 |
| Hard, 6 tasks | $1,589 | $596 |
| Standard, without long_doc_qa (8 tasks, 400 items) | $262 | $361 |
| Hard, without long_doc_qa_hard (5 tasks, 220 items) | $498 | $670 |
| Success within 3 attempts, standard | 100% | 100% |
| Success within 3 attempts, hard | 97.8% | 100% |

## Cache range

`long_doc_qa` sends a handbook of about 20K tokens on every call. DeepSeek served 98.8% of that input from its
cache. Flash-Lite got one hit in 50 calls on the standard task (1.6% of input tokens) and 12 hits in 60 calls
on the hard one (17.1%). That one task is 74% of Flash-Lite's standard spend and 75% of its hard spend.

The rows below are arithmetic on the logged tokens, not measurements: same tokens, same answers, different
share of long-document input billed at the cached rate.

| Long-document input from cache | Standard, per 1M correct | Hard, per 1M correct |
|---|---:|---:|
| 0% | $915 | $1,804 |
| As measured (1.6% / 17.1%) | $905 | $1,589 |
| 98.8%, DeepSeek's rate | $310 | $560 |
| deepseek-flash, for comparison | $347 | $596 |

Flash-Lite ties deepseek-flash at about 93% of long-document input from cache on the standard tier and about
96% on the hard tier. This leaves out any storage fee from an explicit cache, which we did not test: Google
lists $1.00 per 1M tokens per hour for this model on paid keys.

## What the numbers say

- Without the long document, Flash-Lite is about 27% cheaper per correct answer on the standard tier and 26%
  on the hard tier, despite an output price 2.1× deepseek-flash's. It reported no reasoning tokens. On the 9
  shared standard tasks it wrote 25,733 output tokens against deepseek-flash's 101,129, and 81% of DeepSeek's
  were reasoning.
- Task by task, Flash-Lite was cheaper on 7 of 15 and deepseek-flash on 8, both long-document tasks included.
  DeepSeek tends to win where prompts are long and repeat (tool schemas, JSON schemas). Flash-Lite wins where
  DeepSeek reasons at length (bug fixes, record cleanup, regexes).
- With the long document included, the order depends on the cache hit rate, and this run cannot tell you the
  rate on a paid key.
- This is the first model in the benchmark to fail items after 3 attempts, so these tasks now separate models
  on accuracy a little.

## Failures

All 6 final failures are in `regex_from_examples_hard`: items 010, 019, 025, 029, 039 and 040. These are model
errors. Both DeepSeek models passed the same items, and one of Flash-Lite's answers does not compile (invalid
group reference). Six misses in one task type is too little to quote "97.8% accurate" as a general number.

`long_doc_qa_hard` was the other weak spot on the first try at 82%, and every item passed on a retry.
