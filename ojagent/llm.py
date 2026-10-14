"""Thin LLM interface so the pipeline doesn't depend on one vendor SDK.

Any OpenAI-compatible endpoint works: OpenAI, OpenRouter (Claude, GPT, ...), or a
local server such as Ollama or vLLM.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from openai import OpenAI


@dataclass
class Turn:
    content: str | None
    input_tokens: int = 0
    output_tokens: int = 0


class LLM(Protocol):
    model: str

    def complete(self, messages: list[dict]) -> Turn: ...


class OpenAICompatibleLLM:
    def __init__(self, model: str, api_key: str, base_url: str | None = None, temperature: float = 0.2):
        self.model = model
        self.temperature = temperature
        self.client = OpenAI(api_key=api_key, base_url=base_url, max_retries=3, timeout=120)

    def complete(self, messages: list[dict]) -> Turn:
        resp = self.client.chat.completions.create(
            model=self.model, messages=messages, temperature=self.temperature
        )
        if not resp.choices:  # some free providers return an empty body under load
            raise RuntimeError(f"{self.model} returned no choices")
        usage = resp.usage
        return Turn(
            content=resp.choices[0].message.content,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
        )
