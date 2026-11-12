"""
Ouroboros Repo Pack — Pack a repository into a single LLM-friendly file.

Inspired by Repomix (https://github.com/yamadashy/repomix) but tailored for Jo:
- Pure Python (no Node.js dependency, works in Jo's venv)
- Python-aware compression (AST-based signature extraction)
- Secret detection (regex-based, no external deps)
- Token counting (approximate, no tiktoken dependency)
- Directory tree generation
- Multiple output formats (XML, Markdown, JSON, Plain)
- Integrated as a Jo tool (repo_pack)

Usage as a module:
    from ouroboros.repo_pack import pack_repository
    result = pack_repository(
        root=pathlib.Path("."),
        output_format="xml",
        compress=False,
        include_vault=True,
    )
    print(result.output)

Usage as a tool:
    Jo calls `repo_pack` with optional include/exclude/compress/format parameters.
"""

from __future__ import annotations

import ast
import hashlib
import json
import logging
import os
import pathlib
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

log = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════
# Default ignore patterns (adapted from Repomix's defaultIgnore.ts)
# ═══════════════════════════════════════════════════════════════════════

DEFAULT_IGNORE_PATTERNS: List[str] = [
    # Version control
    ".git", ".gitignore", ".gitattributes", ".gitmodules",
    # Dependencies
    "node_modules", "__pycache__", ".venv", "venv", "env",
    ".bun", ".npm", ".npm-global",
    # Build outputs
    "dist", "build", "target", "out", ".next",
    "*.pyc", "*.pyo", "*.pyd", "*.so", "*.dll", "*.dylib",
    "*.egg-info", "*.whl",
    # IDE / Editor
    ".vscode", ".idea", ".cursor", "*.swp", "*.swo", "*~",
    ".DS_Store", "Thumbs.db",
    # Lock files
    "package-lock.json", "bun.lockb", "yarn.lock",
    "poetry.lock", "Pipfile.lock",
    # Secrets / env
    ".env", ".env.*", "*.pem", "*.key", "*.p12", "*.pfx",
    # Logs
    "*.log", "logs/",
    # OS
    ".Trash-*",
    # Repomix / pack outputs
    "repomix-output.*", "*.repomix.*",
    # Jo-specific
    ".jo_data", ".vault", "vault/.vault",
]

# File extensions that are text (everything else treated as binary)
TEXT_EXTENSIONS: Set[str] = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs",
    ".md", ".txt", ".rst", ".asciidoc",
    ".json", ".jsonc", ".json5", ".yaml", ".yml", ".toml", ".ini", ".cfg",
    ".xml", ".html", ".css", ".scss", ".sass", ".less",
    ".sh", ".bash", ".zsh", ".fish", ".ps1",
    ".sql", ".graphql", ".gql",
    ".dockerfile", "Dockerfile",
    ".gitignore", ".gitattributes",
    ".env.example", ".editorconfig",
    ".rs", ".go", ".java", ".kt", ".scala", ".clj", ".cljs",
    ".c", ".cpp", ".cc", ".cxx", ".h", ".hpp", ".hxx",
    ".rb", ".php", ".swift", ".dart",
    ".lua", ".r", ".jl",
    ".makefile", "Makefile", "makefile",
    ".cfg", ".conf",
}

# Max file size (50 MB, matching Repomix default)
MAX_FILE_SIZE = 50 * 1024 * 1024

# Secret detection patterns (adapted from common secret formats)
SECRET_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("AWS Access Key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("AWS Secret Key", re.compile(r"aws_secret_access_key\s*=\s*['\"]([A-Za-z0-9/+=]{40})['\"]")),
    ("GitHub Token", re.compile(r"gh[pousr]_[A-Za-z0-9]{36}")),
    ("GitHub Token (legacy)", re.compile(r"github_token\s*[:=]\s*['\"]([a-f0-9]{40})['\"]", re.IGNORECASE)),
    ("OpenAI API Key", re.compile(r"sk-[A-Za-z0-9]{48}")),
    ("OpenRouter API Key", re.compile(r"sk-or-[A-Za-z0-9-]+")),
    ("Slack Token", re.compile(r"xox[baprs]-[A-Za-z0-9-]+")),
    ("Google API Key", re.compile(r"AIza[0-9A-Za-z\-_]{35}")),
    ("Telegram Bot Token", re.compile(r"[0-9]{8,10}:AA[0-9A-Za-z\-_]{33}")),
    ("Private Key", re.compile(r"-----BEGIN (RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----")),
    ("Generic API Key", re.compile(r"(?i)(api[_-]?key|secret[_-]?key|auth[_-]?token)\s*[:=]\s*['\"]([A-Za-z0-9+/=]{20,})['\"]")),
    ("Bearer Token", re.compile(r"Bearer\s+[A-Za-z0-9\-_\.=]{20,}")),
]


# ═══════════════════════════════════════════════════════════════════════
# Data classes
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class PackedFile:
    """A single file in the packed output."""
    path: str
    content: str
    size: int
    lines: int
    tokens: int
    is_compressed: bool = False
    is_binary: bool = False
    security_issues: List[str] = field(default_factory=list)


@dataclass
class PackResult:
    """Result of packing a repository."""
    output: str
    format: str
    total_files: int
    total_tokens: int
    total_lines: int
    total_size: int
    top_files: List[Dict[str, Any]]
    security_warnings: List[str]
    directory_tree: str
    files: List[PackedFile] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════
# Token counting (approximate, no tiktoken dependency)
# ═══════════════════════════════════════════════════════════════════════

# Rough token estimation: ~4 chars per token for English text/code
# This is a heuristic; for exact counts, install tiktoken
_CHARS_PER_TOKEN = 4.0


def estimate_tokens(text: str) -> int:
    """Estimate token count for a string.

    Uses a simple heuristic: ~4 characters per token.
    For more accuracy, install tiktoken: pip install tiktoken
    """
    if not text:
        return 0
    # Try tiktoken if available
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except ImportError:
        pass
    # Fallback: character-based estimation
    # Code tends to have more tokens per char than prose
    code_ratio = 3.5  # slightly more tokens for code
    return max(1, int(len(text) / code_ratio))


# ═══════════════════════════════════════════════════════════════════════
# File discovery
# ═══════════════════════════════════════════════════════════════════════

def _matches_pattern(path: pathlib.Path, pattern: str) -> bool:
    """Check if a path matches a glob-like pattern."""
    import fnmatch
    name = path.name
    # Check against full path (relative)
    parts = path.parts
    for part in parts:
        if fnmatch.fnmatch(part, pattern):
            return True
    # Check against name
    if fnmatch.fnmatch(name, pattern):
        return True
    # Check against full path string
    if fnmatch.fnmatch(str(path), pattern):
        return True
    return False


def _is_ignored(path: pathlib.Path, ignore_patterns: List[str]) -> bool:
    """Check if a path should be ignored."""
    for pattern in ignore_patterns:
        if _matches_pattern(path, pattern):
            return True
    return False


def _is_text_file(path: pathlib.Path) -> bool:
    """Check if a file is likely text."""
    if path.suffix in TEXT_EXTENSIONS:
        return True
    # Check for files without extension that are text
    if path.name in ("Makefile", "Dockerfile", "Rakefile", "Gemfile", ".gitignore", ".env.example"):
        return True
    # Try to read first few bytes
    try:
        with open(path, "rb") as f:
            chunk = f.read(1024)
        if b"\x00" in chunk:
            return False  # Binary
        return True
    except (OSError, PermissionError):
        return False


def discover_files(
    root: pathlib.Path,
    include_patterns: Optional[List[str]] = None,
    ignore_patterns: Optional[List[str]] = None,
    respect_gitignore: bool = True,
) -> List[pathlib.Path]:
    """Discover all files in the repository, applying filters.

    Args:
        root: Root directory to search
        include_patterns: Glob patterns to include (if None, include all)
        ignore_patterns: Additional patterns to ignore
        respect_gitignore: Whether to respect .gitignore

    Returns:
        Sorted list of file paths (relative to root)
    """
    all_ignores = list(DEFAULT_IGNORE_PATTERNS)
    if ignore_patterns:
        all_ignores.extend(ignore_patterns)

    # Load .gitignore
    if respect_gitignore:
        gitignore = root / ".gitignore"
        if gitignore.exists():
            try:
                for line in gitignore.read_text().splitlines():
                    line = line.strip()
                    if line and not line.startswith("#"):
                        all_ignores.append(line)
            except (OSError, UnicodeDecodeError):
                pass

    files: List[pathlib.Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        # Get relative path
        try:
            rel = path.relative_to(root)
        except ValueError:
            continue

        # Check ignores
        if _is_ignored(rel, all_ignores):
            continue

        # Check includes
        if include_patterns:
            included = any(_matches_pattern(rel, p) for p in include_patterns)
            if not included:
                continue

        # Check size
        try:
            if path.stat().st_size > MAX_FILE_SIZE:
                log.debug(f"Skipping oversized file: {rel}")
                continue
        except (OSError, PermissionError):
            continue

        files.append(rel)

    return sorted(files)


# ═══════════════════════════════════════════════════════════════════════
# Security check
# ═══════════════════════════════════════════════════════════════════════

def check_secrets(content: str) -> List[str]:
    """Check file content for potential secrets.

    Returns list of issue descriptions (empty if clean).
    """
    issues: List[str] = []
    for name, pattern in SECRET_PATTERNS:
        matches = pattern.findall(content)
        if matches:
            # Don't include the actual secret value
            issues.append(f"Potential {name} detected ({len(matches)} occurrence(s))")
    return issues


# ═══════════════════════════════════════════════════════════════════════
# Python compression (AST-based)
# ═══════════════════════════════════════════════════════════════════════

def compress_python(source: str) -> str:
    """Compress Python source using AST — extract signatures only.

    Replaces function/class bodies with a placeholder, keeping:
    - All imports
    - All function signatures (name, args, return type)
    - All class definitions (name, bases, methods)
    - Docstrings
    - Top-level assignments with simple values
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        # Can't parse, return original
        return source

    lines = source.splitlines()
    output_lines: List[str] = []

    class CompressorVisitor(ast.NodeVisitor):
        def __init__(self):
            self.indent = 0
            self.output = output_lines

        def _emit(self, text: str):
            self.output.append("    " * self.indent + text)

        def visit_Import(self, node):
            for alias in node.names:
                if alias.asname:
                    self._emit(f"import {alias.name} as {alias.asname}")
                else:
                    self._emit(f"import {alias.name}")
            self.generic_visit(node)

        def visit_ImportFrom(self, node):
            names = []
            for alias in node.names:
                if alias.asname:
                    names.append(f"{alias.name} as {alias.asname}")
                else:
                    names.append(alias.name)
            self._emit(f"from {node.module} import {', '.join(names)}")

        def visit_FunctionDef(self, node):
            self._visit_function(node)

        def visit_AsyncFunctionDef(self, node):
            self._visit_function(node)

        def _visit_function(self, node):
            # Extract docstring
            docstring = ""
            if (node.body and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)):
                docstring = node.body[0].value.value

            # Build signature
            args = self._format_args(node.args)
            returns = ""
            if node.returns:
                returns = f" -> {ast.unparse(node.returns)}"

            decorators = ""
            if node.decorator_list:
                decorators = "".join(f"@{ast.unparse(d)}\n" + "    " * self.indent for d in node.decorator_list)

            self._emit(f"{decorators}{'async ' if isinstance(node, ast.AsyncFunctionDef) else ''}def {node.name}({args}){returns}:")

            if docstring:
                # Indent docstring
                self.indent += 1
                for line in docstring.strip().splitlines()[:3]:  # First 3 lines only
                    self._emit(line.strip())
                self.indent -= 1

            self._emit("    ...  # body compressed")
            self.output.append("")  # blank line

        def _format_args(self, args: ast.arguments) -> str:
            parts = []
            # Regular args
            for arg in args.args:
                arg_str = arg.arg
                if arg.annotation:
                    arg_str += f": {ast.unparse(arg.annotation)}"
                parts.append(arg_str)
            # *args
            if args.vararg:
                v = f"*{args.vararg.arg}"
                if args.vararg.annotation:
                    v += f": {ast.unparse(args.vararg.annotation)}"
                parts.append(v)
            # **kwargs
            if args.kwarg:
                k = f"**{args.kwarg.arg}"
                if args.kwarg.annotation:
                    k += f": {ast.unparse(args.kwarg.annotation)}"
                parts.append(k)
            return ", ".join(parts)

        def visit_ClassDef(self, node):
            # Bases
            bases = ""
            if node.bases:
                bases = "(" + ", ".join(ast.unparse(b) for b in node.bases) + ")"

            decorators = ""
            if node.decorator_list:
                decorators = "".join(f"@{ast.unparse(d)}\n" + "    " * self.indent for d in node.decorator_list)

            self._emit(f"{decorators}class {node.name}{bases}:")

            # Extract docstring
            docstring = ""
            if (node.body and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)):
                docstring = node.body[0].value.value

            if docstring:
                self.indent += 1
                for line in docstring.strip().splitlines()[:3]:
                    self._emit(line.strip())
                self.indent -= 1

            # Visit children (methods)
            self.indent += 1
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    self._visit_function(child)
                elif isinstance(child, ast.Assign):
                    # Class-level attributes
                    for target in child.targets:
                        if isinstance(target, ast.Name):
                            self._emit(f"{target.id} = ...")
            self.indent -= 1
            self.output.append("")

        def visit_Assign(self, node):
            # Only top-level assignments with simple values
            if self.indent == 0:
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        try:
                            value = ast.unparse(node.value)
                            if len(value) < 100:
                                self._emit(f"{target.id} = {value}")
                        except Exception:
                            self._emit(f"{target.id} = ...")

        def visit_AnnAssign(self, node):
            if self.indent == 0 and node.target and isinstance(node.target, ast.Name):
                ann = ast.unparse(node.annotation) if node.annotation else ""
                val = ""
                if node.value:
                    try:
                        val = f" = {ast.unparse(node.value)}"
                        if len(val) > 100:
                            val = " = ..."
                    except Exception:
                        val = " = ..."
                self._emit(f"{node.target.id}: {ann}{val}")

    visitor = CompressorVisitor()
    visitor.visit(tree)
    return "\n".join(output_lines)


def compress_file(content: str, ext: str) -> str:
    """Compress file content based on language."""
    if ext == ".py":
        return compress_python(content)
    # For other languages, just remove comments and empty lines (simple heuristic)
    lines = content.splitlines()
    result = []
    for line in lines:
        stripped = line.strip()
        # Skip empty lines
        if not stripped:
            continue
        # Skip single-line comments (basic)
        if ext in (".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs", ".c", ".cpp", ".css"):
            if stripped.startswith("//"):
                continue
        elif ext in (".py", ".sh", ".rb", ".yaml", ".yml"):
            if stripped.startswith("#"):
                continue
        result.append(line)
    return "\n".join(result)


# ═══════════════════════════════════════════════════════════════════════
# Directory tree generation
# ═══════════════════════════════════════════════════════════════════════

def generate_directory_tree(files: List[pathlib.Path], root: pathlib.Path) -> str:
    """Generate a directory tree string from file list."""
    tree: Dict[str, Any] = {}
    for f in files:
        parts = f.parts
        node = tree
        for part in parts[:-1]:
            if part not in node:
                node[part] = {}
            node = node[part]
        node[parts[-1]] = None  # File marker

    def render(node: Dict[str, Any], prefix: str = "", is_last: bool = True) -> List[str]:
        lines = []
        items = sorted(node.items(), key=lambda x: (x[1] is None, x[0]))  # Dirs first
        for i, (name, child) in enumerate(items):
            is_last_item = i == len(items) - 1
            connector = "└── " if is_last_item else "├── "
            lines.append(f"{prefix}{connector}{name}")
            if child is not None:  # Directory
                extension = "    " if is_last_item else "│   "
                lines.extend(render(child, prefix + extension))
        return lines

    return "\n".join(render(tree))


# ═══════════════════════════════════════════════════════════════════════
# Output formatters
# ═══════════════════════════════════════════════════════════════════════

def format_xml(packed_files: List[PackedFile], tree: str, header: Optional[str] = None) -> str:
    """Format as XML (Repomix-style)."""
    lines = [
        "This file is a merged representation of the entire codebase, combined into a single document.",
        "",
        "<file_summary>",
        "  <purpose>This file contains a packed representation of the repository's contents",
        "  for consumption by AI systems.</purpose>",
        "  <format>",
        "    1. This summary section",
        "    2. Directory structure",
        "    3. Repository files, each with path and full contents",
        "  </format>",
        "  <usage>",
        "    - Treat as read-only reference",
        "    - Use file paths to distinguish between files",
        "    - Security-sensitive content has been flagged",
        "  </usage>",
        "</file_summary>",
        "",
    ]

    if header:
        lines.append(f"<header>{header}</header>")
        lines.append("")

    lines.append("<directory_structure>")
    lines.append(tree)
    lines.append("</directory_structure>")
    lines.append("")

    lines.append("<files>")
    for pf in packed_files:
        attrs = f' path="{pf.path}"'
        if pf.is_compressed:
            attrs += ' compressed="true"'
        if pf.is_binary:
            attrs += ' binary="true"'
        if pf.security_issues:
            attrs += ' security="flagged"'
        lines.append(f"<file{attrs}>")
        if not pf.is_binary:
            lines.append(pf.content)
        else:
            lines.append("(binary file, content omitted)")
        lines.append("</file>")
    lines.append("</files>")

    return "\n".join(lines)


def format_markdown(packed_files: List[PackedFile], tree: str, header: Optional[str] = None) -> str:
    """Format as Markdown."""
    # Find the longest run of backticks to determine fence length
    max_backticks = 3
    for pf in packed_files:
        if not pf.is_binary:
            for match in re.finditer(r"`+", pf.content):
                max_backticks = max(max_backticks, len(match.group()))
    fence = "`" * (max_backticks + 1)

    lines = [
        "# Repository Pack",
        "",
        "## Purpose",
        "This file contains a packed representation of the repository's contents",
        "for consumption by AI systems.",
        "",
    ]

    if header:
        lines.append(f"## Header")
        lines.append(header)
        lines.append("")

    lines.append("## Directory Structure")
    lines.append("```")
    lines.append(tree)
    lines.append("```")
    lines.append("")

    lines.append("## Files")
    lines.append("")

    for pf in packed_files:
        lang = ""
        if pf.path.endswith(".py"):
            lang = "python"
        elif pf.path.endswith((".js", ".jsx")):
            lang = "javascript"
        elif pf.path.endswith((".ts", ".tsx")):
            lang = "typescript"
        elif pf.path.endswith(".md"):
            lang = "markdown"
        elif pf.path.endswith((".yaml", ".yml")):
            lang = "yaml"
        elif pf.path.endswith(".json"):
            lang = "json"
        elif pf.path.endswith(".sh"):
            lang = "bash"

        marker = ""
        if pf.is_compressed:
            marker = " (compressed)"
        if pf.security_issues:
            marker += " ⚠️ (security flagged)"

        lines.append(f"### File: {pf.path}{marker}")
        lines.append(f"{fence}{lang}")
        if pf.is_binary:
            lines.append("(binary file, content omitted)")
        else:
            lines.append(pf.content)
        lines.append(f"{fence}")
        lines.append("")

    return "\n".join(lines)


def format_json(packed_files: List[PackedFile], tree: str, header: Optional[str] = None) -> str:
    """Format as JSON."""
    data = {
        "directoryStructure": tree,
        "files": {
            pf.path: "(binary)" if pf.is_binary else pf.content
            for pf in packed_files
        },
        "metadata": {
            "totalFiles": len(packed_files),
            "compressedFiles": sum(1 for pf in packed_files if pf.is_compressed),
            "binaryFiles": sum(1 for pf in packed_files if pf.is_binary),
            "securityFlagged": sum(1 for pf in packed_files if pf.security_issues),
        }
    }
    if header:
        data["header"] = header
    return json.dumps(data, indent=2, ensure_ascii=False)


def format_plain(packed_files: List[PackedFile], tree: str, header: Optional[str] = None) -> str:
    """Format as plain text."""
    sep = "=" * 64
    file_sep = "=" * 16

    lines = [sep, "Repository Pack", sep, ""]

    if header:
        lines.extend([header, ""])

    lines.extend(["Directory Structure", sep, tree, "", "Files", sep, ""])

    for pf in packed_files:
        marker = ""
        if pf.is_compressed:
            marker = " (compressed)"
        if pf.security_issues:
            marker += " (SECURITY FLAGGED)"
        lines.extend([file_sep, f"File: {pf.path}{marker}", file_sep])
        if pf.is_binary:
            lines.append("(binary file, content omitted)")
        else:
            lines.append(pf.content)
        lines.append("")

    lines.extend([sep, "End of Codebase", sep])
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════
# Main pack function
# ═══════════════════════════════════════════════════════════════════════

def pack_repository(
    root: pathlib.Path,
    output_format: str = "xml",
    compress: bool = False,
    include_patterns: Optional[List[str]] = None,
    ignore_patterns: Optional[List[str]] = None,
    respect_gitignore: bool = True,
    include_vault: bool = False,
    header: Optional[str] = None,
    max_files: int = 500,
    max_tokens: Optional[int] = None,
    security_check: bool = True,
) -> PackResult:
    """Pack a repository into a single LLM-friendly file.

    Args:
        root: Repository root directory
        output_format: "xml", "markdown", "json", or "plain"
        compress: If True, compress Python files using AST (signatures only)
        include_patterns: Glob patterns to include
        ignore_patterns: Additional patterns to ignore
        respect_gitignore: Whether to respect .gitignore
        include_vault: If True, include vault/ directory even if not in include_patterns
        header: Optional header text to include in output
        max_files: Maximum number of files to pack (safety limit)
        max_tokens: If set, stop packing when token budget exceeded
        security_check: If True, scan for secrets and flag files

    Returns:
        PackResult with the packed output and metadata
    """
    root = pathlib.Path(root).resolve()

    # Discover files
    files = discover_files(
        root,
        include_patterns=include_patterns,
        ignore_patterns=ignore_patterns,
        respect_gitignore=respect_gitignore,
    )

    # Include vault if requested
    if include_vault:
        vault_dir = root / "vault"
        if vault_dir.exists():
            for f in vault_dir.rglob("*.md"):
                if ".vault" not in f.parts:
                    rel = f.relative_to(root)
                    if rel not in files:
                        files.append(rel)
            files = sorted(files)

    # Limit file count
    if len(files) > max_files:
        log.warning(f"File count ({len(files)}) exceeds max ({max_files}), truncating")
        files = files[:max_files]

    # Generate directory tree
    tree = generate_directory_tree(files, root)

    # Process files
    packed_files: List[PackedFile] = []
    security_warnings: List[str] = []
    total_tokens = 0

    for rel_path in files:
        full_path = root / rel_path

        # Check if file is binary before reading
        if not _is_text_file(full_path):
            packed_files.append(PackedFile(
                path=str(rel_path),
                content="",
                size=full_path.stat().st_size if full_path.exists() else 0,
                lines=0,
                tokens=0,
                is_binary=True,
            ))
            continue

        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
        except (OSError, PermissionError):
            # Unreadable
            packed_files.append(PackedFile(
                path=str(rel_path),
                content="",
                size=0,
                lines=0,
                tokens=0,
                is_binary=True,
            ))
            continue

        # Security check
        security_issues: List[str] = []
        if security_check:
            security_issues = check_secrets(content)
            if security_issues:
                security_warnings.append(f"{rel_path}: {'; '.join(security_issues)}")

        # Compress if requested
        is_compressed = False
        if compress and rel_path.suffix == ".py":
            compressed = compress_file(content, rel_path.suffix)
            if len(compressed) < len(content):
                content = compressed
                is_compressed = True

        # Calculate metrics
        lines_count = content.count("\n") + 1
        tokens = estimate_tokens(content)
        total_tokens += tokens

        packed_files.append(PackedFile(
            path=str(rel_path),
            content=content,
            size=len(content),
            lines=lines_count,
            tokens=tokens,
            is_compressed=is_compressed,
            security_issues=security_issues,
        ))

        # Check token budget
        if max_tokens and total_tokens > max_tokens:
            log.info(f"Token budget ({max_tokens}) exceeded, stopping at {len(packed_files)} files")
            break

    # Generate output
    if output_format == "xml":
        output = format_xml(packed_files, tree, header)
    elif output_format == "markdown":
        output = format_markdown(packed_files, tree, header)
    elif output_format == "json":
        output = format_json(packed_files, tree, header)
    elif output_format == "plain":
        output = format_plain(packed_files, tree, header)
    else:
        raise ValueError(f"Unknown output format: {output_format}")

    # Top files by tokens
    top_files = sorted(
        [{"path": pf.path, "tokens": pf.tokens, "lines": pf.lines, "size": pf.size}
         for pf in packed_files],
        key=lambda x: x["tokens"],
        reverse=True,
    )[:10]

    return PackResult(
        output=output,
        format=output_format,
        total_files=len(packed_files),
        total_tokens=total_tokens,
        total_lines=sum(pf.lines for pf in packed_files),
        total_size=sum(pf.size for pf in packed_files),
        top_files=top_files,
        security_warnings=security_warnings,
        directory_tree=tree,
        files=packed_files,
    )


# ═══════════════════════════════════════════════════════════════════════
# CLI entry point (for standalone use)
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Pack a repository into a single LLM-friendly file")
    parser.add_argument("root", nargs="?", default=".", help="Repository root (default: current dir)")
    parser.add_argument("-o", "--output", default="-", help="Output file (default: stdout)")
    parser.add_argument("-f", "--format", choices=["xml", "markdown", "json", "plain"], default="xml")
    parser.add_argument("-c", "--compress", action="store_true", help="Compress Python files (AST signatures only)")
    parser.add_argument("-i", "--include", help="Comma-separated include patterns")
    parser.add_argument("--ignore", help="Comma-separated ignore patterns")
    parser.add_argument("--no-gitignore", action="store_true", help="Don't respect .gitignore")
    parser.add_argument("--include-vault", action="store_true", help="Include vault/ directory")
    parser.add_argument("--max-files", type=int, default=500, help="Max files to pack")
    parser.add_argument("--max-tokens", type=int, help="Token budget limit")
    parser.add_argument("--no-security-check", action="store_true", help="Skip security check")
    parser.add_argument("--header", help="Header text to include in output")
    parser.add_argument("--stats", action="store_true", help="Print stats to stderr")

    args = parser.parse_args()

    result = pack_repository(
        root=pathlib.Path(args.root),
        output_format=args.format,
        compress=args.compress,
        include_patterns=args.include.split(",") if args.include else None,
        ignore_patterns=args.ignore.split(",") if args.ignore else None,
        respect_gitignore=not args.no_gitignore,
        include_vault=args.include_vault,
        header=args.header,
        max_files=args.max_files,
        max_tokens=args.max_tokens,
        security_check=not args.no_security_check,
    )

    if args.output == "-":
        print(result.output)
    else:
        pathlib.Path(args.output).write_text(result.output)
        print(f"Written {len(result.output)} bytes to {args.output}", file=sys.stderr)

    if args.stats:
        print(f"\n=== Pack Statistics ===", file=sys.stderr)
        print(f"Total files: {result.total_files}", file=sys.stderr)
        print(f"Total tokens: {result.total_tokens:,}", file=sys.stderr)
        print(f"Total lines: {result.total_lines:,}", file=sys.stderr)
        print(f"Total size: {result.total_size:,} bytes", file=sys.stderr)
        if result.security_warnings:
            print(f"\n⚠️  Security warnings ({len(result.security_warnings)}):", file=sys.stderr)
            for w in result.security_warnings:
                print(f"  {w}", file=sys.stderr)
        print(f"\nTop files by tokens:", file=sys.stderr)
        for tf in result.top_files[:5]:
            print(f"  {tf['tokens']:>6} tokens  {tf['lines']:>6} lines  {tf['path']}", file=sys.stderr)
