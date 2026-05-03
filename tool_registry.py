from __future__ import annotations

import json
import inspect
from typing import Callable, Any


class ToolSpec:
    """Metadata for a registered tool."""

    def __init__(self, name: str, description: str, parameters: dict[str, dict], fn: Callable):
        self.name = name
        self.description = description
        self.parameters = parameters  # {param_name: {type, description}}
        self.fn = fn

    def params_json_schema(self) -> str:
        """Human-readable parameter docs for the LLM prompt."""
        lines = []
        for pname, pinfo in self.parameters.items():
            ptype = pinfo.get("type", "string")
            pdesc = pinfo.get("description", "")
            lines.append(f"  - {pname} ({ptype}): {pdesc}")
        return "\n".join(lines) if lines else "  (no parameters)"


# Global registry ----------------------------------------------------------

_TOOLS: dict[str, ToolSpec] = {}


def tool(name: str, description: str, parameters: dict[str, dict] | None = None):
    """Decorator to register a function as an agent tool."""

    def decorator(fn: Callable) -> Callable:
        _TOOLS[name] = ToolSpec(
            name=name,
            description=description,
            parameters=parameters or {},
            fn=fn,
        )
        return fn

    return decorator


def get_tool(name: str) -> ToolSpec | None:
    return _TOOLS.get(name)


def list_tools() -> list[ToolSpec]:
    return list(_TOOLS.values())


def generate_tool_descriptions() -> str:
    """Produce the tool block injected into the system prompt."""
    parts: list[str] = []
    for t in _TOOLS.values():
        parts.append(
            f"### {t.name}\n{t.description}\nParameters:\n{t.params_json_schema()}"
        )
    return "\n\n".join(parts)


def dispatch_tool(name: str, args_json: str) -> str:
    """Parse JSON args, call the tool, return result as string."""
    spec = _TOOLS.get(name)
    if spec is None:
        return f"ERROR: Unknown tool '{name}'. Available tools: {', '.join(_TOOLS.keys())}"

    try:
        args: dict[str, Any] = json.loads(args_json) if args_json.strip() else {}
    except json.JSONDecodeError as exc:
        return f"ERROR: Invalid JSON for tool arguments: {exc}"

    # Validate required params
    sig = inspect.signature(spec.fn)
    for pname, param in sig.parameters.items():
        if param.default is inspect.Parameter.empty and pname not in args:
            return f"ERROR: Missing required parameter '{pname}' for tool '{name}'"

    try:
        result = spec.fn(**args)
        if result is None:
            return "(no output)"
        return str(result)
    except Exception as exc:
        return f"ERROR executing {name}: {type(exc).__name__}: {exc}"
