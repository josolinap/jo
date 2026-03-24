"""Runtime Tools Loader - Auto-discover and register runtime tools.

This module loads runtime tools created by Jo at runtime and registers
them in the main ToolRegistry.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, List, Optional

from ouroboros.tools.registry import ToolEntry, ToolContext

log = logging.getLogger(__name__)

# Cache for loaded runtime tools
_runtime_tools_cache: dict = {}


def _get_runtime_tools_dir() -> Path:
    """Get the runtime tools directory."""
    import os

    return Path(os.environ.get("REPO_DIR", ".")) / "runtime_tools"


def _load_runtime_tool_spec(tool_path: Path) -> Optional[dict]:
    """Load a runtime tool spec from JSON file."""
    try:
        return json.loads(tool_path.read_text(encoding="utf-8"))
    except Exception as e:
        log.debug(f"Failed to load runtime tool spec {tool_path}: {e}")
        return None


def _create_tool_handler(spec: dict) -> Any:
    """Create a handler function for a runtime tool."""
    tool_name = spec.get("name", "")
    code = spec.get("code", "")

    def handler(ctx: ToolContext, **kwargs: Any) -> str:
        """Execute the runtime tool."""
        try:
            # Create namespace with safe modules
            namespace: dict = {}
            safe_modules = [
                "json",
                "re",
                "os",
                "pathlib",
                "datetime",
                "time",
                "math",
                "collections",
                "itertools",
                "functools",
                "typing",
                "dataclasses",
                "hashlib",
                "base64",
                "urllib",
                "string",
                "textwrap",
                "io",
                "csv",
                "html",
                "xml",
                "unicodedata",
                "difflib",
            ]

            for module_name in safe_modules:
                try:
                    module = __import__(module_name)
                    namespace[module_name] = module
                except ImportError:
                    pass

            # Execute the tool code
            exec(code, namespace)

            # Find the function
            func = namespace.get(tool_name)
            if func and callable(func):
                # Call with kwargs
                return func(**kwargs)

            # Try to find any callable
            for key, value in namespace.items():
                if callable(value) and not key.startswith("_"):
                    return value(**kwargs)

            return f"⚠️ TOOL_ERROR ({tool_name}): No callable function found"

        except Exception as e:
            return f"⚠️ TOOL_ERROR ({tool_name}): {e}"

    return handler


def get_tools() -> List[ToolEntry]:
    """Auto-discover and return runtime tools as ToolEntry objects."""
    runtime_dir = _get_runtime_tools_dir()
    if not runtime_dir.exists():
        return []

    entries = []
    for tool_file in runtime_dir.glob("*.json"):
        try:
            spec = _load_runtime_tool_spec(tool_file)
            if not spec:
                continue

            tool_name = spec.get("name", "")
            if not tool_name:
                continue

            # Skip if already loaded
            if tool_name in _runtime_tools_cache:
                entries.append(_runtime_tools_cache[tool_name])
                continue

            # Create handler
            handler = _create_tool_handler(spec)

            # Create ToolEntry
            entry = ToolEntry(
                name=tool_name,
                schema={
                    "name": tool_name,
                    "description": spec.get("description", "Runtime tool"),
                    "parameters": spec.get("parameters", {}),
                },
                handler=handler,
                is_code_tool=False,
            )

            # Cache and add to entries
            _runtime_tools_cache[tool_name] = entry
            entries.append(entry)
            log.debug(f"Loaded runtime tool: {tool_name}")

        except Exception as e:
            log.warning(f"Failed to load runtime tool {tool_file}: {e}")

    return entries
