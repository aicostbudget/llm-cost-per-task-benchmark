"""Check every validator against every item: the reference answer must pass and each near-miss must fail.
For the bug-fix task the buggy source must also fail, so every planted bug is real.

    python benchmarks/cost-per-task/selftest.py [--task <id>]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bench import registry  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", choices=sorted(registry.BY_ID))
    args = parser.parse_args()
    tasks = [registry.BY_ID[args.task]] if args.task else registry.ALL_TASKS
    problems = []
    for task in tasks:
        items, shared = registry.generate(task)
        if len(items) != task.DEFAULT_COUNT:
            problems.append(f"{task.TASK_ID}: {len(items)} items, expected {task.DEFAULT_COUNT}")
        if len({item["id"] for item in items}) != len(items):
            problems.append(f"{task.TASK_ID}: duplicate item ids")
        checked = 0
        for item in items:
            sent = registry.prompt(task, item, shared)
            if sent.get("tools") and getattr(task, "REPLY", "text") != "tool_call":
                problems.append(f"{task.TASK_ID}: sends tools but does not set REPLY = \"tool_call\"")
                break
            verdict = registry.validate(task, item, task.reference_output(item), shared)
            if not verdict.ok:
                problems.append(f"{item['id']}: reference answer failed: {verdict.reason}")
            for wrong in task.wrong_outputs(item):
                checked += 1
                if registry.validate(task, item, wrong, shared).ok:
                    problems.append(f"{item['id']}: wrong answer passed: {wrong[:120]!r}")
        print(f"{task.TASK_ID:<24} {len(items):>3} items, {checked:>3} near-misses checked")
    if problems:
        print(f"\n{len(problems)} problem(s):")
        print("\n".join(f"  {p}" for p in problems[:60]))
        return 1
    print("\nall validators behave as expected")
    return 0


if __name__ == "__main__":
    sys.exit(main())
