"""Offline checks for runner.py: cost arithmetic, the retry loop with a fake provider, resume, the budget
stop and the summary. No network and no SDKs."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))

import runner  # noqa: E402
from bench import providers, registry  # noqa: E402

PRICE = {"input": 2.0, "output": 10.0, "cached_input": 0.1, "cache_write": 2.5}
MODEL = {"model_id": "fake-model", "provider": "fake", "api_model": "fake-model", "vision": True, "reasoning_allowance": 0}


class FakeAdapter:
    """Fails the first attempt of every item with malformed output, then answers with the reference."""

    calls = 0

    def send(self, api_model, system, turns, images, tools, cache_system):
        FakeAdapter.calls += 1
        task = registry.BY_ID["invoice_extraction"]
        items, _ = registry.generate(task)
        item = next(i for i in items if i["input"]["document"] == turns[0]["text"])
        text = "not json" if len(turns) == 1 else task.reference_output(item)
        return providers.Reply(text, None, providers.Usage(input_uncached=1000, output=100), "end_turn", "fake")


def main() -> int:
    usage = {"input_uncached": 1_000_000, "input_cached": 1_000_000, "cache_write": 0, "output": 1_000_000}
    assert abs(runner.attempt_cost(usage, PRICE) - 12.1) < 1e-9, runner.attempt_cost(usage, PRICE)

    providers.ADAPTERS["fake"] = FakeAdapter
    with tempfile.TemporaryDirectory() as tmp:
        runner.HERE = Path(tmp)
        args = SimpleNamespace(tasks="invoice_extraction", limit=2, dry_run=False, budget=1.0, run_id="t")
        assert runner.run(args, [MODEL], {"fake-model": PRICE}, {}) == 0
        log = Path(tmp) / "runs" / "t" / "attempts.jsonl"
        rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
        assert [r["attempt"] for r in rows] == [1, 2, 1, 2], rows
        assert [r["ok"] for r in rows] == [False, True, False, True]
        assert rows[0]["reason"].startswith("output is not valid JSON")
        summary = json.loads((Path(tmp) / "runs" / "t" / "summary.json").read_text(encoding="utf-8"))[0]
        assert summary["first_attempt_success"] == 0 and summary["success_within_3"] == 1 and summary["mean_attempts"] == 2
        per_attempt = (1000 * 2.0 + 100 * 10.0) / 1_000_000
        assert abs(summary["cost_per_success_3_attempts"] - 2 * per_attempt) < 1e-9
        assert summary["calculator"] == {"input_tokens_per_request": 1000, "output_tokens_per_request": 100,
                                         "cached_input_share_percent": 0, "success_rate_percent": 0.0, "retry_rate_percent": 100.0}
        report = (Path(tmp) / "runs" / "t" / "report.md").read_text(encoding="utf-8")
        assert "| invoice_extraction | fake-model | 2 | 0% | 100% | 2.00 |" in report and "utm_campaign=cost-per-task-benchmark" in report

        calls_before = FakeAdapter.calls
        assert runner.run(args, [MODEL], {"fake-model": PRICE}, {}) == 0
        assert FakeAdapter.calls == calls_before, "resume must skip finished items"

        tight = SimpleNamespace(tasks="invoice_extraction", limit=2, dry_run=False, budget=0.000001, run_id="b")
        assert runner.run(tight, [MODEL], {"fake-model": PRICE}, {}) == 2, "budget guard must stop the run"
        assert not (Path(tmp) / "runs" / "b" / "attempts.jsonl").exists()
    print("runner tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
