"""
Ouroboros — Gap Detector.

Identifies gaps in automation, documentation, coverage, and processes.
Inspired by aidevops' gap awareness pattern.

Every session is an opportunity to identify what's missing and create tasks to fill them.
"""

from __future__ import annotations

import json
import logging
import pathlib
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


@dataclass
class Gap:
    gap_id: str
    category: str  # "documentation", "testing", "automation", "coverage", "process"
    description: str
    severity: str = "medium"  # low, medium, high, critical
    file_path: str = ""
    suggested_fix: str = ""
    detected_at: str = ""


class GapDetector:
    """Detects gaps in codebase coverage and processes."""

    def __init__(self, repo_dir: pathlib.Path):
        self.repo_dir = repo_dir
        self._gaps: List[Gap] = []

    def scan(self) -> List[Gap]:
        self._gaps = []
        self._check_missing_tests()
        self._check_missing_docs()
        self._check_missing_init()
        self._check_todo_comments()
        self._check_empty_functions()
        return self._gaps

    def _add_gap(
        self, category: str, description: str, severity: str = "medium", file_path: str = "", suggestion: str = ""
    ) -> None:
        gap_id = f"gap-{len(self._gaps) + 1:03d}"
        self._gaps.append(
            Gap(
                gap_id=gap_id,
                category=category,
                description=description,
                severity=severity,
                file_path=file_path,
                suggested_fix=suggestion,
                detected_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
            )
        )

    def _check_missing_tests(self) -> None:
        src_files = set()
        test_files = set()
        for f in (self.repo_dir / "ouroboros").rglob("*.py"):
            if "__pycache__" in str(f) or "__init__" in f.name:
                continue
            src_files.add(f.stem)
        for f in (self.repo_dir / "tests").rglob("*.py") if (self.repo_dir / "tests").exists() else []:
            test_files.add(f.stem.replace("test_", ""))
        missing = src_files - test_files
        for name in sorted(missing)[:10]:
            self._add_gap(
                "testing",
                f"No tests for module: {name}.py",
                "medium",
                f"ouroboros/{name}.py",
                f"Create tests/test_{name}.py",
            )

    def _check_missing_docs(self) -> None:
        for f in (self.repo_dir / "ouroboros").rglob("*.py"):
            if "__pycache__" in str(f):
                continue
            try:
                content = f.read_text(encoding="utf-8", errors="replace")
                lines = content.splitlines()
                has_docstring = False
                for line in lines[:20]:
                    if '"""' in line or "'''" in line:
                        has_docstring = True
                        break
                if not has_docstring and len(lines) > 20:
                    self._add_gap(
                        "documentation", f"Missing module docstring: {f.name}", "low", str(f.relative_to(self.repo_dir))
                    )
            except Exception:
                pass

    def _check_missing_init(self) -> None:
        for d in (self.repo_dir / "ouroboros").iterdir():
            if d.is_dir() and not d.name.startswith("_") and not d.name.startswith("."):
                if not (d / "__init__.py").exists():
                    self._add_gap(
                        "process", f"Missing __init__.py in: {d.name}/", "low", str(d.relative_to(self.repo_dir))
                    )

    def _check_todo_comments(self) -> None:
        pattern = re.compile(r"#\s*(TODO|FIXME|HACK|XXX|BUG)\s*:?\s*(.*)", re.IGNORECASE)
        count = 0
        for f in (self.repo_dir / "ouroboros").rglob("*.py"):
            if "__pycache__" in str(f):
                continue
            try:
                content = f.read_text(encoding="utf-8", errors="replace")
                for i, line in enumerate(content.splitlines(), 1):
                    m = pattern.search(line)
                    if m:
                        count += 1
                        if count <= 10:
                            self._add_gap(
                                "process",
                                f"{m.group(1)}: {m.group(2).strip()[:80]}",
                                "low",
                                f"{f.relative_to(self.repo_dir)}:{i}",
                            )
            except Exception:
                pass

    def _check_empty_functions(self) -> None:
        for f in (self.repo_dir / "ouroboros").rglob("*.py"):
            if "__pycache__" in str(f):
                continue
            try:
                content = f.read_text(encoding="utf-8", errors="replace")
                lines = content.splitlines()
                for i, line in enumerate(lines):
                    if line.strip().startswith("def ") or line.strip().startswith("async def "):
                        if i + 1 < len(lines):
                            next_line = lines[i + 1].strip()
                            if next_line == "pass" or (
                                next_line == '"""' and i + 2 < len(lines) and lines[i + 2].strip() == '"""'
                            ):
                                func_name = line.strip().split("(")[0].replace("def ", "").replace("async ", "").strip()
                                self._add_gap(
                                    "coverage",
                                    f"Empty function: {func_name}",
                                    "medium",
                                    f"{f.relative_to(self.repo_dir)}:{i + 1}",
                                )
            except Exception:
                pass

    def summary(self) -> str:
        if not self._gaps:
            self.scan()
        by_category: Dict[str, List[Gap]] = {}
        for g in self._gaps:
            by_category.setdefault(g.category, []).append(g)
        lines = [f"## Gap Analysis ({len(self._gaps)} gaps found)"]
        for cat, gaps in sorted(by_category.items()):
            severity_counts = {}
            for g in gaps:
                severity_counts[g.severity] = severity_counts.get(g.severity, 0) + 1
            lines.append(f"\n### {cat.title()} ({len(gaps)} gaps)")
            lines.append(f"- Severity: {json.dumps(severity_counts)}")
            for g in gaps[:5]:
                lines.append(f"- [{g.severity}] {g.description}")
                if g.suggested_fix:
                    lines.append(f"  Suggestion: {g.suggested_fix}")
        return "\n".join(lines)


def get_tools():
    from ouroboros.tools.registry import ToolEntry

    _detectors: Dict[str, GapDetector] = {}

    def _get_detector(repo_dir: pathlib.Path) -> GapDetector:
        key = str(repo_dir)
        if key not in _detectors:
            _detectors[key] = GapDetector(repo_dir)
        return _detectors[key]

    def gaps_scan(ctx) -> str:
        return _get_detector(ctx.repo_dir).summary()

    return [
        ToolEntry(
            "gaps_scan",
            {
                "name": "gaps_scan",
                "description": "Scan codebase for gaps in testing, documentation, automation, and coverage.",
                "parameters": {"type": "object", "properties": {}},
            },
            gaps_scan,
        ),
    ]
