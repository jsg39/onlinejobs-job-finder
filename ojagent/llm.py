"""Thin LLM interface so the agent loop doesn't depend on one vendor SDK.

Any OpenAI-compatible endpoint works: OpenAI, OpenRouter (Claude, GPT, ...), or a
local server such as Ollama or vLLM.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from openai import OpenAI


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str  # raw JSON string from the model


@dataclass
class Turn:
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0

    def as_message(self) -> dict:
        msg: dict = {"role": "assistant", "content": self.content or ""}
        if self.tool_calls:
            msg["tool_calls"] = [
                {"id": c.id, "type": "function", "function": {"name": c.name, "arguments": c.arguments}}
                for c in self.tool_calls
            ]
        return msg


class LLM(Protocol):
    model: str

    def complete(self, messages: list[dict], tools: list[dict]) -> Turn: ...


class OpenAICompatibleLLM:
    def __init__(self, model: str, api_key: str, base_url: str | None = None, temperature: float = 0.2):
        self.model = model
        self.temperature = temperature
        self.client = OpenAI(api_key=api_key, base_url=base_url, max_retries=3, timeout=120)

    def complete(self, messages: list[dict], tools: list[dict]) -> Turn:
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
            temperature=self.temperature,
        )
        msg = resp.choices[0].message
        usage = resp.usage
        return Turn(
            content=msg.content,
            tool_calls=[
                ToolCall(c.id, c.function.name, c.function.arguments) for c in msg.tool_calls or []
            ],
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
        )
