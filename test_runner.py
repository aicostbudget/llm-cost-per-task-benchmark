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


def check_local_roster() -> None:
    """models.local.json adds models with a typed price; such a run needs no download and no dataset entry."""
    here = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory() as tmp:
        runner.HERE = Path(tmp)
        (Path(tmp) / "models.json").write_text((here / "models.json").read_text(encoding="utf-8"), encoding="utf-8")
        local = {"models": [{"model_id": "qwen-local", "provider": "openai-compatible", "api_model": "qwen3:8b",
                             "base_url": "http://localhost:11434/v1", "price": {"input": 0.05, "output": 0.2}},
                            {"model_id": "router-model", "provider": "openai-compatible", "api_model": "vendor/model",
                             "base_url": "https://example.invalid/v1", "api_key_env": "TEST_ROUTER_KEY_UNSET",
                             "price": {"input": 1, "output": 4, "cached_input": 0.25}}]}
        (Path(tmp) / "models.local.json").write_text(json.dumps(local), encoding="utf-8")
        roster = runner.load_roster("qwen-local,router-model")
        assert [m["model_id"] for m in roster] == ["qwen-local", "router-model"]
        assert roster[0]["vision"] is False and roster[0]["reasoning_allowance"] == runner.DEFAULT_REASONING_ALLOWANCE
        prices, meta = runner.load_prices(None, roster)  # no network: every price is typed
        assert prices["qwen-local"] == {"input": 0.05, "output": 0.2, "cached_input": 0.05, "cache_write": 0.05}
        assert prices["router-model"]["cached_input"] == 0.25 and meta["pricing_source"].startswith("roster")
        assert providers.missing_keys(roster) == ["TEST_ROUTER_KEY_UNSET"], "a local server needs no key; a named key must be set"
        assert providers.adapter_key(roster[0]) != providers.adapter_key(roster[1])

        local["models"].append({"model_id": "no-price", "provider": "openai-compatible", "api_model": "x", "base_url": "http://x/v1"})
        (Path(tmp) / "models.local.json").write_text(json.dumps(local), encoding="utf-8")
        try:
            runner.load_roster(None)
            raise AssertionError("an openai-compatible entry without a price must be rejected")
        except SystemExit as stop:
            assert "needs a price" in str(stop)
        local["models"][-1] = {"model_id": "deepseek-flash", "provider": "openai-compatible", "api_model": "x", "base_url": "http://x/v1",
                               "price": {"input": 1, "output": 1}}
        (Path(tmp) / "models.local.json").write_text(json.dumps(local), encoding="utf-8")
        try:
            runner.load_roster(None)
            raise AssertionError("a model_id repeated from models.json must be rejected")
        except SystemExit as stop:
            assert "repeats" in str(stop)


class StubCompletions:
    def __init__(self, response):
        self.response = response
        self.request = None

    def create(self, **kwargs):
        self.request = kwargs
        return self.response


def stub_adapter(response) -> tuple[providers.OpenAICompatible, StubCompletions]:
    adapter = providers.OpenAICompatible.__new__(providers.OpenAICompatible)
    completions = StubCompletions(response)
    adapter.client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    return adapter, completions


def check_openai_compatible() -> None:
    """Request shape and usage parsing for the Chat Completions adapter, against a stub client."""
    ns = SimpleNamespace
    usage = ns(prompt_tokens=1200, completion_tokens=300, prompt_tokens_details=ns(cached_tokens=1000),
               completion_tokens_details=ns(reasoning_tokens=250))
    message = ns(content="<think>\nlet me see\n</think>\n\n{\"a\": 1}", tool_calls=None)
    adapter, stub = stub_adapter(ns(id="r1", usage=usage, choices=[ns(message=message, finish_reason="stop")]))
    first_png = next((Path(__file__).resolve().parent / "data" / "receipt_vision").rglob("*.png"))
    reply = adapter.send("m", "sys", [{"role": "user", "text": "hi"}], [first_png], None, False)
    assert reply.text == '{"a": 1}', reply.text
    assert vars(reply.usage) == {"input_uncached": 200, "input_cached": 1000, "cache_write": 0, "output": 300, "reasoning": 250}
    sent = stub.request["messages"]
    assert sent[0] == {"role": "system", "content": "sys"}
    assert sent[1]["content"][0]["image_url"]["url"].startswith("data:image/png;base64,") and sent[1]["content"][-1]["text"] == "hi"

    call = ns(function=ns(name="get_weather", arguments='{"city": "Graz"}'))
    usage = ns(prompt_tokens=50, completion_tokens=10, prompt_cache_hit_tokens=32)  # DeepSeek's field names
    adapter, stub = stub_adapter(ns(id="r2", usage=usage, choices=[ns(message=ns(content=None, tool_calls=[call]), finish_reason="tool_calls")]))
    tools = [{"name": "get_weather", "description": "d", "parameters": {"type": "object", "properties": {}}}]
    reply = adapter.send("m", "sys", [{"role": "user", "text": "hi"}], [], tools, False)
    assert reply.tool_call == {"tool": "get_weather", "arguments": {"city": "Graz"}} and reply.text == ""
    assert reply.usage.input_cached == 32 and reply.usage.input_uncached == 18
    assert stub.request["tools"][0]["function"]["name"] == "get_weather"

    adapter, _ = stub_adapter(ns(id="r3", usage=None, choices=[ns(message=ns(content="x", tool_calls=None), finish_reason="stop")]))
    try:
        adapter.send("m", "sys", [{"role": "user", "text": "hi"}], [], None, False)
        raise AssertionError("a reply without token usage must not be priced as free")
    except ValueError as error:
        assert "no token usage" in str(error)


def main() -> int:
    usage = {"input_uncached": 1_000_000, "input_cached": 1_000_000, "cache_write": 0, "output": 1_000_000}
    assert abs(runner.attempt_cost(usage, PRICE) - 12.1) < 1e-9, runner.attempt_cost(usage, PRICE)

    providers.ADAPTERS["fake"] = FakeAdapter
    with tempfile.TemporaryDirectory() as tmp:
        runner.HERE = Path(tmp)
        args = SimpleNamespace(tasks="invoice_extraction", limit=2, dry_run=False, budget=1.0, run_id="t", pace=0)
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

        errored = Path(tmp) / "runs" / "e" / "attempts.jsonl"
        errored.parent.mkdir(parents=True)
        errored.write_text(json.dumps({"model_id": "fake-model", "task": "invoice_extraction", "item_id": "invoice_extraction-001",
                                       "attempt": 1, "api_error": "ServerError: 503", "cost_usd": 0.0, "final": True}) + "\n", encoding="utf-8")
        calls_before = FakeAdapter.calls
        retry = SimpleNamespace(tasks="invoice_extraction", limit=1, dry_run=False, budget=1.0, run_id="e", pace=0)
        assert runner.run(retry, [MODEL], {"fake-model": PRICE}, {}) == 0
        assert FakeAdapter.calls == calls_before + 2, "an item that only hit an API error must run again on resume"
        retried = json.loads((Path(tmp) / "runs" / "e" / "summary.json").read_text(encoding="utf-8"))[0]
        assert retried["items"] == 1 and retried["api_errors"] == 0 and retried["success_within_3"] == 1

        tight = SimpleNamespace(tasks="invoice_extraction", limit=2, dry_run=False, budget=0.000001, run_id="b", pace=0)
        assert runner.run(tight, [MODEL], {"fake-model": PRICE}, {}) == 2, "budget guard must stop the run"
        assert not (Path(tmp) / "runs" / "b" / "attempts.jsonl").exists()

    check_local_roster()
    check_openai_compatible()
    print("runner tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
