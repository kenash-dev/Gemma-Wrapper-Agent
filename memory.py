"""Conversation memory with automatic compression for small context windows."""

from __future__ import annotations

from config import AGENT_CONTEXT_BUDGET


def _estimate_tokens(text: str) -> int:
    """Rough approximation: 1 token ≈ 4 chars."""
    return len(text) // 4


class Memory:
    """Manages conversation history and a working scratchpad."""

    def __init__(self, context_budget: int = AGENT_CONTEXT_BUDGET):
        self.conversation: list[dict] = []  # full history
        self.working_memory: dict[str, str] = {}  # key-value scratchpad
        self.summary: str = ""  # compressed summary of older turns
        self.context_budget = context_budget

    # ---- mutations --------------------------------------------------------

    def add_user_message(self, content: str) -> None:
        self.conversation.append({"role": "user", "content": content})

    def add_assistant_turn(self, raw_text: str) -> None:
        self.conversation.append({"role": "assistant", "content": raw_text})

    def add_observation(self, tool_name: str, result: str) -> None:
        # Truncate very long observations
        if _estimate_tokens(result) > 1500:
            result = result[: 1500 * 4] + "\n... (truncated)"
        self.conversation.append({
            "role": "user",
            "content": f"OBSERVATION ({tool_name}):\n{result}",
        })

    def set_scratch(self, key: str, value: str) -> None:
        self.working_memory[key] = value

    def clear(self) -> None:
        self.conversation.clear()
        self.working_memory.clear()
        self.summary = ""

    # ---- retrieval --------------------------------------------------------

    def get_messages(self) -> list[dict]:
        """Return messages that fit within the token budget.

        Strategy: keep the system-prompt placeholder + recent turns.
        If total is too big, compress older turns into a summary first.
        """
        self._maybe_compress()

        messages: list[dict] = []

        # Inject compressed summary if present
        if self.summary:
            messages.append({
                "role": "user",
                "content": f"[Summary of earlier conversation]\n{self.summary}",
            })

        # Inject working memory if present
        if self.working_memory:
            scratch = "\n".join(f"- {k}: {v}" for k, v in self.working_memory.items())
            messages.append({
                "role": "user",
                "content": f"[Working memory]\n{scratch}",
            })

        messages.extend(self.conversation)
        return messages

    # ---- compression ------------------------------------------------------

    def _maybe_compress(self) -> None:
        """If conversation exceeds budget, fold the oldest turns into a summary."""
        total = sum(_estimate_tokens(m["content"]) for m in self.conversation)
        if total <= self.context_budget:
            return

        # Keep removing the oldest pair of turns until we fit
        compressed_parts: list[str] = []
        while total > self.context_budget and len(self.conversation) > 2:
            old = self.conversation.pop(0)
            total -= _estimate_tokens(old["content"])
            role = old["role"]
            text = old["content"]
            # Summarise: keep first 200 chars
            short = text[:200] + ("..." if len(text) > 200 else "")
            compressed_parts.append(f"[{role}] {short}")

        if compressed_parts:
            new_summary = "\n".join(compressed_parts)
            if self.summary:
                self.summary += "\n" + new_summary
            else:
                self.summary = new_summary
            # Keep summary itself bounded
            if _estimate_tokens(self.summary) > 1500:
                self.summary = self.summary[-(1500 * 4):]
