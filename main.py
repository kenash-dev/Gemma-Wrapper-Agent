#!/usr/bin/env python3
"""Gemma Agent — Local AI agent powered by Google Gemma in Docker.

Usage:
    python main.py                              # interactive REPL
    python main.py "create a hello world app"   # single task
    python main.py --workspace ./my-project     # restrict to a directory
"""

from __future__ import annotations

import argparse
import sys

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

# ---- Import tools to register them with the registry ----------------------
import tools.file_ops       # noqa: F401
import tools.shell          # noqa: F401
import tools.code_exec      # noqa: F401
import tools.web_search     # noqa: F401
# import tools.knowledge    # Uncomment if you have chromadb + sentence-transformers

from llm_client import LLMClient
from memory import Memory
from planner import Planner
from agent_loop import run_agent_loop
from tool_registry import list_tools
import config

console = Console()

BANNER = """
[bold cyan]╔══════════════════════════════════════════╗
║         🤖  Gemma Agent  v0.1.0         ║
║   Local AI Agent · Powered by Gemma     ║
╚══════════════════════════════════════════╝[/]
"""

HELP_TEXT = """[dim]Commands:
  /plan      — Show the current task plan
  /memory    — Show working memory
  /tools     — List available tools
  /clear     — Reset conversation
  /config    — Show current configuration
  /quit      — Exit the agent
  
Type any message to give the agent a task.[/]
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gemma Agent — local AI agent")
    parser.add_argument("task", nargs="?", default=None, help="Single task to execute (optional)")
    parser.add_argument("--workspace", default=".", help="Workspace directory to restrict file access")
    parser.add_argument("--model", default=None, help="Override model name")
    parser.add_argument("--base-url", default=None, help="Override Gemma API base URL")
    parser.add_argument("--no-confirm", action="store_true", help="Skip confirmation prompts")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Apply overrides
    if args.workspace:
        import os
        config.AGENT_WORKSPACE = os.path.abspath(args.workspace)
    if args.model:
        config.GEMMA_MODEL = args.model
    if args.base_url:
        config.GEMMA_BASE_URL = args.base_url
    if args.no_confirm:
        config.AGENT_CONFIRM_WRITES = False

    # Initialise components
    llm = LLMClient(base_url=config.GEMMA_BASE_URL, model=config.GEMMA_MODEL)
    memory = Memory()
    planner = Planner(llm)

    console.print(BANNER)
    console.print(f"[dim]Model:     {config.GEMMA_MODEL}[/]")
    console.print(f"[dim]Endpoint:  {config.GEMMA_BASE_URL}[/]")
    console.print(f"[dim]Workspace: {config.AGENT_WORKSPACE}[/]")
    console.print()

    # Single-task mode
    if args.task:
        console.print(f"[bold]Task:[/] {args.task}\n")
        run_agent_loop(llm, memory, args.task)
        return

    # Interactive REPL
    console.print(HELP_TEXT)

    while True:
        try:
            user_input = console.input("[bold green]You>[/] ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye![/]")
            break

        if not user_input:
            continue

        # Slash commands
        if user_input.startswith("/"):
            cmd = user_input.lower().split()[0]

            if cmd in ("/quit", "/exit", "/q"):
                console.print("[dim]Goodbye![/]")
                break

            elif cmd == "/clear":
                memory.clear()
                console.print("[dim]Conversation cleared.[/]")
                continue

            elif cmd == "/tools":
                for t in list_tools():
                    console.print(f"  [yellow]{t.name}[/] — {t.description}")
                continue

            elif cmd == "/memory":
                if memory.working_memory:
                    for k, v in memory.working_memory.items():
                        console.print(f"  [cyan]{k}:[/] {v}")
                else:
                    console.print("[dim]  (empty)[/]")
                if memory.summary:
                    console.print(f"\n[dim]Summary: {memory.summary[:300]}...[/]")
                continue

            elif cmd == "/plan":
                console.print(planner.format_status())
                continue

            elif cmd == "/config":
                console.print(f"  Model:       {config.GEMMA_MODEL}")
                console.print(f"  Base URL:    {config.GEMMA_BASE_URL}")
                console.print(f"  Workspace:   {config.AGENT_WORKSPACE}")
                console.print(f"  Max Iters:   {config.AGENT_MAX_ITERATIONS}")
                console.print(f"  Confirm:     {config.AGENT_CONFIRM_WRITES}")
                console.print(f"  Temperature: {config.AGENT_TEMPERATURE}")
                continue

            elif cmd == "/help":
                console.print(HELP_TEXT)
                continue

            else:
                console.print(f"[dim]Unknown command: {cmd}. Type /help[/]")
                continue

        # Run the agent
        try:
            run_agent_loop(llm, memory, user_input)
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted. Agent stopped.[/]")
        except Exception as exc:
            console.print(f"[bold red]Error: {exc}[/]")


if __name__ == "__main__":
    main()
