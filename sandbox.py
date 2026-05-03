from __future__ import annotations

import os
import re

from config import AGENT_WORKSPACE, AGENT_CONFIRM_WRITES

# When running in desktop GUI mode, confirmations are handled by the UI layer.
# Set this to True to skip CLI-based confirm_action() prompts.
GUI_MODE = False

# ---------------------------------------------------------------------------
# Command safety
# ---------------------------------------------------------------------------

BLOCKED_COMMANDS = [
    r"\brm\s+-rf\s+/",
    r"\bsudo\b",
    r"\bmkfs\b",
    r"\bformat\b",
    r"\bdd\s+",
    r":\(\)\s*\{",          # fork bomb
    r"\bshutdown\b",
    r"\breboot\b",
    r"\bpasswd\b",
    r"\bchmod\s+777\b",
    r"\bcurl\b.*\|\s*bash",  # pipe-to-shell
    r"\bwget\b.*\|\s*bash",
]

DESTRUCTIVE_PATTERNS = [
    r"\brm\b",
    r"\bdel\b",
    r"\bgit\s+push\b",
    r"\bgit\s+reset\s+--hard\b",
    r"\bpip\s+install\b",
    r"\bnpm\s+install\b",
    r"\bdrop\s+table\b",
    r"\btruncate\b",
]


def validate_command(command: str) -> tuple[bool, str]:
    """Check a shell command against safety rules.

    Returns (allowed, reason).
    """
    for pattern in BLOCKED_COMMANDS:
        if re.search(pattern, command, re.IGNORECASE):
            return False, f"Blocked: command matches dangerous pattern ({pattern})"
    return True, ""


def requires_confirmation(command: str) -> bool:
    """Return True if the command should be confirmed by the user."""
    if not AGENT_CONFIRM_WRITES:
        return False
    for pattern in DESTRUCTIVE_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return True
    return False


# ---------------------------------------------------------------------------
# Path safety
# ---------------------------------------------------------------------------

def validate_path(path: str) -> tuple[bool, str]:
    """Ensure the path is inside the allowed workspace."""
    resolved = os.path.abspath(path)
    workspace = os.path.abspath(AGENT_WORKSPACE)
    if not resolved.startswith(workspace):
        return False, f"Path '{resolved}' is outside the workspace '{workspace}'"
    return True, ""


def safe_resolve(path: str) -> str:
    """Resolve a path relative to the workspace. Raises ValueError if outside."""
    if os.path.isabs(path):
        resolved = os.path.abspath(path)
    else:
        resolved = os.path.abspath(os.path.join(AGENT_WORKSPACE, path))

    workspace = os.path.abspath(AGENT_WORKSPACE)
    if not resolved.startswith(workspace):
        raise ValueError(f"Path '{resolved}' is outside the workspace '{workspace}'")
    return resolved


# ---------------------------------------------------------------------------
# User confirmation helper
# ---------------------------------------------------------------------------

def confirm_action(description: str) -> bool:
    """Ask the user to confirm a potentially destructive action."""
    if GUI_MODE:
        # In desktop mode, confirmations are handled by the UI layer before dispatch
        return True
    from rich.console import Console
    console = Console()
    console.print(f"\n[bold yellow]⚠  Confirmation required:[/] {description}")
    answer = input("Proceed? [y/N] ").strip().lower()
    return answer in ("y", "yes")
