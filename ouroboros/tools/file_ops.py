"""
File operations tools - glob, grep, stats, copy, move.
No external dependencies - uses Python standard library only.
"""

from __future__ import annotations

import pathlib
import re
import shutil
from typing import List, Optional, Tuple

from ouroboros.tools.registry import ToolContext, ToolEntry


def _glob_files(ctx: ToolContext, pattern: str, path: Optional[str] = None) -> str:
    """Find files matching a glob pattern."""
    base = ctx.repo_path(path) if path else ctx.repo_dir
    matches = list(base.glob(pattern))

    if not matches:
        return f"No files found matching '{pattern}' in {base}"

    result = [f"{'📁 ' if m.is_dir() else '📄 '}{m.relative_to(base)}" for m in sorted(matches)]
    return f"Found {len(matches)} files:\n" + "\n".join(result[:50])


def _grep_content(
    ctx: ToolContext, pattern: str, path: Optional[str] = None, file_pattern: str = "*.py", context_lines: int = 2
) -> str:
    """Search for pattern within files."""
    import fnmatch

    base = ctx.repo_path(path) if path else ctx.repo_dir
    regex = re.compile(pattern, re.IGNORECASE)

    matches: List[Tuple[pathlib.Path, int, str]] = []

    for py_file in base.rglob(file_pattern):
        if py_file.is_file():
            try:
                for i, line in enumerate(py_file.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                    if regex.search(line):
                        matches.append((py_file, i, line.strip()))
            except Exception:
                continue

    if not matches:
        return f"No matches found for '{pattern}' in {base}/**/{file_pattern}"

    result_lines = [f"Found {len(matches)} matches:"]
    for file_path, line_num, line_content in matches[:30]:
        rel_path = file_path.relative_to(base)
        result_lines.append(f"{rel_path}:{line_num}: {line_content[:100]}")

    return "\n".join(result_lines)


def _file_stats(ctx: ToolContext, path: str) -> str:
    """Get file/directory statistics."""
    target = ctx.repo_path(path)

    if not target.exists():
        return f"⚠️ Path does not exist: {path}"

    if target.is_file():
        content = target.read_text(encoding="utf-8", errors="ignore")
        lines = content.count("\n") + 1
        return f"""📄 File: {target.relative_to(ctx.repo_dir)}
Size: {target.stat().st_size:,} bytes
Lines: {lines:,}
Encoding: UTF-8"""

    # Directory
    files = list(target.rglob("*"))
    py_files = [f for f in files if f.suffix == ".py" and f.is_file()]

    total_lines = 0
    for pf in py_files:
        try:
            total_lines += len(pf.read_text(encoding="utf-8", errors="ignore").splitlines())
        except Exception:
            continue

    return f"""📁 Directory: {target.relative_to(ctx.repo_dir)}
Total files: {len(files)}
Python files: {len(py_files)}
Total Python lines: {total_lines:,}"""


def _copy_file(ctx: ToolContext, source: str, destination: str) -> str:
    """Copy a file or directory."""
    src = ctx.repo_path(source)
    dst = ctx.repo_path(destination)

    if not src.exists():
        return f"⚠️ Source does not exist: {source}"

    try:
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        return f"✅ Copied {source} -> {destination}"
    except Exception as e:
        return f"⚠️ Copy failed: {e}"


def _move_file(ctx: ToolContext, source: str, destination: str) -> str:
    """Move a file or directory."""
    src = ctx.repo_path(source)
    dst = ctx.repo_path(destination)

    if not src.exists():
        return f"⚠️ Source does not exist: {source}"

    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return f"✅ Moved {source} -> {destination}"
    except Exception as e:
        return f"⚠️ Move failed: {e}"


def _delete_file(ctx: ToolContext, path: str, recursive: bool = False) -> str:
    """Delete a file or directory."""
    target = ctx.repo_path(path)

    if not target.exists():
        return f"Path does not exist: {path}"

    try:
        if target.is_dir():
            if recursive:
                shutil.rmtree(target)
                return f"Deleted directory: {path}"
            else:
                return f"Use recursive=true to delete directory: {path}"
        else:
            target.unlink()
            return f"Deleted file: {path}"
    except Exception as e:
        return f"Delete failed: {e}"


def _repo_tree(ctx: ToolContext, path: Optional[str] = None, max_depth: int = 3) -> str:
    """Display directory tree structure."""
    import os

    base = ctx.repo_path(path) if path else ctx.repo_dir
    result = [f"{base.relative_to(ctx.repo_dir)}/"]

    def walk_dir(current: pathlib.Path, prefix: str, depth: int):
        if depth > max_depth:
            return

        try:
            entries = sorted(current.iterdir(), key=lambda x: (not x.is_dir(), x.name))
        except PermissionError:
            return

        dirs = []
        files = []

        for entry in entries:
            if entry.name.startswith("."):
                continue
            if entry.is_dir():
                dirs.append(entry)
            else:
                files.append(entry)

        for d in dirs:
            result.append(f"{prefix}📁 {d.name}/")
            walk_dir(d, prefix + "  ", depth + 1)

        for f in files[:5]:  # Limit files shown
            result.append(f"{prefix}📄 {f.name}")

        if len(files) > 5:
            result.append(f"{prefix}  ... and {len(files) - 5} more files")

    walk_dir(base, "", 0)
    return "\n".join(result[:50])


def _git_graph(ctx: ToolContext, max_commits: int = 20) -> str:
    """Display git history as ASCII graph."""
    import subprocess

    try:
        result = subprocess.run(
            ["git", "log", f"--max-count={max_commits}", "--graph", "--oneline", "--all", "--decorate"],
            cwd=str(ctx.repo_dir),
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout if result.stdout else "No git history."
    except Exception as e:
        return f"Git error: {e}"


def _code_quality(ctx: ToolContext, path: Optional[str] = None) -> str:
    """Basic code quality metrics without external tools."""
    import ast

    base = ctx.repo_path(path) if path else ctx.repo_dir

    total_files = 0
    total_lines = 0
    total_functions = 0
    total_classes = 0
    issues = []

    for py_file in base.rglob("*.py"):
        if "/.venv/" in str(py_file) or "/venv/" in str(py_file):
            continue

        try:
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            total_files += 1
            total_lines += len(content.splitlines())

            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        total_functions += 1
                    elif isinstance(node, ast.ClassDef):
                        total_classes += 1
            except SyntaxError:
                issues.append(f"{py_file.relative_to(base)}: Syntax error")

        except Exception:
            continue

    return (
        f"""Code Quality Report for {base.relative_to(ctx.repo_dir)}

Files: {total_files}
Lines: {total_lines:,}
Functions: {total_functions}
Classes: {total_classes}

Functions per file: {total_functions / max(total_files, 1):.1f}

Issues: {len(issues)}
"""
        + "\n".join(issues[:5])
        if issues
        else "No issues found."
    )


def get_tools() -> List[ToolEntry]:
    return [
        ToolEntry(
            "glob_files",
            {
                "name": "glob_files",
                "description": "Find files matching a glob pattern (e.g., '**/*.py'). Searches from repo root unless path specified.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pattern": {"type": "string", "description": "Glob pattern (e.g., '**/*.py', 'tests/*.py')"},
                        "path": {"type": "string", "description": "Optional directory to search in"},
                    },
                    "required": ["pattern"],
                },
            },
            _glob_files,
        ),
        ToolEntry(
            "grep_content",
            {
                "name": "grep_content",
                "description": "Search for a regex pattern within files. Useful for finding code patterns across the codebase.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pattern": {"type": "string", "description": "Regex pattern to search for"},
                        "path": {"type": "string", "description": "Optional directory to search in"},
                        "file_pattern": {
                            "type": "string",
                            "default": "*.py",
                            "description": "File pattern to match (e.g., '*.py', '*.md')",
                        },
                        "context_lines": {"type": "integer", "default": 2, "description": "Number of context lines"},
                    },
                    "required": ["pattern"],
                },
            },
            _grep_content,
        ),
        ToolEntry(
            "file_stats",
            {
                "name": "file_stats",
                "description": "Get statistics about a file or directory (size, line count, file count).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File or directory path (relative to repo)"},
                    },
                    "required": ["path"],
                },
            },
            _file_stats,
        ),
        ToolEntry(
            "copy_file",
            {
                "name": "copy_file",
                "description": "Copy a file or directory to a new location.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "source": {"type": "string", "description": "Source file or directory"},
                        "destination": {"type": "string", "description": "Destination path"},
                    },
                    "required": ["source", "destination"],
                },
            },
            _copy_file,
        ),
        ToolEntry(
            "move_file",
            {
                "name": "move_file",
                "description": "Move a file or directory to a new location.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "source": {"type": "string", "description": "Source file or directory"},
                        "destination": {"type": "string", "description": "Destination path"},
                    },
                    "required": ["source", "destination"],
                },
            },
            _move_file,
        ),
        ToolEntry(
            "delete_file",
            {
                "name": "delete_file",
                "description": "Delete a file or directory. Use with caution.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File or directory to delete"},
                        "recursive": {
                            "type": "boolean",
                            "default": False,
                            "description": "Allow recursive delete for directories",
                        },
                    },
                    "required": ["path"],
                },
            },
            _delete_file,
        ),
        ToolEntry(
            "repo_tree",
            {
                "name": "repo_tree",
                "description": "Display directory tree structure. Useful for understanding project layout.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Directory to display (default: repo root)"},
                        "max_depth": {"type": "integer", "default": 3, "description": "Maximum depth to display"},
                    },
                },
            },
            _repo_tree,
        ),
        ToolEntry(
            "git_graph",
            {
                "name": "git_graph",
                "description": "Display git history as ASCII graph. Shows branches, commits, and tags.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "max_commits": {"type": "integer", "default": 20, "description": "Maximum commits to show"},
                    },
                },
            },
            _git_graph,
        ),
        ToolEntry(
            "code_quality",
            {
                "name": "code_quality",
                "description": "Get basic code quality metrics (files, lines, functions, classes) without external tools.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Directory to analyze (default: repo root)"},
                    },
                },
            },
            _code_quality,
        ),
    ]
