"""Background worker that runs the agent loop in a thread and posts UI events."""

from __future__ import annotations

import os
import re
import json
import queue
import threading
from dataclasses import dataclass, field
from typing import Any

from llm_client import LLMClient
from memory import Memory
from tool_registry import generate_tool_descriptions, dispatch_tool
import config

# ── Event types sent from worker → UI ──────────────────────────────

@dataclass
class AgentEvent:
    kind: str            # thought | action | observation | answer | error | status | confirm
    text: str = ""
    data: dict = field(default_factory=dict)


# ── Regex for parsing model output ──────────────────────────────────

_RE_THOUGHT = re.compile(r"THOUGHT:\s*(.+?)(?=\nACTION:|\nANSWER:|\Z)", re.DOTALL)
_RE_ACTION = re.compile(r"ACTION:\s*(\S+)")
_RE_ACTION_INPUT = re.compile(r"ACTION_INPUT:\s*(.+?)(?=\n(?:THOUGHT|ACTION|ANSWER):|\Z)", re.DOTALL)
_RE_ANSWER = re.compile(r"ANSWER:\s*(.+)", re.DOTALL)

_SYSTEM_PROMPT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts", "system.txt")

_RETRY_HINT = (
    "\n\nYour previous response could not be parsed. "
    "Please respond in the correct format:\n"
    "THOUGHT: <reasoning>\nACTION: <tool_name>\n"
    'ACTION_INPUT: {"param": "value"}\n\n'
    "Or if done:\nTHOUGHT: <summary>\nANSWER: <response>"
)


def _load_system_prompt() -> str:
    with open(_SYSTEM_PROMPT_PATH, "r", encoding="utf-8") as f:
        template = f.read()
    return template.replace("{tool_descriptions}", generate_tool_descriptions())


def _parse_response(text: str) -> dict:
    result: dict = {"thought": None, "action": None, "action_input": None, "answer": None}
    m = _RE_THOUGHT.search(text)
    if m:
        result["thought"] = m.group(1).strip()
    m = _RE_ANSWER.search(text)
    if m:
        result["answer"] = m.group(1).strip()
        return result
    m = _RE_ACTION.search(text)
    if m:
        result["action"] = m.group(1).strip()
    m = _RE_ACTION_INPUT.search(text)
    if m:
        raw = m.group(1).strip()
        raw = re.sub(r"^```\w*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        result["action_input"] = raw.strip()
    return result


class AgentWorker:
    """Runs the agent loop on a background thread, posting AgentEvents to a queue."""

    def __init__(self, event_queue: queue.Queue):
        self.event_queue = event_queue
        self.llm: LLMClient | None = None
        self.memory = Memory()
        self._thread: threading.Thread | None = None
        self._stop_flag = threading.Event()
        self._confirm_result: threading.Event = threading.Event()
        self._confirm_answer: bool = False

    # ── lifecycle ───────────────────────────────────────────────────

    def connect(self, base_url: str, model: str) -> None:
        self.llm = LLMClient(base_url=base_url, model=model)
        self._post(AgentEvent("status", f"Connected to {model} at {base_url}"))

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def stop(self) -> None:
        self._stop_flag.set()
        # Unblock any pending confirmation wait
        self._confirm_result.set()

    def clear(self) -> None:
        self.memory.clear()
        self._post(AgentEvent("status", "Conversation cleared"))

    # ── confirmation bridge (called from UI thread) ─────────────────

    def provide_confirmation(self, accepted: bool) -> None:
        self._confirm_answer = accepted
        self._confirm_result.set()

    # ── send a user message ─────────────────────────────────────────

    def send_message(self, text: str) -> None:
        if not self.llm:
            self._post(AgentEvent("error", "Not connected. Open Settings to configure the endpoint."))
            return
        if self.is_running():
            self._post(AgentEvent("error", "Agent is already running. Wait or press Stop."))
            return

        self._stop_flag.clear()
        self._thread = threading.Thread(target=self._run_loop, args=(text,), daemon=True)
        self._thread.start()

    # ── the actual ReAct loop ───────────────────────────────────────

    def _run_loop(self, user_message: str) -> None:
        self.memory.add_user_message(user_message)
        system_prompt = _load_system_prompt()
        max_iter = config.AGENT_MAX_ITERATIONS

        for iteration in range(max_iter):
            if self._stop_flag.is_set():
                self._post(AgentEvent("status", "Stopped by user"))
                return

            self._post(AgentEvent("status", f"Thinking... (step {iteration + 1}/{max_iter})"))

            messages = [{"role": "system", "content": system_prompt}] + self.memory.get_messages()

            try:
                raw = self.llm.chat(messages)
            except Exception as exc:
                self._post(AgentEvent("error", f"LLM error: {exc}"))
                return

            parsed = _parse_response(raw)

            # Thought
            if parsed["thought"]:
                self._post(AgentEvent("thought", parsed["thought"]))

            # Answer → done
            if parsed["answer"]:
                self.memory.add_assistant_turn(raw)
                self._post(AgentEvent("answer", parsed["answer"]))
                self._post(AgentEvent("status", "Done"))
                return

            # Action
            if parsed["action"] and parsed["action_input"] is not None:
                action_name = parsed["action"]
                action_input = parsed["action_input"]

                self._post(AgentEvent("action", action_name, {"input": action_input}))
                self.memory.add_assistant_turn(raw)

                # Check if we need user confirmation for writes
                if self._needs_confirmation(action_name, action_input):
                    self._post(AgentEvent("confirm",
                        f"Tool '{action_name}' wants to modify your system. Allow?",
                        {"action": action_name, "input": action_input}))

                    self._confirm_result.clear()
                    self._confirm_result.wait()  # blocks until UI responds

                    if self._stop_flag.is_set():
                        return
                    if not self._confirm_answer:
                        observation = "CANCELLED by user."
                        self._post(AgentEvent("observation", observation))
                        self.memory.add_observation(action_name, observation)
                        continue

                # Dispatch tool (bypass sandbox confirm since we handle it above)
                observation = dispatch_tool(action_name, action_input)
                self._post(AgentEvent("observation", observation))
                self.memory.add_observation(action_name, observation)
                continue

            # Malformed → retry
            self._post(AgentEvent("status", "Could not parse response, retrying..."))
            self.memory.add_assistant_turn(raw)
            self.memory.add_user_message(_RETRY_HINT)

        self._post(AgentEvent("error", f"Max iterations ({max_iter}) reached. Agent stopped."))
        self._post(AgentEvent("status", "Max iterations reached"))

    # ── helpers ─────────────────────────────────────────────────────

    def _post(self, event: AgentEvent) -> None:
        self.event_queue.put(event)

    @staticmethod
    def _needs_confirmation(action_name: str, action_input: str) -> bool:
        if not config.AGENT_CONFIRM_WRITES:
            return False
        if action_name in ("write_file", "edit_file"):
            return True
        if action_name == "run_command":
            from sandbox import requires_confirmation
            try:
                args = json.loads(action_input)
                return requires_confirmation(args.get("command", ""))
            except (json.JSONDecodeError, KeyError):
                return False
        return False
