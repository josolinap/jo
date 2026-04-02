"""
Ouroboros — Stack Detection.

Auto-detects project stack (languages, frameworks, tools) and adjusts behavior.
Inspired by claw-code's CLAW.md stack detection pattern.

Detects:
- Languages (Python, JS/TS, Rust, Go, etc.)
- Frameworks (React, Django, FastAPI, etc.)
- Build tools (npm, cargo, make, etc.)
- Testing frameworks
- CI/CD systems
"""

from __future__ import annotations

import json
import logging
import pathlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

log = logging.getLogger(__name__)


@dataclass
class DetectedStack:
    languages: List[str] = field(default_factory=list)
    frameworks: List[str] = field(default_factory=list)
    build_tools: List[str] = field(default_factory=list)
    test_frameworks: List[str] = field(default_factory=list)
    ci_systems: List[str] = field(default_factory=list)
    package_managers: List[str] = field(default_factory=list)
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return vars(self)

    def summary(self) -> str:
        parts = []
        if self.languages:
            parts.append(f"Languages: {', '.join(self.languages)}")
        if self.frameworks:
            parts.append(f"Frameworks: {', '.join(self.frameworks)}")
        if self.build_tools:
            parts.append(f"Build: {', '.join(self.build_tools)}")
        if self.test_frameworks:
            parts.append(f"Tests: {', '.join(self.test_frameworks)}")
        if self.ci_systems:
            parts.append(f"CI: {', '.join(self.ci_systems)}")
        return "\n".join(parts) if parts else "No stack detected"


STACK_MARKERS = {
    "languages": {
        "python": ["pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "Pipfile", "*.py"],
        "javascript": ["package.json", "*.js", "*.jsx"],
        "typescript": ["tsconfig.json", "*.ts", "*.tsx"],
        "rust": ["Cargo.toml", "*.rs"],
        "go": ["go.mod", "go.sum", "*.go"],
        "java": ["pom.xml", "build.gradle", "*.java"],
        "ruby": ["Gemfile", "*.rb"],
        "php": ["composer.json", "*.php"],
        "csharp": ["*.csproj", "*.cs"],
        "swift": ["Package.swift", "*.swift"],
    },
    "frameworks": {
        "react": ["package.json:react", "*.jsx", "*.tsx"],
        "vue": ["package.json:vue", "*.vue"],
        "angular": ["package.json:@angular", "angular.json"],
        "django": ["manage.py", "settings.py"],
        "flask": ["app.py", "flask"],
        "fastapi": ["fastapi", "uvicorn"],
        "express": ["package.json:express"],
        "nextjs": ["next.config.js", "next.config.mjs", "package.json:next"],
        "nuxt": ["nuxt.config.ts", "nuxt.config.js"],
        "spring": ["pom.xml:spring", "build.gradle:spring"],
    },
    "build_tools": {
        "npm": ["package.json", "package-lock.json"],
        "yarn": ["yarn.lock"],
        "pnpm": ["pnpm-lock.yaml"],
        "cargo": ["Cargo.toml"],
        "make": ["Makefile"],
        "cmake": ["CMakeLists.txt"],
        "gradle": ["build.gradle"],
        "maven": ["pom.xml"],
        "webpack": ["webpack.config.js"],
        "vite": ["vite.config.ts", "vite.config.js"],
    },
    "test_frameworks": {
        "pytest": ["pytest.ini", "pyproject.toml:pytest", "conftest.py"],
        "jest": ["jest.config.js", "jest.config.ts", "package.json:jest"],
        "vitest": ["vitest.config.ts", "package.json:vitest"],
        "mocha": [".mocharc.json", "package.json:mocha"],
        "rust_test": ["Cargo.toml:[test]"],
        "go_test": ["*_test.go"],
        "junit": ["pom.xml:junit"],
    },
    "ci_systems": {
        "github_actions": [".github/workflows"],
        "gitlab_ci": [".gitlab-ci.yml"],
        "jenkins": ["Jenkinsfile"],
        "circleci": [".circleci/config.yml"],
        "travis": [".travis.yml"],
        "azure_pipelines": ["azure-pipelines.yml"],
    },
}


class StackDetector:
    """Detects project stack from file markers."""

    def __init__(self, repo_dir: pathlib.Path):
        self.repo_dir = repo_dir

    def detect(self) -> DetectedStack:
        stack = DetectedStack()
        markers_found = 0

        for category, items in STACK_MARKERS.items():
            for name, markers in items.items():
                for marker in markers:
                    if ":" in marker:
                        file_marker, content_marker = marker.split(":", 1)
                        if self._check_file_content(file_marker, content_marker):
                            getattr(stack, category).append(name)
                            markers_found += 1
                            break
                    elif "*" in marker:
                        if self._check_glob(marker):
                            getattr(stack, category).append(name)
                            markers_found += 1
                            break
                    elif self._check_file(marker):
                        getattr(stack, category).append(name)
                        markers_found += 1
                        break

        stack.confidence = min(1.0, markers_found * 0.1)
        return stack

    def _check_file(self, name: str) -> bool:
        return (self.repo_dir / name).exists()

    def _check_glob(self, pattern: str) -> bool:
        return any(self.repo_dir.rglob(pattern))

    def _check_file_content(self, filename: str, content: str) -> bool:
        path = self.repo_dir / filename
        if not path.exists():
            return False
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            return content.lower() in text.lower()
        except Exception:
            return False

    def suggest_verification(self, stack: DetectedStack) -> List[str]:
        suggestions = []
        if "pytest" in stack.test_frameworks:
            suggestions.append("pytest tests/ -v")
        if "jest" in stack.test_frameworks or "vitest" in stack.test_frameworks:
            suggestions.append("npm test")
        if "npm" in stack.build_tools or "yarn" in stack.build_tools or "pnpm" in stack.build_tools:
            suggestions.append("npm run lint")
        if "cargo" in stack.build_tools:
            suggestions.append("cargo test")
            suggestions.append("cargo clippy")
        if "make" in stack.build_tools:
            suggestions.append("make test")
        if "python" in stack.languages:
            suggestions.append("python -m py_compile **/*.py")
        if "typescript" in stack.languages:
            suggestions.append("npx tsc --noEmit")
        return suggestions

    def get_run_command(self, stack: DetectedStack) -> str:
        if "python" in stack.languages:
            if "fastapi" in stack.frameworks:
                return "uvicorn main:app --reload"
            if "flask" in stack.frameworks:
                return "flask run"
            if "django" in stack.frameworks:
                return "python manage.py runserver"
        if "node" in str(stack.languages) or "javascript" in stack.languages or "typescript" in stack.languages:
            if "nextjs" in stack.frameworks:
                return "npm run dev"
            return "npm start"
        if "rust" in stack.languages:
            return "cargo run"
        if "go" in stack.languages:
            return "go run ."
        return ""


def get_tools():
    from ouroboros.tools.registry import ToolEntry

    _detectors: Dict[str, StackDetector] = {}

    def _get_detector(repo_dir: pathlib.Path) -> StackDetector:
        key = str(repo_dir)
        if key not in _detectors:
            _detectors[key] = StackDetector(repo_dir)
        return _detectors[key]

    def stack_detect(ctx) -> str:
        stack = _get_detector(ctx.repo_dir).detect()
        return stack.summary()

    def stack_verify_suggest(ctx) -> str:
        detector = _get_detector(ctx.repo_dir)
        stack = detector.detect()
        suggestions = detector.suggest_verification(stack)
        if not suggestions:
            return "No verification suggestions for detected stack."
        return "Suggested verification commands:\n" + "\n".join(f"- {s}" for s in suggestions)

    def stack_run_command(ctx) -> str:
        detector = _get_detector(ctx.repo_dir)
        stack = detector.detect()
        cmd = detector.get_run_command(stack)
        return f"Run command: {cmd}" if cmd else "No run command detected for this stack."

    return [
        ToolEntry(
            "stack_detect",
            {
                "name": "stack_detect",
                "description": "Auto-detect the project's technology stack (languages, frameworks, tools).",
                "parameters": {"type": "object", "properties": {}},
            },
            stack_detect,
        ),
        ToolEntry(
            "stack_verify_suggest",
            {
                "name": "stack_verify_suggest",
                "description": "Get suggested verification commands based on detected stack.",
                "parameters": {"type": "object", "properties": {}},
            },
            stack_verify_suggest,
        ),
        ToolEntry(
            "stack_run_command",
            {
                "name": "stack_run_command",
                "description": "Get the run command for the detected stack.",
                "parameters": {"type": "object", "properties": {}},
            },
            stack_run_command,
        ),
    ]
