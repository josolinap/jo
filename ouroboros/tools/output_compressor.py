"""
Jo — Output Compressor.

Native Python output compression - similar to RTK but pure Python.
Compresses command outputs before they reach the LLM context.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)


class OutputCompressor:
    """
    Compress command output for token efficiency.

    Strategies:
    1. Smart Filtering - Removes noise (comments, whitespace, boilerplate)
    2. Grouping - Aggregates similar items (files by directory, errors by type)
    3. Truncation - Keeps relevant context, cuts redundancy
    4. Deduplication - Collapses repeated log lines with counts
    """

    def __init__(self, max_tokens: int = 2000):
        self.max_tokens = max_tokens
        # Rough token estimate: 1 token ~= 4 chars
        self.max_chars = max_tokens * 4

    def compress(self, output: str, command_type: str = "generic") -> str:
        """Compress output based on command type."""
        if not output:
            return output

        # Step 1: Deduplicate repeated lines
        output = self._deduplicate(output)

        # Step 2: Type-specific compression
        if command_type == "git":
            output = self._compress_git(output)
        elif command_type == "test":
            output = self._compress_test(output)
        elif command_type == "lint":
            output = self._compress_lint(output)
        elif command_type == "build":
            output = self._compress_build(output)
        elif command_type == "ls":
            output = self._compress_ls(output)
        elif command_type == "grep":
            output = self._compress_grep(output)
        elif command_type == "diff":
            output = self._compress_diff(output)

        # Step 3: Truncate if still too long
        output = self._truncate(output)

        return output

    def _deduplicate(self, output: str) -> str:
        """Collapse repeated lines with counts."""
        lines = output.split("\n")
        if len(lines) <= 1:
            return output

        # Count ALL duplicates (not just consecutive)
        line_counts = {}
        for line in lines:
            line_counts[line] = line_counts.get(line, 0) + 1

        # Build result
        result = []
        for line in lines:
            count = line_counts.get(line, 1)
            if count > 2:
                # Mark as duplicate, only include once
                if line not in result:
                    result.append(f"{line} (x{count})")
            else:
                if line not in result:
                    result.append(line)

        return "\n".join(result)

    def _compress_git(self, output: str) -> str:
        """Compress git command output."""
        lines = output.split("\n")
        result = []

        # Parse git status
        if "git status" in output.lower():
            for line in lines:
                # Shorten paths
                line = re.sub(r"^\s+", "", line)
                if line.startswith("modified:") or line.startswith("M "):
                    result.append(f"M {line.split(' ', 1)[-1]}")
                elif line.startswith("new file:") or line.startswith("A "):
                    result.append(f"A {line.split(' ', 1)[-1]}")
                elif line.startswith("deleted:") or line.startswith("D "):
                    result.append(f"D {line.split(' ', 1)[-1]}")
                elif "nothing to commit" in line.lower():
                    return "✓ Working tree clean"
                elif line.strip():
                    result.append(line)
            return "\n".join(result[:30])  # Limit lines

        # Parse git log
        if "git log" in output.lower():
            commits = []
            for line in lines:
                if line.startswith("commit "):
                    commit = line.split()[1][:8]
                    commits.append(commit)
                elif line.startswith("Date:"):
                    date = line.replace("Date:", "").strip()[:20]
                    if commits:
                        commits[-1] += f" | {date}"

            if commits:
                return "Commits:\n" + "\n".join(commits[:10])

        # Parse git diff
        if "git diff" in output.lower():
            # Just show stats
            stats_match = re.search(r"(\d+) files? changed", output)
            insert_match = re.search(r"(\d+) insertions?", output)
            delete_match = re.search(r"(\d+) deletions?", output)

            stats = []
            if stats_match:
                stats.append(f"{stats_match.group(1)} files")
            if insert_match:
                stats.append(f"+{insert_match.group(1)}")
            if delete_match:
                stats.append(f"-{delete_match.group(1)}")

            if stats:
                return ", ".join(stats)

        return output[:5000]

    def _compress_test(self, output: str) -> str:
        """Compress test output - show failures only."""
        lines = output.split("\n")
        result = []
        failure_count = 0
        pass_count = 0
        seen_lines = set()

        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue

            # Skip if we've seen this exact line (avoid double counting)
            if line_stripped in seen_lines:
                continue
            seen_lines.add(line_stripped)

            # Check for PASSED status (be specific to avoid matching summary lines)
            if re.search(r"PASSED|passed|^ok |test passed", line, re.IGNORECASE):
                if "FAILED" not in line and "ERROR" not in line:
                    pass_count += 1
            # Check for FAILED/ERROR status
            elif re.search(r"FAILED|ERROR|failed|error", line, re.IGNORECASE):
                failure_count += 1
                # Show first 100 chars of failure line
                result.append(line_stripped[:100])

        if failure_count == 0 and pass_count > 0:
            return f"[PASS] All {pass_count} tests passed"

        if failure_count > 0:
            result.insert(0, f"[FAIL] {failure_count} failed, {pass_count} passed")

        return "\n".join(result[:30])

    def _compress_lint(self, output: str) -> str:
        """Compress lint output - group by rule."""
        lines = output.split("\n")
        errors = {}

        for line in lines:
            # Parse common lint formats
            match = re.match(r"(.+?):(\d+):(\d+):\s*(\w+)\s+(.+)", line)
            if match:
                file_path = match.group(1).split("/")[-1]
                rule = match.group(4)
                msg = match.group(5)[:50]

                key = f"{rule}:{msg}"
                if key not in errors:
                    errors[key] = []
                errors[key].append(f"{file_path}:{match.group(2)}")

        if errors:
            result = [f"Lint errors: {sum(len(v) for v in errors.values())}"]
            for rule, locations in list(errors.items())[:10]:
                result.append(f"  {rule}: {len(locations)}")
            return "\n".join(result)

        return output[:3000]

    def _compress_build(self, output: str) -> str:
        """Compress build output - show errors/warnings only."""
        lines = output.split("\n")
        result = []
        error_count = 0
        warning_count = 0

        for line in lines:
            if re.search(r"error:|ERROR:", line, re.IGNORECASE):
                error_count += 1
                result.append(f"ERROR: {line[:100]}")
            elif re.search(r"warning:|WARNING:", line, re.IGNORECASE):
                warning_count += 1

        if error_count > 0:
            return f"Build FAILED: {error_count} errors, {warning_count} warnings\n" + "\n".join(result[:10])
        elif warning_count > 0:
            return f"Build OK ({warning_count} warnings)"

        return "Build OK"

    def _compress_ls(self, output: str) -> str:
        """Compress directory listing."""
        lines = output.split("\n")
        result = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Shorten long listings
            if line.startswith("total"):
                continue

            # Format: drwxr-xr-x or -rw-r--r--
            parts = line.split()
            if len(parts) >= 9:
                perms = parts[0]
                name = " ".join(parts[8:])
                is_dir = perms.startswith("d")

                # Shorten path
                name = name.split("/")[-1]

                if is_dir:
                    result.append(f"{name}/")
                else:
                    result.append(name)

        return "\n".join(result[:50])

    def _compress_grep(self, output: str) -> str:
        """Compress grep output - group by file."""
        lines = output.split("\n")
        by_file: Dict[str, List[str]] = {}

        for line in lines:
            # Parse grep output
            match = re.match(r"(.+?):(\d+):(.+)", line)
            if match:
                file_path = match.group(1).split("/")[-1]
                line_num = match.group(2)
                content = match.group(3)[:60]

                if file_path not in by_file:
                    by_file[file_path] = []
                by_file[file_path].append(f"{line_num}: {content}")

        if by_file:
            result = []
            for file_path, matches in list(by_file.items())[:5]:
                result.append(f"{file_path}: {len(matches)} matches")
                for m in matches[:2]:
                    result.append(f"  {m}")

            return "\n".join(result)

        return output[:3000]

    def _compress_diff(self, output: str) -> str:
        """Compress diff output - show stats only for large diffs."""
        lines = output.split("\n")
        result = []

        # Count changes
        add_count = sum(1 for l in lines if l.startswith("+") and not l.startswith("+++"))
        del_count = sum(1 for l in lines if l.startswith("-") and not l.startswith("---"))

        if add_count > 20 or del_count > 20:
            return f"+{add_count} -{del_count} lines changed\n--- Truncated ---"

        return "\n".join(lines[:100])

    def _truncate(self, output: str) -> str:
        """Truncate output if too long."""
        if len(output) <= self.max_chars:
            return output

        # Keep beginning and end
        keep_chars = self.max_chars // 2
        return (
            output[:keep_chars]
            + f"\n... [truncated, {len(output) - self.max_chars} chars omitted] ...\n"
            + output[-keep_chars:]
        )


# Singleton
_compressor: Optional[OutputCompressor] = None


def get_compressor() -> OutputCompressor:
    """Get or create the output compressor."""
    global _compressor
    if _compressor is None:
        _compressor = OutputCompressor()
    return _compressor


# Convenience function for shell tool
def compress_shell_output(output: str, command: str = "") -> str:
    """Compress shell output based on command type."""
    compressor = get_compressor()

    # Detect command type
    cmd_lower = command.lower()

    if cmd_lower.startswith("git "):
        return compressor.compress(output, "git")
    elif "test" in cmd_lower or "pytest" in cmd_lower:
        return compressor.compress(output, "test")
    elif "lint" in cmd_lower or "ruff" in cmd_lower or "eslint" in cmd_lower:
        return compressor.compress(output, "lint")
    elif "build" in cmd_lower or "compile" in cmd_lower:
        return compressor.compress(output, "build")
    elif cmd_lower.startswith("ls") or cmd_lower.startswith("dir"):
        return compressor.compress(output, "ls")
    elif "grep" in cmd_lower or "rg" in cmd_lower or "find" in cmd_lower:
        return compressor.compress(output, "grep")
    elif "diff" in cmd_lower:
        return compressor.compress(output, "diff")

    return compressor.compress(output, "generic")
