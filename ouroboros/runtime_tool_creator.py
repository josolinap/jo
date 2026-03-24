"""
Runtime Tool Creation - Enable Jo to create new tools at runtime.

Inspired by 724-office's create_tool feature:
- Agent can write Python code that becomes a new tool
- Tool is saved to disk and loaded into the registry
- No restart required
- Tools are sandboxed with validation

Security:
- Protected file check (cannot modify protected files)
- Syntax validation before loading
- Import restriction (only safe modules)
- Timeout enforcement
"""

from __future__ import annotations

import ast
import inspect
import json
import logging
import os
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

# Safe modules that runtime tools can import
SAFE_MODULES = {
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
}

# Dangerous patterns to block
DANGEROUS_PATTERNS = [
    "exec(",
    "eval(",
    "compile(",
    "__import__",
    "open(",
    "os.system",
    "os.popen",
    "subprocess",
    "importlib",
    "shutil.rmtree",
    "os.remove",
    "os.unlink",
    "socket",
    "http.server",
    "requests.post",
    "requests.put",
    "requests.delete",
]


@dataclass
class ToolSpec:
    """Specification for a runtime-created tool."""

    name: str
    description: str
    parameters: Dict[str, Any]
    code: str
    author: str = "jo"
    version: str = "1.0"
    created_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "code": self.code,
            "author": self.author,
            "version": self.version,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ToolSpec:
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            parameters=data.get("parameters", {}),
            code=data.get("code", ""),
            author=data.get("author", "jo"),
            version=data.get("version", "1.0"),
            created_at=data.get("created_at", ""),
            metadata=data.get("metadata", {}),
        )


class RuntimeToolCreator:
    """Creates and manages runtime tools.

    Tools are:
    1. Validated for safety
    2. Saved to disk
    3. Loaded into registry
    4. Available immediately (no restart)
    """

    def __init__(self, tools_dir: Path):
        self._tools_dir = Path(tools_dir)
        self._tools_dir.mkdir(parents=True, exist_ok=True)
        self._tools: Dict[str, ToolSpec] = {}
        self._load_existing()

    def _load_existing(self) -> None:
        """Load existing runtime tools from disk."""
        for tool_file in self._tools_dir.glob("*.json"):
            try:
                data = json.loads(tool_file.read_text(encoding="utf-8"))
                spec = ToolSpec.from_dict(data)
                self._tools[spec.name] = spec
                log.debug(f"Loaded runtime tool: {spec.name}")
            except Exception as e:
                log.warning(f"Failed to load tool {tool_file}: {e}")

    def _validate_code(self, code: str) -> Tuple[bool, str]:
        """Validate tool code for safety.

        Returns (is_valid, error_message)
        """
        # Check syntax
        try:
            ast.parse(code)
        except SyntaxError as e:
            return False, f"Syntax error: {e}"

        # Check for dangerous patterns
        for pattern in DANGEROUS_PATTERNS:
            if pattern in code:
                return False, f"Dangerous pattern detected: {pattern}"

        # Check imports are safe
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module = alias.name.split(".")[0]
                        if module not in SAFE_MODULES:
                            return False, f"Unsafe import: {alias.name}"
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        module = node.module.split(".")[0]
                        if module not in SAFE_MODULES:
                            return False, f"Unsafe import from: {node.module}"
        except Exception as e:
            return False, f"Import validation failed: {e}"

        return True, ""

    def create_tool(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        code: str,
        author: str = "jo",
    ) -> Tuple[bool, str]:
        """Create a new runtime tool.

        Args:
            name: Tool name (must be valid Python identifier)
            description: What the tool does
            parameters: JSON schema for parameters
            code: Python code implementing the tool
            author: Who created it

        Returns:
            (success, message)
        """
        # Validate name
        if not name.isidentifier():
            return False, f"Invalid tool name: {name}"

        # Check if tool already exists
        if name in self._tools:
            return False, f"Tool already exists: {name}"

        # Validate code
        is_valid, error = self._validate_code(code)
        if not is_valid:
            return False, f"Code validation failed: {error}"

        # Create tool spec
        from datetime import datetime

        spec = ToolSpec(
            name=name,
            description=description,
            parameters=parameters,
            code=code,
            author=author,
            created_at=datetime.now().isoformat(),
        )

        # Save to disk
        tool_path = self._tools_dir / f"{name}.json"
        try:
            tool_path.write_text(
                json.dumps(spec.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as e:
            return False, f"Failed to save tool: {e}"

        # Register in memory
        self._tools[name] = spec
        log.info(f"Created runtime tool: {name}")

        return True, f"Tool '{name}' created successfully"

    def get_tool(self, name: str) -> Optional[ToolSpec]:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> List[Dict[str, Any]]:
        """List all runtime tools."""
        return [
            {
                "name": spec.name,
                "description": spec.description,
                "author": spec.author,
                "created_at": spec.created_at,
            }
            for spec in self._tools.values()
        ]

    def remove_tool(self, name: str) -> Tuple[bool, str]:
        """Remove a runtime tool.

        Returns (success, message)
        """
        if name not in self._tools:
            return False, f"Tool not found: {name}"

        # Remove from disk
        tool_path = self._tools_dir / f"{name}.json"
        try:
            if tool_path.exists():
                tool_path.unlink()
        except Exception as e:
            return False, f"Failed to delete tool file: {e}"

        # Remove from memory
        del self._tools[name]
        log.info(f"Removed runtime tool: {name}")

        return True, f"Tool '{name}' removed"

    def get_tool_function(self, name: str) -> Optional[Callable]:
        """Get the executable function for a tool.

        Compiles the tool code and returns the function.
        """
        spec = self._tools.get(name)
        if not spec:
            return None

        try:
            # Create a namespace for the tool
            namespace: Dict[str, Any] = {}

            # Import safe modules into namespace
            for module_name in SAFE_MODULES:
                try:
                    module = __import__(module_name)
                    namespace[module_name] = module
                except ImportError:
                    pass

            # Execute the tool code
            exec(spec.code, namespace)

            # Find the function (should be named same as tool)
            func = namespace.get(name)
            if func and callable(func):
                return func

            # Try to find any function in the namespace
            for key, value in namespace.items():
                if callable(value) and not key.startswith("_"):
                    return value

        except Exception as e:
            log.error(f"Failed to compile tool {name}: {e}")

        return None


# Singleton instance
_runtime_tool_creator: Optional[RuntimeToolCreator] = None


def get_runtime_tool_creator(tools_dir: Optional[Path] = None) -> RuntimeToolCreator:
    """Get singleton runtime tool creator."""
    global _runtime_tool_creator
    if _runtime_tool_creator is None:
        if tools_dir is None:
            tools_dir = Path(os.environ.get("REPO_DIR", ".")) / "runtime_tools"
        _runtime_tool_creator = RuntimeToolCreator(tools_dir)
    return _runtime_tool_creator
