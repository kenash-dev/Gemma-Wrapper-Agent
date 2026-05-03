"""Shell command execution tool with sandboxing."""

from __future__ import annotations

import subprocess

from tool_registry import tool
from sandbox import validate_command, requires_confirmation, confirm_action
from config import AGENT_WORKSPACE


@tool(
    name="run_command",
    description="Execute a shell command and return stdout + stderr. Timeout: 30s.",
    parameters={
        "command": {"type": "string", "description": "The shell command to run"},
        "cwd": {"type": "string", "description": "Working directory (default: workspace root)"},
    },
)
def run_command(command: str, cwd: str | None = None) -> str:
    # Safety check
    allowed, reason = validate_command(command)
    if not allowed:
        return f"BLOCKED: {reason}"

    if requires_confirmation(command):
        if not confirm_action(f"Run command: {command}"):
            return "CANCELLED by user."

    work_dir = cwd or AGENT_WORKSPACE

    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=work_dir,
            capture_output=True,
            text=True,
            timeout=30,
        )
        output_parts: list[str] = []
        if result.stdout.strip():
            output_parts.append(result.stdout.strip())
        if result.stderr.strip():
            output_parts.append(f"[stderr]\n{result.stderr.strip()}")
        output_parts.append(f"[exit code: {result.returncode}]")
        return "\n".join(output_parts)
    except subprocess.TimeoutExpired:
        return "ERROR: Command timed out after 30 seconds."
    except Exception as exc:
        return f"ERROR: {type(exc).__name__}: {exc}"
