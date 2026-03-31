"""
Ouroboros — Project Anatomy (File Index).

Maintains an index of files with descriptions and token estimates.
Before reading a file, check the index first to avoid unnecessary reads.
Inspired by OpenWolf's anatomy.md pattern.

Claims ~80% token reduction by avoiding blind file reads.
Stores data in vault/anatomy.json.
"""

from __future__ import annotations

import hashlib
import json
import logging
import pathlib
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

TOKENS_PER_CHAR = 0.25  # Approximate tokens per character


@dataclass
class FileEntry:
    path: str
    description: str = ""
    line_count: int = 0
    token_estimate: int = 0
    file_hash: str = ""
    last_scanned: str = ""
    category: str = ""  # "module", "test", "config", "doc", "tool"
    functions: List[str] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)


class ProjectAnatomy:
    """Manages the project file index."""

    def __init__(self, repo_dir: pathlib.Path):
        self.repo_dir = repo_dir
        self.index_path = repo_dir / "vault" / "anatomy.json"
        self._entries: Optional[Dict[str, FileEntry]] = None

    def _load(self) -> Dict[str, FileEntry]:
        if self._entries is not None:
            return self._entries
        if self.index_path.exists():
            try:
                data = json.loads(self.index_path.read_text(encoding="utf-8"))
                self._entries = {}
                for path, entry_data in data.get("files", {}).items():
                    self._entries[path] = FileEntry(**entry_data)
            except Exception as e:
                log.warning("Failed to load anatomy: %s", e)
                self._entries = {}
        else:
            self._entries = {}
        return self._entries

    def _save(self) -> None:
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "files": {path: vars(entry) for path, entry in self._entries.items()},
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "total_files": len(self._entries),
            "total_tokens": sum(e.token_estimate for e in self._entries.values()),
        }
        self.index_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _hash_file(self, path: pathlib.Path) -> str:
        try:
            return hashlib.md5(path.read_bytes()).hexdigest()[:12]
        except Exception:
            return ""

    def _extract_info(self, path: pathlib.Path, content: str) -> Tuple[str, List[str], List[str]]:
        lines = content.splitlines()
        functions = []
        imports = []
        first_comment = ""
        for line in lines[:20]:
            stripped = line.strip()
            if stripped.startswith("#") and not first_comment:
                first_comment = stripped.lstrip("# ").strip()
            if stripped.startswith("def ") or stripped.startswith("async def "):
                func_name = stripped.split("(")[0].replace("def ", "").replace("async ", "").strip()
                functions.append(func_name)
            if stripped.startswith("from ") or stripped.startswith("import "):
                imports.append(stripped[:60])
        return first_comment, functions[:20], imports[:10]

    def scan_file(self, rel_path: str) -> Optional[FileEntry]:
        full_path = self.repo_dir / rel_path
        if not full_path.exists() or not full_path.suffix == ".py":
            return None
        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return None

        entries = self._load()
        file_hash = self._hash_file(full_path)
        existing = entries.get(rel_path)

        if existing and existing.file_hash == file_hash:
            return existing

        description, functions, imports = self._extract_info(full_path, content)
        line_count = len(content.splitlines())
        token_estimate = int(len(content) * TOKENS_PER_CHAR)

        category = "module"
        if "test" in rel_path:
            category = "test"
        elif rel_path.startswith("ouroboros/tools/"):
            category = "tool"
        elif rel_path.endswith((".json", ".yaml", ".toml")):
            category = "config"

        entry = FileEntry(
            path=rel_path,
            description=description or f"{line_count}-line {category}",
            line_count=line_count,
            token_estimate=token_estimate,
            file_hash=file_hash,
            last_scanned=time.strftime("%Y-%m-%dT%H:%M:%S"),
            category=category,
            functions=functions,
            imports=imports,
        )
        entries[rel_path] = entry
        self._entries = entries
        self._save()
        return entry

    def scan_directory(self, directory: str = "ouroboros", max_files: int = 100) -> str:
        dir_path = self.repo_dir / directory
        if not dir_path.exists():
            return f"Directory not found: {directory}"
        scanned = 0
        for py_file in dir_path.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            rel = str(py_file.relative_to(self.repo_dir)).replace("\\", "/")
            self.scan_file(rel)
            scanned += 1
            if scanned >= max_files:
                break
        return f"Scanned {scanned} files in {directory}/"

    def lookup(self, rel_path: str) -> str:
        entries = self._load()
        entry = entries.get(rel_path)
        if not entry:
            return f"No anatomy entry for: {rel_path}"
        lines = [
            f"## {rel_path}",
            f"- **Description**: {entry.description}",
            f"- **Lines**: {entry.line_count}",
            f"- **Est. tokens**: ~{entry.token_estimate}",
            f"- **Category**: {entry.category}",
            f"- **Last scanned**: {entry.last_scanned}",
        ]
        if entry.functions:
            lines.append(f"- **Functions** ({len(entry.functions)}): {', '.join(entry.functions[:10])}")
        return "\n".join(lines)

    def search(self, query: str, limit: int = 10) -> str:
        entries = self._load()
        query_lower = query.lower()
        matches = []
        for e in entries.values():
            searchable = f"{e.path} {e.description} {' '.join(e.functions)} {' '.join(e.imports)}".lower()
            if query_lower in searchable:
                matches.append(e)
        if not matches:
            return f"No anatomy entries found for: {query}"
        lines = [f"Found {len(matches)} entries for '{query}':"]
        for m in matches[:limit]:
            lines.append(f"- `{m.path}` ({m.line_count} lines, ~{m.token_estimate} tok): {m.description[:60]}")
        return "\n".join(lines)

    def summary(self) -> str:
        entries = self._load()
        if not entries:
            return "Anatomy index is empty. Run anatomy_scan first."
        total_tokens = sum(e.token_estimate for e in entries.values())
        by_category: Dict[str, List[FileEntry]] = {}
        for e in entries.values():
            by_category.setdefault(e.category, []).append(e)

        lines = [
            f"## Project Anatomy ({len(entries)} files, ~{total_tokens:,} tokens)",
        ]
        for cat, files in sorted(by_category.items()):
            cat_tokens = sum(f.token_estimate for f in files)
            lines.append(f"\n### {cat.title()} ({len(files)} files, ~{cat_tokens:,} tokens)")
            for f in sorted(files, key=lambda x: -x.token_estimate)[:5]:
                lines.append(f"- `{f.path}`: {f.line_count} lines, ~{f.token_estimate} tok — {f.description[:50]}")
        return "\n".join(lines)

    def suggest_read(self, query: str) -> str:
        entries = self._load()
        query_lower = query.lower()
        best_matches = []
        for e in entries.values():
            score = 0
            if query_lower in e.path.lower():
                score += 3
            if query_lower in e.description.lower():
                score += 2
            for func in e.functions:
                if query_lower in func.lower():
                    score += 2
            if score > 0:
                best_matches.append((score, e))
        best_matches.sort(key=lambda x: -x[0])
        if not best_matches:
            return f"No relevant files found for: {query}"
        top = best_matches[0][1]
        return f"Best match: `{top.path}` (~{top.token_estimate} tokens): {top.description}"


def get_tools():
    from ouroboros.tools.registry import ToolEntry

    _managers: Dict[str, ProjectAnatomy] = {}

    def _get_manager(repo_dir: pathlib.Path) -> ProjectAnatomy:
        key = str(repo_dir)
        if key not in _managers:
            _managers[key] = ProjectAnatomy(repo_dir)
        return _managers[key]

    def anatomy_scan(ctx, directory: str = "ouroboros", max_files: int = 100) -> str:
        return _get_manager(ctx.repo_dir).scan_directory(directory, max_files)

    def anatomy_lookup(ctx, file_path: str) -> str:
        return _get_manager(ctx.repo_dir).lookup(file_path)

    def anatomy_search(ctx, query: str, limit: int = 10) -> str:
        return _get_manager(ctx.repo_dir).search(query, limit)

    def anatomy_summary(ctx) -> str:
        return _get_manager(ctx.repo_dir).summary()

    def anatomy_suggest(ctx, query: str) -> str:
        return _get_manager(ctx.repo_dir).suggest_read(query)

    return [
        ToolEntry(
            "anatomy_scan",
            {
                "name": "anatomy_scan",
                "description": "Scan a directory to build/update the file index with descriptions and token estimates.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "directory": {"type": "string", "default": "ouroboros", "description": "Directory to scan"},
                        "max_files": {"type": "integer", "default": 100, "description": "Max files to scan"},
                    },
                },
            },
            anatomy_scan,
        ),
        ToolEntry(
            "anatomy_lookup",
            {
                "name": "anatomy_lookup",
                "description": "Look up a file in the anatomy index to see its description, size, and functions.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Relative file path"},
                    },
                    "required": ["file_path"],
                },
            },
            anatomy_lookup,
        ),
        ToolEntry(
            "anatomy_search",
            {
                "name": "anatomy_search",
                "description": "Search the anatomy index for files matching a query.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "limit": {"type": "integer", "default": 10},
                    },
                    "required": ["query"],
                },
            },
            anatomy_search,
        ),
        ToolEntry(
            "anatomy_summary",
            {
                "name": "anatomy_summary",
                "description": "Get a summary of the project anatomy index.",
                "parameters": {"type": "object", "properties": {}},
            },
            anatomy_summary,
        ),
        ToolEntry(
            "anatomy_suggest",
            {
                "name": "anatomy_suggest",
                "description": "Get a suggestion for which file to read based on a query. Use before repo_read to save tokens.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "What you're looking for"},
                    },
                    "required": ["query"],
                },
            },
            anatomy_suggest,
        ),
    ]
