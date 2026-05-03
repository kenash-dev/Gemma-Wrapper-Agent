from __future__ import annotations

import time
from typing import Iterator

from openai import OpenAI

from config import GEMMA_BASE_URL, GEMMA_MODEL, AGENT_TEMPERATURE, AGENT_MAX_TOKENS


class LLMClient:
    """OpenAI-compatible client pointed at a local Gemma endpoint."""

    def __init__(
        self,
        base_url: str = GEMMA_BASE_URL,
        model: str = GEMMA_MODEL,
    ):
        self.model = model
        self.client = OpenAI(base_url=base_url, api_key="not-needed")

    # ------------------------------------------------------------------
    def chat(
        self,
        messages: list[dict],
        temperature: float = AGENT_TEMPERATURE,
        max_tokens: int = AGENT_MAX_TOKENS,
        stop: list[str] | None = None,
    ) -> str:
        """Blocking chat completion. Returns assistant text."""
        for attempt in range(3):
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stop=stop,
                    timeout=120,
                )
                return resp.choices[0].message.content or ""
            except Exception as exc:
                if attempt == 2:
                    raise
                wait = 2 ** attempt
                time.sleep(wait)
        return ""

    # ------------------------------------------------------------------
    def chat_stream(
        self,
        messages: list[dict],
        temperature: float = AGENT_TEMPERATURE,
        max_tokens: int = AGENT_MAX_TOKENS,
        stop: list[str] | None = None,
    ) -> Iterator[str]:
        """Streaming chat completion. Yields text chunks."""
        stream = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stop=stop,
            stream=True,
            timeout=120,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content
