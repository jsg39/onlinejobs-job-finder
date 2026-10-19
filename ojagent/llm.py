"""Thin LLM interface so the pipeline doesn't depend on one vendor SDK.

Any OpenAI-compatible endpoint works: OpenAI, OpenRouter (Claude, GPT, ...), or a
local server such as Ollama or vLLM.

Free models are often overloaded, so FallbackLLM moves on to the next model when one
errors or replies empty, and starts from whichever model last worked.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Callable, Protocol

import httpx
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
    def __init__(self, model: str, api_key: str, base_url: str | None = None, temperature: float = 0.2,
                 max_retries: int = 3):
        self.model = model
        self.temperature = temperature
        self.client = OpenAI(api_key=api_key, base_url=base_url, max_retries=max_retries, timeout=120)

    def complete(self, messages: list[dict]) -> Turn:
        resp = self.client.chat.completions.create(
            model=self.model, messages=messages, temperature=self.temperature
        )
        if not resp.choices:  # some free providers return an empty body under load
            raise RuntimeError(f"{self.model} returned no choices")
        if not resp.choices[0].message.content:
            raise RuntimeError(f"{self.model} returned an empty reply")
        usage = resp.usage
        return Turn(
            content=resp.choices[0].message.content,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
        )


# Free models that can't write the JSON this app asks for: music generation, safety classifiers.
_UNSUITABLE = ("lyria", "safety")


def openrouter_free_models(base_url: str) -> list[str]:
    """OpenRouter's current free text models, largest context first; openrouter/free goes last
    because it picks a free model for us, which makes it a good last resort."""
    resp = httpx.get(base_url.rstrip("/") + "/models", timeout=20)
    resp.raise_for_status()
    models = [
        m for m in resp.json()["data"]
        if m["id"].endswith(":free")
        and "text" in m.get("architecture", {}).get("output_modalities", ["text"])
        and not any(word in m["id"] for word in _UNSUITABLE)
    ]
    models.sort(key=lambda m: -(m.get("context_length") or 0))
    return [m["id"] for m in models] + ["openrouter/free"]


class FallbackLLM:
    """Tries each model in turn until one answers. Sticks with the one that worked."""

    def __init__(self, models: list[str], make: Callable[[str], LLM],
                 discover: Callable[[], list[str]] | None = None):
        self.models = list(dict.fromkeys(models))  # dedupe, keep order
        self.make = make
        self.discover = discover  # called once, the first time every listed model fails
        self.current = 0
        self.clients: dict[str, LLM] = {}
        self.lock = threading.Lock()

    @property
    def model(self) -> str:
        return self.models[self.current]

    def _client(self, model: str) -> LLM:
        if model not in self.clients:
            self.clients[model] = self.make(model)
        return self.clients[model]

    def complete(self, messages: list[dict]) -> Turn:
        errors: list[str] = []
        tried: set[str] = set()
        while True:
            with self.lock:
                order = self.models[self.current:] + self.models[:self.current]
            for model in order:
                if model in tried:
                    continue
                tried.add(model)
                try:
                    turn = self._client(model).complete(messages)
                except Exception as e:  # overloaded, rate limited, empty reply, model gone...
                    errors.append(f"{model}: {e}")
                    continue
                with self.lock:
                    self.current = self.models.index(model)
                return turn
            if not self._discover_more():
                raise RuntimeError("Every model failed. " + " | ".join(errors[-5:]))

    def _discover_more(self) -> bool:
        if self.discover is None:
            return False
        discover, self.discover = self.discover, None
        try:
            found = discover()
        except Exception:
            return False
        with self.lock:
            new = [m for m in found if m not in self.models]
            self.models += new
        return bool(new)


def build_llm(model: str, api_key: str, base_url: str | None, fallbacks: list[str] | None) -> LLM:
    """The app's LLM: `model` first, then `fallbacks`. None means "find free ones" on OpenRouter."""
    def make(m: str) -> LLM:
        return OpenAICompatibleLLM(m, api_key, base_url, max_retries=1)  # fail fast, then fall back

    on_openrouter = bool(base_url and "openrouter.ai" in base_url)
    if fallbacks is None and on_openrouter:
        return FallbackLLM([model], make, discover=lambda: openrouter_free_models(base_url))
    if fallbacks:
        return FallbackLLM([model, *fallbacks], make)
    return OpenAICompatibleLLM(model, api_key, base_url)
