"""Code normalizer for Jo - cleans code before LLM processing."""

from __future__ import annotations

import os
import re
from typing import Dict, List, Optional, Tuple


class CodeNormalizer:
    """Normalizes code to reduce noise and token waste before LLM processing."""

    def __init__(self):
        self._enabled = os.environ.get("OUROBOROS_NORMALIZE_CODE", "1") == "1"
        self._max_file_chars = int(os.environ.get("OUROBOROS_NORMALIZE_MAX_CHARS", "50000"))

    def is_enabled(self) -> bool:
        return self._enabled

    def normalize(self, code: str, file_type: str = "python") -> str:
        """Apply normalization based on file type."""
        if not self._enabled:
            return code

        if file_type == "python":
            return self.normalize_python(code)
        elif file_type in ("javascript", "typescript"):
            return self.normalize_javascript(code)
        elif file_type in ("yaml", "yml"):
            return self.normalize_yaml(code)
        elif file_type == "json":
            return self.normalize_json(code)

        return code

    def normalize_python(self, code: str) -> str:
        """Apply Python-specific normalizations."""
        if not code:
            return code

        normalized = code

        normalized = self._remove_trailing_whitespace(normalized)
        normalized = self._remove_consecutive_blanks(normalized)
        normalized = self._remove_debug_statements(normalized)
        normalized = self._remove_empty_triple_quoted_strings(normalized)
        normalized = self._normalize_docstring_formatting(normalized)

        return normalized.strip() + "\n"

    def normalize_javascript(self, code: str) -> str:
        """Apply JS/TS normalizations."""
        if not code:
            return code

        normalized = code

        normalized = self._remove_trailing_whitespace(normalized)
        normalized = self._remove_consecutive_blanks(normalized)
        normalized = self._remove_debug_statements(normalized)

        return normalized.strip() + "\n"

    def normalize_yaml(self, code: str) -> str:
        """Normalize YAML - remove excessive whitespace."""
        if not code:
            return code

        lines = code.split("\n")
        result = []

        for line in lines:
            stripped = line.rstrip()
            if stripped:
                result.append(stripped)

        return "\n".join(result) + "\n"

    def normalize_json(self, code: str) -> str:
        """Format JSON nicely."""
        import json

        try:
            parsed = json.loads(code)
            return json.dumps(parsed, indent=2, ensure_ascii=False) + "\n"
        except json.JSONDecodeError:
            return code

    def _remove_trailing_whitespace(self, code: str) -> str:
        """Remove trailing whitespace from each line."""
        return "\n".join(line.rstrip() for line in code.split("\n"))

    def _remove_consecutive_blanks(self, code: str) -> str:
        """Replace 3+ consecutive blank lines with 2."""
        return re.sub(r"\n{3,}", "\n\n", code)

    def _remove_debug_statements(self, code: str) -> str:
        """Remove obvious debug statements."""
        patterns = [
            r'print\(["\'].*debug.*["\']\)',
            r'console\.log\(["\'].*debug.*["\']\)',
            r"#\s*DEBUG:.*",
            r"//\s*DEBUG.*",
            r"/\*\s*DEBUG.*?\*/",
            r"#\s*TODO:.*remove.*debug",
            r"//\s*TODO:.*remove.*debug",
        ]

        result = code
        for pattern in patterns:
            result = re.sub(pattern, "", result, flags=re.IGNORECASE)

        return result

    def _remove_empty_triple_quoted_strings(self, code: str) -> str:
        """Remove empty or whitespace-only triple-quoted strings."""
        patterns = [
            r'"""\s*"""',
            r"'''\s*'''",
        ]

        result = code
        for pattern in patterns:
            result = re.sub(pattern, '"""', result)

        return result

    def _normalize_docstring_formatting(self, code: str) -> str:
        """Normalize docstring indentation."""
        lines = code.split("\n")
        result = []
        in_docstring = False
        docstring_indent = 0

        for line in lines:
            stripped = line.lstrip()

            if stripped.startswith('"""') or stripped.startswith("'''"):
                quote = stripped[:3]
                if stripped.endswith(quote) and len(stripped) > 6:
                    result.append(line)
                    continue

                if not in_docstring:
                    in_docstring = True
                    docstring_indent = len(line) - len(line.lstrip())
                else:
                    in_docstring = False

                result.append(line)
            elif in_docstring:
                if stripped:
                    indent = len(line) - len(stripped)
                    if indent > docstring_indent + 4:
                        excess = indent - docstring_indent - 4
                        line = " " * (docstring_indent + 4) + line.lstrip()
                result.append(line)
            else:
                result.append(line)

        return "\n".join(result)

    def extract_structure(self, code: str, file_type: str = "python") -> Dict[str, List[str]]:
        """Extract code structure for context."""
        structure: Dict[str, List[str]] = {
            "imports": [],
            "classes": [],
            "functions": [],
            "decorators": [],
            "constants": [],
        }

        if file_type == "python":
            return self._extract_python_structure(code)
        elif file_type in ("javascript", "typescript"):
            return self._extract_js_structure(code)

        return structure

    def _extract_python_structure(self, code: str) -> Dict[str, List[str]]:
        """Extract Python code structure."""
        structure: Dict[str, List[str]] = {
            "imports": [],
            "classes": [],
            "functions": [],
            "decorators": [],
            "constants": [],
        }

        for line in code.split("\n"):
            stripped = line.strip()

            if stripped.startswith("import ") or stripped.startswith("from "):
                structure["imports"].append(stripped)
            elif stripped.startswith("class "):
                match = re.match(r"class\s+(\w+)", stripped)
                if match:
                    structure["classes"].append(match.group(1))
            elif stripped.startswith("def "):
                match = re.match(r"def\s+(\w+)", stripped)
                if match:
                    structure["functions"].append(match.group(1))
            elif stripped.startswith("@") and not stripped.startswith("@"):
                structure["decorators"].append(stripped)
            elif re.match(r"^[A-Z][A-Z0-9_]*\s*=", stripped):
                structure["constants"].append(stripped.split("=")[0].strip())

        return structure

    def _extract_js_structure(self, code: str) -> Dict[str, List[str]]:
        """Extract JS/TS code structure."""
        structure: Dict[str, List[str]] = {
            "imports": [],
            "classes": [],
            "functions": [],
            "decorators": [],
            "constants": [],
        }

        for line in code.split("\n"):
            stripped = line.strip()

            if stripped.startswith("import ") or stripped.startswith("export "):
                structure["imports"].append(stripped)
            elif stripped.startswith("class "):
                match = re.match(r"class\s+(\w+)", stripped)
                if match:
                    structure["classes"].append(match.group(1))
            elif "function " in stripped or "=> {" in stripped:
                match = re.match(r"(?:function\s+)?(\w+)\s*\(", stripped)
                if match:
                    structure["functions"].append(match.group(1))
            elif re.match(r"^const\s+\w+\s*=", stripped):
                const_match = re.match(r"const\s+(\w+)", stripped)
                if const_match:
                    name = const_match.group(1)
                    if name.isupper():
                        structure["constants"].append(name)

        return structure

    def truncate(self, code: str, max_chars: Optional[int] = None, preserve_structure: bool = True) -> Tuple[str, str]:
        """Truncate code to fit limit, optionally preserving structure."""
        limit = max_chars or self._max_file_chars

        if len(code) <= limit:
            return code, ""

        if not preserve_structure:
            return code[:limit], f"[Truncated {len(code) - limit} chars]"

        structure = self.extract_structure(code)

        head_chars = limit // 2
        tail_chars = limit // 2

        head = code[:head_chars]
        tail = code[-tail_chars:]

        truncation_note = f"\n[... {len(code) - limit:,} chars truncated ...]\n"

        summary_parts = []
        if structure["classes"]:
            summary_parts.append(f"Classes: {', '.join(structure['classes'][:5])}")
        if structure["functions"]:
            summary_parts.append(f"Functions: {', '.join(structure['functions'][:10])}")
        if structure["imports"]:
            summary_parts.append(f"Imports: {len(structure['imports'])}")

        if summary_parts:
            truncation_note += "[Structure: " + " | ".join(summary_parts) + "]"

        return head + truncation_note + tail, f"Original: {len(code):,} chars"

    def truncate_for_llm(self, code: str, max_tokens: int = 2000) -> Tuple[str, str]:
        """Truncate code based on estimated token count."""
        char_limit = max_tokens * 4
        return self.truncate(code, max_chars=char_limit, preserve_structure=True)


_normalizer: Optional[CodeNormalizer] = None


def get_normalizer() -> CodeNormalizer:
    """Get singleton normalizer instance."""
    global _normalizer
    if _normalizer is None:
        _normalizer = CodeNormalizer()
    return _normalizer
