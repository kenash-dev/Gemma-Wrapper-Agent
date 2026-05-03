"""Execute Python code in a sandboxed subprocess."""

from __future__ import annotations

import subprocess
import tempfile
import os

from tool_registry import tool
from config import AGENT_WORKSPACE


@tool(
    name="execute_python",
    description="Run a Python code snippet in a subprocess. Returns stdout, stderr and exit code.",
    parameters={
        "code": {"type": "string", "description": "Python code to execute"},
    },
)
def execute_python(code: str) -> str:
    tmp_dir = tempfile.mkdtemp(prefix="agent_exec_")
    script_path = os.path.join(tmp_dir, "script.py")

    with open(script_path, "w", encoding="utf-8") as f:
        f.write(code)

    try:
        result = subprocess.run(
            ["python", script_path],
            cwd=AGENT_WORKSPACE,
            capture_output=True,
            text=True,
            timeout=30,
        )
        parts: list[str] = []
        if result.stdout.strip():
            parts.append(result.stdout.strip())
        if result.stderr.strip():
            parts.append(f"[stderr]\n{result.stderr.strip()}")
        parts.append(f"[exit code: {result.returncode}]")
        return "\n".join(parts)
    except subprocess.TimeoutExpired:
        return "ERROR: Script timed out after 30 seconds."
    except Exception as exc:
        return f"ERROR: {type(exc).__name__}: {exc}"
    finally:
        try:
            os.remove(script_path)
            os.rmdir(tmp_dir)
        except OSError:
            pass
