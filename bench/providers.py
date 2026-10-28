"""One adapter per provider, each on the provider's official Python SDK (requirements-runner.txt).
SDKs are imported only when a live run starts, so --estimate and --dry-run need none of them.

Every adapter takes the same conversation (system text, a list of user/assistant turns, optional images
on the first user turn, optional tools) and returns a Reply with the text, any tool call, and token usage
split the same way for every provider, so cost is computed in one place (runner.attempt_cost).

Provider defaults are kept on purpose: no temperature, no effort or reasoning setting, no fallbacks to
another model. A refusal counts as a failed attempt, recorded with its stop reason."""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

MAX_OUTPUT_TOKENS = 16000
KEY_ENV = {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY", "google-gemini": "GEMINI_API_KEY",
           "deepseek": "DEEPSEEK_API_KEY"}


@dataclass
class Usage:
    input_uncached: int = 0
    input_cached: int = 0
    cache_write: int = 0
    output: int = 0          # includes reasoning tokens, which every provider bills as output
    reasoning: int = 0       # informational part of `output`


@dataclass
class Reply:
    text: str
    tool_call: dict | None
    usage: Usage
    stop_reason: str
    raw_id: str = ""
    extra: dict = field(default_factory=dict)


def missing_keys(providers: set[str]) -> list[str]:
    return [KEY_ENV[p] for p in sorted(providers) if p in KEY_ENV and not os.environ.get(KEY_ENV[p])]


def _image_b64(path: Path) -> str:
    return base64.standard_b64encode(path.read_bytes()).decode("ascii")


class Anthropic:
    def __init__(self) -> None:
        import anthropic
        self.client = anthropic.Anthropic(max_retries=4)

    def send(self, api_model: str, system: str, turns: list[dict], images: list[Path], tools: list[dict] | None,
             cache_system: bool) -> Reply:
        system_block = {"type": "text", "text": system}
        if cache_system:
            system_block["cache_control"] = {"type": "ephemeral"}
        messages = []
        for index, turn in enumerate(turns):
            if index == 0 and images:
                content = [{"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": _image_b64(p)}} for p in images]
                content.append({"type": "text", "text": turn["text"]})
                messages.append({"role": turn["role"], "content": content})
            else:
                messages.append({"role": turn["role"], "content": turn["text"]})
        kwargs = {}
        if tools:
            kwargs["tools"] = [{"name": t["name"], "description": t["description"], "input_schema": t["parameters"]} for t in tools]
        response = self.client.messages.create(model=api_model, max_tokens=MAX_OUTPUT_TOKENS, system=[system_block],
                                               messages=messages, **kwargs)
        text = "".join(block.text for block in response.content if block.type == "text")
        call = next(({"tool": b.name, "arguments": dict(b.input)} for b in response.content if b.type == "tool_use"), None)
        u = response.usage
        usage = Usage(input_uncached=u.input_tokens, input_cached=u.cache_read_input_tokens or 0,
                      cache_write=u.cache_creation_input_tokens or 0, output=u.output_tokens)
        return Reply(text, call, usage, response.stop_reason or "", response.id)


class OpenAI:
    def __init__(self) -> None:
        import openai
        self.client = openai.OpenAI(max_retries=4)

    def send(self, api_model: str, system: str, turns: list[dict], images: list[Path], tools: list[dict] | None,
             cache_system: bool) -> Reply:
        items = []
        for index, turn in enumerate(turns):
            kind = "input_text" if turn["role"] == "user" else "output_text"
            content = [{"type": kind, "text": turn["text"]}]
            if index == 0 and images:
                content = [{"type": "input_image", "image_url": f"data:image/png;base64,{_image_b64(p)}"} for p in images] + content
            items.append({"role": turn["role"], "content": content})
        kwargs = {}
        if tools:
            kwargs["tools"] = [{"type": "function", "name": t["name"], "description": t["description"], "parameters": t["parameters"]} for t in tools]
        response = self.client.responses.create(model=api_model, instructions=system, input=items,
                                                max_output_tokens=MAX_OUTPUT_TOKENS, **kwargs)
        call = None
        for item in response.output:
            if item.type == "function_call":
                call = {"tool": item.name, "arguments": json.loads(item.arguments or "{}")}
                break
        u = response.usage
        cached = getattr(u.input_tokens_details, "cached_tokens", 0) or 0
        reasoning = getattr(u.output_tokens_details, "reasoning_tokens", 0) or 0
        usage = Usage(input_uncached=u.input_tokens - cached, input_cached=cached, output=u.output_tokens, reasoning=reasoning)
        return Reply(response.output_text or "", call, usage, response.status or "", response.id)


class Gemini:
    def __init__(self) -> None:
        from google import genai
        self.genai = genai
        self.client = genai.Client()

    def send(self, api_model: str, system: str, turns: list[dict], images: list[Path], tools: list[dict] | None,
             cache_system: bool) -> Reply:
        types = self.genai.types
        contents = []
        for index, turn in enumerate(turns):
            parts = [types.Part.from_text(text=turn["text"])]
            if index == 0 and images:
                parts = [types.Part.from_bytes(data=p.read_bytes(), mime_type="image/png") for p in images] + parts
            contents.append(types.Content(role="user" if turn["role"] == "user" else "model", parts=parts))
        config = {"system_instruction": system, "max_output_tokens": MAX_OUTPUT_TOKENS}
        if tools:
            config["tools"] = [types.Tool(function_declarations=[
                types.FunctionDeclaration(name=t["name"], description=t["description"], parameters_json_schema=t["parameters"]) for t in tools])]
            config["automatic_function_calling"] = types.AutomaticFunctionCallingConfig(disable=True)
        response = self.client.models.generate_content(model=api_model, contents=contents, config=types.GenerateContentConfig(**config))
        calls = response.function_calls or []
        call = {"tool": calls[0].name, "arguments": dict(calls[0].args or {})} if calls else None
        m = response.usage_metadata
        cached = m.cached_content_token_count or 0
        thoughts = m.thoughts_token_count or 0
        usage = Usage(input_uncached=(m.prompt_token_count or 0) - cached, input_cached=cached,
                      output=(m.candidates_token_count or 0) + thoughts, reasoning=thoughts)
        finish = str(response.candidates[0].finish_reason) if response.candidates else ""
        text = "" if calls else (response.text or "")
        return Reply(text, call, usage, finish, response.response_id or "")


class DeepSeek:
    """DeepSeek documents its API as OpenAI-compatible and points to the OpenAI SDK with its own base URL."""

    def __init__(self) -> None:
        import openai
        self.client = openai.OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com", max_retries=4)

    def send(self, api_model: str, system: str, turns: list[dict], images: list[Path], tools: list[dict] | None,
             cache_system: bool) -> Reply:
        if images:
            raise ValueError("DeepSeek models in the roster take no image input")
        messages = [{"role": "system", "content": system}] + [{"role": t["role"], "content": t["text"]} for t in turns]
        kwargs = {}
        if tools:
            kwargs["tools"] = [{"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["parameters"]}} for t in tools]
        response = self.client.chat.completions.create(model=api_model, messages=messages, max_tokens=MAX_OUTPUT_TOKENS, **kwargs)
        choice = response.choices[0]
        call = None
        if choice.message.tool_calls:
            fn = choice.message.tool_calls[0].function
            call = {"tool": fn.name, "arguments": json.loads(fn.arguments or "{}")}
        u = response.usage
        hit = getattr(u, "prompt_cache_hit_tokens", 0) or 0
        details = getattr(u, "completion_tokens_details", None)
        reasoning = getattr(details, "reasoning_tokens", 0) or 0 if details else 0
        usage = Usage(input_uncached=u.prompt_tokens - hit, input_cached=hit, output=u.completion_tokens, reasoning=reasoning)
        return Reply(choice.message.content or "", call, usage, choice.finish_reason or "", response.id)


ADAPTERS = {"anthropic": Anthropic, "openai": OpenAI, "google-gemini": Gemini, "deepseek": DeepSeek}
