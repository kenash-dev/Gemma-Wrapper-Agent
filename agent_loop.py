"""Core ReAct agent loop: THOUGHT → ACTION → OBSERVATION → ... → ANSWER."""

from __future__ import annotations

import os
import re
import json

from rich.console import Console
from rich.panel import Panel

from llm_client import LLMClient
from memory import Memory
from tool_registry import generate_tool_descriptions, dispatch_tool, get_tool
from config import AGENT_MAX_ITERATIONS

console = Console()

_SYSTEM_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "prompts", "system.txt")

# ---- regex patterns for parsing model output --------------------------------

_RE_THOUGHT = re.compile(r"THOUGHT:\s*(.+?)(?=\nACTION:|\nANSWER:|\Z)", re.DOTALL)
_RE_ACTION = re.compile(r"ACTION:\s*(\S+)")
_RE_ACTION_INPUT = re.compile(r"ACTION_INPUT:\s*(.+?)(?=\n(?:THOUGHT|ACTION|ANSWER):|\Z)", re.DOTALL)
_RE_ANSWER = re.compile(r"ANSWER:\s*(.+)", re.DOTALL)


def _load_system_prompt() -> str:
    with open(_SYSTEM_PROMPT_PATH, "r", encoding="utf-8") as f:
        template = f.read()
    return template.replace("{tool_descriptions}", generate_tool_descriptions())


def _parse_response(text: str) -> dict:
    """Extract THOUGHT, ACTION, ACTION_INPUT, ANSWER from model output."""
    result: dict = {"thought": None, "action": None, "action_input": None, "answer": None, "raw": text}

    m = _RE_THOUGHT.search(text)
    if m:
        result["thought"] = m.group(1).strip()

    m = _RE_ANSWER.search(text)
    if m:
        result["answer"] = m.group(1).strip()
        return result  # answer takes priority — loop ends

    m = _RE_ACTION.search(text)
    if m:
        result["action"] = m.group(1).strip()

    m = _RE_ACTION_INPUT.search(text)
    if m:
        raw_input = m.group(1).strip()
        # Strip accidental markdown fencing
        raw_input = re.sub(r"^```\w*\n?", "", raw_input)
        raw_input = re.sub(r"\n?```$", "", raw_input)
        result["action_input"] = raw_input.strip()

    return result


def _display_thought(thought: str) -> None:
    console.print(f"[dim italic]💭 {thought}[/]")


def _display_action(action: str, action_input: str) -> None:
    console.print(Panel(
        f"[yellow bold]{action}[/]\n[white]{action_input}[/]",
        title="🔧 Tool Call",
        border_style="yellow",
    ))


def _display_observation(text: str) -> None:
    # Truncate for display (full version stays in memory)
    display_text = text if len(text) < 1500 else text[:1500] + "\n... (truncated in display)"
    console.print(Panel(display_text, title="📋 Observation", border_style="blue"))


def _display_answer(answer: str) -> None:
    console.print()
    console.print(Panel(answer, title="✅ Agent", border_style="green"))


# ---- main loop --------------------------------------------------------------

_RETRY_HINT = (
    "\n\nYour previous response could not be parsed. "
    "Please respond in the correct format:\n"
    "THOUGHT: <reasoning>\n"
    "ACTION: <tool_name>\n"
    'ACTION_INPUT: {"param": "value"}\n\n'
    "Or if done:\n"
    "THOUGHT: <summary>\n"
    "ANSWER: <response>"
)


def run_agent_loop(llm: LLMClient, memory: Memory, user_message: str) -> str | None:
    """Run the ReAct loop for a single user turn. Returns the agent's final answer."""

    memory.add_user_message(user_message)
    system_prompt = _load_system_prompt()

    for iteration in range(AGENT_MAX_ITERATIONS):
        messages = [{"role": "system", "content": system_prompt}] + memory.get_messages()

        with console.status("[bold cyan]Thinking...[/]", spinner="dots"):
            raw = llm.chat(messages)

        parsed = _parse_response(raw)

        # Show thought
        if parsed["thought"]:
            _display_thought(parsed["thought"])

        # Final answer?
        if parsed["answer"]:
            memory.add_assistant_turn(raw)
            _display_answer(parsed["answer"])
            return parsed["answer"]

        # Valid action?
        if parsed["action"] and parsed["action_input"] is not None:
            action_name = parsed["action"]
            action_input = parsed["action_input"]

            _display_action(action_name, action_input)
            memory.add_assistant_turn(raw)

            # Dispatch
            observation = dispatch_tool(action_name, action_input)
            _display_observation(observation)
            memory.add_observation(action_name, observation)
            continue

        # Malformed output — retry once
        console.print("[dim red]⚠ Could not parse response. Nudging model...[/]")
        memory.add_assistant_turn(raw)
        memory.add_user_message(_RETRY_HINT)
        continue

    # Max iterations reached
    console.print("[bold red]⛔ Max iterations reached. Stopping agent loop.[/]")
    return None
