"""The task list, plus uniform access to tasks whose functions take an optional `shared` argument."""

from __future__ import annotations

import inspect
import random
from types import ModuleType

from .tasks import (bug_fix, intent_classification, invoice_extraction, long_doc_qa, receipt_vision, record_normalization,
                    regex_from_examples, strict_json, text_to_sql, tool_calling)

TASKS: list[ModuleType] = [invoice_extraction, receipt_vision, strict_json, text_to_sql, intent_classification, bug_fix,
                           tool_calling, long_doc_qa, record_normalization, regex_from_examples]
BY_ID = {task.TASK_ID: task for task in TASKS}
SEED = 20261028


def generate(task: ModuleType, count: int | None = None, seed: int = SEED) -> tuple[list[dict], dict]:
    """Same seed and count always give the same items: the seed is mixed with the task id."""
    rng = random.Random(f"{seed}:{task.TASK_ID}")
    result = task.generate(rng, count or task.DEFAULT_COUNT)
    return result if isinstance(result, tuple) else (result, {})


def prompt(task: ModuleType, item: dict, shared: dict) -> dict:
    return task.prompt(item, shared)


def validate(task: ModuleType, item: dict, output: str, shared: dict):
    if len(inspect.signature(task.validate).parameters) >= 3:
        return task.validate(item, output, shared)
    return task.validate(item, output)
