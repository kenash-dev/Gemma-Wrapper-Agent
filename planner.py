"""Task planner: decompose complex goals into numbered steps."""

from __future__ import annotations

import os
from llm_client import LLMClient

_PLANNER_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "prompts", "planner.txt")


def _load_planner_prompt() -> str:
    with open(_PLANNER_PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()


class Planner:
    def __init__(self, llm: LLMClient):
        self.llm = llm
        self.steps: list[str] = []
        self.completed: list[str] = []

    def create_plan(self, task: str) -> list[str]:
        """Ask the LLM to decompose a task into concrete steps."""
        system = _load_planner_prompt()
        response = self.llm.chat(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": f"Task: {task}"},
            ],
            temperature=0.2,
            max_tokens=1024,
        )
        self.steps = self._parse_steps(response)
        self.completed = []
        return self.steps

    def mark_done(self, step: str) -> None:
        if step in self.steps:
            self.steps.remove(step)
            self.completed.append(step)

    def get_current_step(self) -> str | None:
        return self.steps[0] if self.steps else None

    def is_complete(self) -> bool:
        return len(self.steps) == 0

    def format_status(self) -> str:
        parts: list[str] = []
        for s in self.completed:
            parts.append(f"  [done] {s}")
        for i, s in enumerate(self.steps):
            marker = ">>>" if i == 0 else "   "
            parts.append(f"  {marker} {s}")
        return "\n".join(parts) if parts else "(no plan)"

    @staticmethod
    def _parse_steps(text: str) -> list[str]:
        """Extract numbered or bulleted steps from LLM output."""
        steps: list[str] = []
        for line in text.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            # Strip numbering: "1. ", "1) ", "- ", "* "
            for prefix_len in range(1, 5):
                if line[:prefix_len].rstrip(".)- *").isdigit() or line[0] in "-*":
                    cleaned = line.lstrip("0123456789.)- *").strip()
                    if cleaned:
                        steps.append(cleaned)
                    break
            else:
                # No numbering detected — take the line as-is if short enough
                if len(line) < 200:
                    steps.append(line)
        return steps
