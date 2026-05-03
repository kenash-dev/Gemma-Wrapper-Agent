"""File-system tools: read, write, edit, list, search, grep."""

from __future__ import annotations

import os
import glob
import re

from tool_registry import tool
from sandbox import safe_resolve, confirm_action
from config import AGENT_CONFIRM_WRITES

MAX_READ_LINES = 500


@tool(
    name="read_file",
    description="Read the contents of a file. Returns up to 500 lines.",
    parameters={
        "path": {"type": "string", "description": "File path (absolute or relative to workspace)"},
    },
)
def read_file(path: str) -> str:
    resolved = safe_resolve(path)
    if not os.path.isfile(resolved):
        return f"ERROR: File not found: {resolved}"
    with open(resolved, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    if len(lines) > MAX_READ_LINES:
        content = "".join(lines[:MAX_READ_LINES])
        return content + f"\n... (truncated, {len(lines)} total lines)"
    return "".join(lines)


@tool(
    name="write_file",
    description="Write content to a file. Creates parent directories if needed. Overwrites existing file.",
    parameters={
        "path": {"type": "string", "description": "File path"},
        "content": {"type": "string", "description": "Full file content to write"},
    },
)
def write_file(path: str, content: str) -> str:
    resolved = safe_resolve(path)
    if AGENT_CONFIRM_WRITES:
        if not confirm_action(f"Write file: {resolved}"):
            return "CANCELLED by user."
    os.makedirs(os.path.dirname(resolved), exist_ok=True)
    with open(resolved, "w", encoding="utf-8") as f:
        f.write(content)
    return f"Written {len(content)} chars to {resolved}"


@tool(
    name="edit_file",
    description="Replace an exact text snippet in a file with new text.",
    parameters={
        "path": {"type": "string", "description": "File path"},
        "old_text": {"type": "string", "description": "Exact text to find (must appear once)"},
        "new_text": {"type": "string", "description": "Replacement text"},
    },
)
def edit_file(path: str, old_text: str, new_text: str) -> str:
    resolved = safe_resolve(path)
    if not os.path.isfile(resolved):
        return f"ERROR: File not found: {resolved}"
    with open(resolved, "r", encoding="utf-8") as f:
        original = f.read()
    count = original.count(old_text)
    if count == 0:
        return "ERROR: old_text not found in the file."
    if count > 1:
        return f"ERROR: old_text found {count} times; must be unique."
    if AGENT_CONFIRM_WRITES:
        if not confirm_action(f"Edit file: {resolved}"):
            return "CANCELLED by user."
    updated = original.replace(old_text, new_text, 1)
    with open(resolved, "w", encoding="utf-8") as f:
        f.write(updated)
    return f"Edited {resolved} (replaced 1 occurrence)."


@tool(
    name="list_directory",
    description="List files and folders in a directory.",
    parameters={
        "path": {"type": "string", "description": "Directory path (default: workspace root)"},
    },
)
def list_directory(path: str = ".") -> str:
    resolved = safe_resolve(path)
    if not os.path.isdir(resolved):
        return f"ERROR: Not a directory: {resolved}"
    entries: list[str] = []
    for entry in sorted(os.listdir(resolved)):
        full = os.path.join(resolved, entry)
        suffix = "/" if os.path.isdir(full) else ""
        entries.append(f"{entry}{suffix}")
    return "\n".join(entries) if entries else "(empty directory)"


@tool(
    name="search_files",
    description="Search for files matching a glob pattern.",
    parameters={
        "pattern": {"type": "string", "description": "Glob pattern (e.g. '**/*.py')"},
        "directory": {"type": "string", "description": "Base directory (default: workspace)"},
    },
)
def search_files(pattern: str, directory: str = ".") -> str:
    resolved = safe_resolve(directory)
    matches = glob.glob(os.path.join(resolved, pattern), recursive=True)
    if not matches:
        return "No files matched."
    # Show relative paths
    results: list[str] = []
    for m in sorted(matches)[:50]:
        results.append(os.path.relpath(m, resolved))
    text = "\n".join(results)
    if len(matches) > 50:
        text += f"\n... ({len(matches)} total matches, showing first 50)"
    return text


@tool(
    name="grep",
    description="Search for a text pattern inside files.",
    parameters={
        "pattern": {"type": "string", "description": "Search pattern"},
        "path": {"type": "string", "description": "File or directory to search"},
        "is_regex": {"type": "boolean", "description": "Treat pattern as regex (default: false)"},
    },
)
def grep(pattern: str, path: str, is_regex: bool = False) -> str:
    resolved = safe_resolve(path)
    results: list[str] = []
    max_results = 30

    if is_regex:
        try:
            compiled = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            return f"ERROR: Invalid regex: {e}"
        match_fn = compiled.search
    else:
        lower_pat = pattern.lower()
        match_fn = lambda line: lower_pat in line.lower()  # noqa: E731

    def _search_file(fpath: str) -> None:
        try:
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                for lineno, line in enumerate(f, 1):
                    if len(results) >= max_results:
                        return
                    if match_fn(line):
                        rel = os.path.relpath(fpath, safe_resolve("."))
                        results.append(f"{rel}:{lineno}: {line.rstrip()}")
        except (OSError, UnicodeDecodeError):
            pass

    if os.path.isfile(resolved):
        _search_file(resolved)
    elif os.path.isdir(resolved):
        for root, _dirs, files in os.walk(resolved):
            for fname in files:
                if len(results) >= max_results:
                    break
                _search_file(os.path.join(root, fname))
    else:
        return f"ERROR: Path not found: {resolved}"

    if not results:
        return "No matches found."
    text = "\n".join(results)
    if len(results) >= max_results:
        text += f"\n... (showing first {max_results} results)"
    return text
