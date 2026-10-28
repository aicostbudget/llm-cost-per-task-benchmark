"""Run the benchmark against real models, or estimate what a run would cost.

    python runner.py --estimate
    python runner.py --dry-run --models claude-haiku-5-5 --tasks invoice_extraction --limit 1
    python runner.py --run --budget 5 [--models a,b] [--tasks x,y] [--limit N] [--run-id NAME]
    python runner.py --summarize runs/<run-id>

A live run needs the provider SDKs (pip install -r requirements-runner.txt) and API keys in environment
variables only (OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY, DEEPSEEK_API_KEY). Keys are never
written to logs. Prices come from the public AI API pricing dataset (github.com/aicostbudget/ai-api-pricing-data),
pinned to its current commit, unless --pricing points at a local copy. Every attempt is appended to runs/<run-id>/attempts.jsonl, so an interrupted run resumes
where it stopped. The run stops before any attempt that could push spend past --budget.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from bench import registry  # noqa: E402

MAX_ATTEMPTS = 3
FEEDBACK = "Your previous answer failed validation: {reason}\nReply again, following the original instructions exactly."
# Rough output tokens per attempt by task, before reasoning; used for --estimate and the budget guard only.
OUTPUT_GUESS = {"invoice_extraction": 150, "receipt_vision": 80, "strict_json": 250, "text_to_sql": 120,
                "intent_classification": 10, "bug_fix": 300, "tool_calling": 80, "long_doc_qa": 40,
                "record_normalization": 150, "regex_from_examples": 60}
IMAGE_TOKENS_GUESS = 1500
PRICING_REPO = "aicostbudget/ai-api-pricing-data"
PRICING_FILE = "data/canonical/models.json"
CALCULATOR_URL = ("https://aicostbudget.com/en/model-switch-cost-calculator"
                  "?utm_source=github&utm_medium=referral&utm_campaign=cost-per-task-benchmark&utm_content=report")


def load_roster(selected: str | None) -> list[dict]:
    roster = json.loads((HERE / "models.json").read_text(encoding="utf-8"))["models"]
    if selected:
        wanted = selected.split(",")
        unknown = set(wanted) - {m["model_id"] for m in roster}
        if unknown:
            raise SystemExit(f"not in models.json: {', '.join(sorted(unknown))}")
        roster = [m for m in roster if m["model_id"] in wanted]
    return roster


def fetch_public_prices() -> tuple[list, dict]:
    """Download the canonical price file from the public dataset, pinned to the commit main points at now,
    so the run records exactly which prices it used. Cached under runs/.pricing/<commit>.json."""
    def get(url: str) -> bytes:
        request = urllib.request.Request(url, headers={"User-Agent": "cost-per-task-benchmark"})
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read()

    commit = json.loads(get(f"https://api.github.com/repos/{PRICING_REPO}/commits/main"))["sha"]
    cache = HERE / "runs" / ".pricing" / f"{commit}.json"
    if not cache.exists():
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(get(f"https://raw.githubusercontent.com/{PRICING_REPO}/{commit}/{PRICING_FILE}"))
    content = cache.read_bytes()
    return json.loads(content), {"pricing_source": f"https://github.com/{PRICING_REPO}/blob/{commit}/{PRICING_FILE}",
                                 "dataset_commit": commit, "pricing_sha256": hashlib.sha256(content).hexdigest()}


def load_prices(path: Path | None, roster: list[dict]) -> tuple[dict, dict]:
    if path is None:
        canonical, meta = fetch_public_prices()
    else:
        content = path.read_bytes()
        canonical = json.loads(content)
        try:
            commit = subprocess.run(["git", "-C", str(path.parent), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        except OSError:
            commit = ""
        meta = {"pricing_source": str(path), "dataset_commit": commit, "pricing_sha256": hashlib.sha256(content).hexdigest()}
    by_id = {(m["provider_id"], m["model_id"]): m for m in canonical}
    prices = {}
    for model in roster:
        entry = by_id.get((model["provider"], model["model_id"]))
        if not entry or not entry.get("pricing") or entry["pricing"].get("input") is None:
            raise SystemExit(f"no standard price for {model['provider']}/{model['model_id']} in {meta['pricing_source']}")
        p = entry["pricing"]
        prices[model["model_id"]] = {"input": p["input"], "output": p["output"],
                                     "cached_input": p.get("cached_input") if p.get("cached_input") is not None else p["input"],
                                     "cache_write": p.get("cache_write") if p.get("cache_write") is not None else p["input"]}
    return prices, meta


def attempt_cost(usage: dict, price: dict) -> float:
    return (usage["input_uncached"] * price["input"] + usage["input_cached"] * price["cached_input"]
            + usage["cache_write"] * price["cache_write"] + usage["output"] * price["output"]) / 1_000_000


def selected_tasks(names: str | None):
    if not names:
        return registry.TASKS
    unknown = set(names.split(",")) - set(registry.BY_ID)
    if unknown:
        raise SystemExit(f"unknown task(s): {', '.join(sorted(unknown))}")
    return [registry.BY_ID[n] for n in names.split(",")]


def prompt_tokens_guess(prompt: dict) -> tuple[float, float]:
    """(system-and-tools tokens, user tokens) at about 4 characters per token."""
    system = len(prompt["system"]) + (len(json.dumps(prompt["tools"])) if prompt.get("tools") else 0)
    user = len(prompt["user"]) + IMAGE_TOKENS_GUESS * 4 * len(prompt.get("images", []))
    return system / 4, user / 4


def estimate_attempt(task_id: str, prompt: dict, attempt: int, model: dict, price: dict, first_call: bool) -> float:
    system, user = prompt_tokens_guess(prompt)
    user += (attempt - 1) * (OUTPUT_GUESS[task_id] + 80)
    output = OUTPUT_GUESS[task_id] + model["reasoning_allowance"]
    if prompt.get("cache_system"):
        system_cost = system * (price["cache_write"] if first_call else price["cached_input"])
    else:
        system_cost = system * price["input"]
    return (system_cost + user * price["input"] + output * price["output"]) / 1_000_000


def estimate(args, roster, prices) -> int:
    print(f"{'model':<20}{'1 attempt':>12}{'up to 3 attempts':>18}")
    totals = [0.0, 0.0]
    for model in roster:
        one = worst = 0.0
        for task in selected_tasks(args.tasks):
            if task.TASK_ID == "receipt_vision" and not model["vision"]:
                continue
            items, shared = registry.generate(task)
            for index, item in enumerate(items[: args.limit or None]):
                prompt = registry.prompt(task, item, shared)
                one += estimate_attempt(task.TASK_ID, prompt, 1, model, prices[model["model_id"]], index == 0)
                worst += sum(estimate_attempt(task.TASK_ID, prompt, k, model, prices[model["model_id"]], index == 0 and k == 1)
                             for k in range(1, MAX_ATTEMPTS + 1))
        totals[0] += one
        totals[1] += worst
        print(f"{model['model_id']:<20}{one:>11.2f}${worst:>17.2f}$")
    print(f"{'total':<20}{totals[0]:>11.2f}${totals[1]:>17.2f}$")
    print("Reasoning tokens are a guess (models.json reasoning_allowance); real runs log actual usage.")
    return 0


def validator_output(task_id: str, reply) -> str:
    if task_id == "tool_calling":
        return json.dumps(reply.tool_call if reply.tool_call else {"tool": None, "arguments": {}})
    return reply.text


def assistant_turn_text(reply) -> str:
    return reply.text if reply.text else json.dumps(reply.tool_call or {})


def done_keys(log: Path) -> set[tuple[str, str]]:
    if not log.exists():
        return set()
    keys = set()
    for line in log.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row.get("final") and "api_error" not in row:  # items that hit an API error are retried on resume
            keys.add((row["model_id"], row["item_id"]))
    return keys


def run(args, roster, prices, pricing_meta) -> int:
    from bench import providers
    missing = providers.missing_keys({m["provider"] for m in roster})
    if missing and not args.dry_run:
        raise SystemExit(f"set these environment variables first: {', '.join(missing)}")
    run_dir = HERE / "runs" / (args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    log = run_dir / "attempts.jsonl"
    if not args.dry_run:
        run_dir.mkdir(parents=True, exist_ok=True)
        meta = {"started_at": datetime.now(timezone.utc).isoformat(), "budget_usd": args.budget, "seed": registry.SEED,
                "models": roster, "prices_per_million": prices, **pricing_meta}
        (run_dir / "run.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    spent = sum(json.loads(l)["cost_usd"] for l in log.read_text(encoding="utf-8").splitlines()) if log.exists() else 0.0
    finished = done_keys(log)
    adapters: dict[str, object] = {}
    for task in selected_tasks(args.tasks):
        items, shared = registry.generate(task)
        task_dir = HERE / "data" / task.TASK_ID
        for model in roster:
            if task.TASK_ID == "receipt_vision" and not model["vision"]:
                continue
            price = prices[model["model_id"]]
            for index, item in enumerate(items[: args.limit or None]):
                if (model["model_id"], item["id"]) in finished:
                    continue
                prompt = registry.prompt(task, item, shared)
                images = [task_dir / p for p in prompt.get("images", [])]
                turns = [{"role": "user", "text": prompt["user"]}]
                if args.dry_run:
                    print(json.dumps({"model": model["api_model"], "provider": model["provider"], "system_chars": len(prompt["system"]),
                                      "turns": turns, "images": [str(p) for p in images], "tools": [t["name"] for t in prompt.get("tools", [])],
                                      "cache_system": bool(prompt.get("cache_system"))}, ensure_ascii=False)[:600])
                    continue
                adapter = adapters.get(model["provider"]) or adapters.setdefault(model["provider"], providers.ADAPTERS[model["provider"]]())
                for attempt in range(1, MAX_ATTEMPTS + 1):
                    guard = 3 * estimate_attempt(task.TASK_ID, prompt, attempt, model, price, index == 0 and attempt == 1)
                    if spent + guard > args.budget:
                        print(f"stopping: spent ${spent:.2f}, next attempt could exceed the ${args.budget:.2f} budget")
                        return 2
                    if args.pace:
                        time.sleep(args.pace)
                    started = time.monotonic()
                    try:
                        reply = adapter.send(model["api_model"], prompt["system"], turns, images, prompt.get("tools"),
                                             bool(prompt.get("cache_system")))
                    except Exception as error:  # SDK already retried 429/5xx/connection errors
                        row = {"model_id": model["model_id"], "task": task.TASK_ID, "item_id": item["id"], "attempt": attempt,
                               "api_error": f"{type(error).__name__}: {str(error)[:300]}", "cost_usd": 0.0, "final": True}
                        with log.open("a", encoding="utf-8") as handle:
                            handle.write(json.dumps(row) + "\n")
                        print(f"API error {model['model_id']} {item['id']}: {row['api_error']}")
                        break
                    usage = vars(reply.usage)
                    cost = attempt_cost(usage, price)
                    spent += cost
                    verdict = registry.validate(task, item, validator_output(task.TASK_ID, reply), shared)
                    final = verdict.ok or attempt == MAX_ATTEMPTS
                    row = {"model_id": model["model_id"], "task": task.TASK_ID, "item_id": item["id"], "attempt": attempt,
                           "ok": verdict.ok, "reason": verdict.reason, "usage": usage, "cost_usd": round(cost, 8),
                           "stop_reason": reply.stop_reason, "latency_s": round(time.monotonic() - started, 2),
                           "response_id": reply.raw_id, "output": validator_output(task.TASK_ID, reply)[:4000],
                           "at": datetime.now(timezone.utc).isoformat(), "final": final}
                    with log.open("a", encoding="utf-8") as handle:
                        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
                    print(f"{model['model_id']:<18} {item['id']:<28} try {attempt} {'PASS' if verdict.ok else 'fail'} ${cost:.5f} total ${spent:.2f}")
                    if final:
                        break
                    turns = turns + [{"role": "assistant", "text": assistant_turn_text(reply)},
                                     {"role": "user", "text": FEEDBACK.format(reason=verdict.reason)}]
    if not args.dry_run:
        print(f"done: spent ${spent:.2f}")
        summarize(run_dir)
    return 0


def summarize(run_dir: Path) -> int:
    rows = [json.loads(l) for l in (run_dir / "attempts.jsonl").read_text(encoding="utf-8").splitlines()]
    by_key: dict[tuple, list] = defaultdict(list)
    for row in rows:
        by_key[(row["task"], row["model_id"], row["item_id"])].append(row)
    table: dict[tuple, dict] = defaultdict(lambda: {"items": 0, "api_errors": 0, "first_ok": 0, "ok": 0, "attempts": 0,
                                                    "cost_first": 0.0, "cost_all": 0.0, "output_tokens": 0,
                                                    "first_input": 0, "first_cached": 0, "first_output": 0})
    for (task, model, _), attempts in by_key.items():
        cell = table[(task, model)]
        answered = sorted((a for a in attempts if "api_error" not in a), key=lambda a: a["attempt"])
        if not answered:
            cell["api_errors"] += 1
            continue
        attempts = answered
        cell["items"] += 1
        cell["attempts"] += len(attempts)
        cell["first_ok"] += attempts[0]["ok"]
        cell["ok"] += any(a["ok"] for a in attempts)
        cell["cost_first"] += attempts[0]["cost_usd"]
        cell["cost_all"] += sum(a["cost_usd"] for a in attempts)
        cell["output_tokens"] += sum(a["usage"]["output"] for a in attempts)
        first = attempts[0]["usage"]
        cell["first_input"] += first["input_uncached"] + first["input_cached"] + first["cache_write"]
        cell["first_cached"] += first["input_cached"]
        cell["first_output"] += first["output"]
    summary = []
    for (task, model), c in sorted(table.items()):
        n = c["items"] or 1
        summary.append({
            "task": task, "model_id": model, "items": c["items"], "api_errors": c["api_errors"],
            "first_attempt_success": round(c["first_ok"] / n, 4), "success_within_3": round(c["ok"] / n, 4),
            "mean_attempts": round(c["attempts"] / n, 3),
            "cost_per_success_1_attempt": round(c["cost_first"] / c["first_ok"], 6) if c["first_ok"] else None,
            "cost_per_success_3_attempts": round(c["cost_all"] / c["ok"], 6) if c["ok"] else None,
            "total_cost_usd": round(c["cost_all"], 6), "mean_output_tokens_per_attempt": round(c["output_tokens"] / max(c["attempts"], 1), 1),
            # The model-switch calculator's inputs, as measured on the first attempt of each item.
            "calculator": {"input_tokens_per_request": round(c["first_input"] / n), "output_tokens_per_request": round(c["first_output"] / n),
                           "cached_input_share_percent": round(100 * c["first_cached"] / c["first_input"], 1) if c["first_input"] else 0,
                           "success_rate_percent": round(100 * c["first_ok"] / n, 1),
                           "retry_rate_percent": round(100 * (c["attempts"] - c["items"]) / n, 1)}})
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    (run_dir / "report.md").write_text(report_markdown(summary, run_dir), encoding="utf-8")
    print(f"{'task':<22}{'model':<18}{'n':>4}{'1st':>7}{'<=3':>7}{'tries':>7}{'$/success':>12}{'api err':>9}")
    for s in summary:
        cps = s["cost_per_success_3_attempts"]
        print(f"{s['task']:<22}{s['model_id']:<18}{s['items']:>4}{s['first_attempt_success']:>7.0%}{s['success_within_3']:>7.0%}"
              f"{s['mean_attempts']:>7.2f}{('$%.5f' % cps) if cps is not None else '-':>12}{s['api_errors']:>9}")
    print(f"wrote {run_dir / 'summary.json'} and {run_dir / 'report.md'}")
    return 0


def _money(value: float | None) -> str:
    return "-" if value is None else (f"${value:.4f}" if value >= 0.001 else f"${value * 1000:.3f}/1K")


def report_markdown(summary: list[dict], run_dir: Path) -> str:
    meta_path = run_dir / "run.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    lines = ["# Cost per successful task", "",
             f"Run `{run_dir.name}`, prices from {meta.get('pricing_source', 'unknown')}.", "",
             "| Task | Model | Items | 1st try | Within 3 | Tries | $/success (1 try) | $/success (≤3) |",
             "|---|---|---:|---:|---:|---:|---:|---:|"]
    for s in summary:
        lines.append(f"| {s['task']} | {s['model_id']} | {s['items']} | {s['first_attempt_success']:.0%} | {s['success_within_3']:.0%} | "
                     f"{s['mean_attempts']:.2f} | {_money(s['cost_per_success_1_attempt'])} | {_money(s['cost_per_success_3_attempts'])} |")
    lines += ["", "## Calculator inputs", "",
              f"Open {CALCULATOR_URL}, set Success rate source to \"Measured with my own eval\" and use these values.", "",
              "| Task | Model | Input tokens | Output tokens | Cached input | Success rate | Retry rate |",
              "|---|---|---:|---:|---:|---:|---:|"]
    for s in summary:
        c = s["calculator"]
        lines.append(f"| {s['task']} | {s['model_id']} | {c['input_tokens_per_request']:,} | {c['output_tokens_per_request']:,} | "
                     f"{c['cached_input_share_percent']}% | {c['success_rate_percent']}% | {c['retry_rate_percent']}% |")
    return "\n".join(lines) + "\n"


def main() -> int:
    # Prompts contain €, £ and similar; a Windows console defaulting to a legacy code page would crash on them.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--estimate", action="store_true")
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--summarize", type=Path, metavar="RUN_DIR")
    parser.add_argument("--pricing", type=Path, help="local data/canonical/models.json; default: download from the public dataset")
    parser.add_argument("--models")
    parser.add_argument("--tasks")
    parser.add_argument("--limit", type=int, help="first N items per task (smoke tests)")
    parser.add_argument("--budget", type=float, help="hard spending cap in USD for --run")
    parser.add_argument("--run-id")
    parser.add_argument("--pace", type=float, default=0, metavar="SECONDS", help="wait before each call (free-tier per-minute limits)")
    args = parser.parse_args()
    if args.summarize:
        return summarize(args.summarize)
    if args.run and not args.budget:
        parser.error("--run needs --budget")
    roster = load_roster(args.models)
    prices, meta = load_prices(args.pricing, roster)
    if args.estimate:
        return estimate(args, roster, prices)
    return run(args, roster, prices, meta)


if __name__ == "__main__":
    sys.exit(main())
