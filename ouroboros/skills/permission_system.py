"""
Jo — Permission System.

Risk classification and permission management inspired by Claude Code's permission system.

Permission Modes:
- default: Interactive prompts for approval
- auto: ML-based auto-approval via classifier
- bypass: Skip checks entirely
- yolo: Deny all (ironically named)

Risk Classification:
- LOW: Safe operations (read-only, info queries)
- MEDIUM: Potentially destructive but recoverable
- HIGH: Dangerous operations (data loss, system changes)

Features:
- Protected files list
- Path traversal prevention
- Risk classification per tool
- Permission explainer (LLM-generated risk explanations)
"""

from __future__ import annotations

import logging
import pathlib
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

log = logging.getLogger(__name__)


class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PermissionMode(Enum):
    DEFAULT = "default"  # Interactive prompts
    AUTO = "auto"  # ML-based auto-approval
    BYPASS = "bypass"  # Skip checks
    YOLO = "yolo"  # Deny all


@dataclass
class ToolAction:
    """A tool action to be evaluated."""

    tool_name: str
    args: Dict[str, Any]
    risk_level: RiskLevel = RiskLevel.LOW
    explanation: str = ""
    blocked: bool = False
    block_reason: str = ""


# Protected files that cannot be automatically edited
PROTECTED_FILES: Set[str] = {
    ".gitconfig",
    ".bashrc",
    ".zshrc",
    ".mcp.json",
    ".claude.json",
    ".env",
    ".jo_protected",
    "memory/identity.md",
    "config/constitution.json",
    "constitution.json",  # Legacy path for backward compatibility
}

# Path traversal patterns to detect
PATH_TRAVERSAL_PATTERNS: List[re.Pattern] = [
    re.compile(r"\.\./"),  # Standard traversal
    re.compile(r"\.\\./"),  # Windows traversal
    re.compile(r"%2e%2e[/\\]"),  # URL-encoded traversal
    re.compile(r"\.\.%2[fF]"),  # Mixed encoding
    re.compile(r"%252e%252e"),  # Double encoding
]


class PermissionSystem:
    """Permission and risk classification system."""

    def __init__(self, repo_dir: pathlib.Path):
        self.repo_dir = repo_dir
        self.mode = PermissionMode.DEFAULT
        self._risk_rules = self._build_risk_rules()

    def _build_risk_rules(self) -> Dict[str, RiskLevel]:
        """Build risk classification rules for tools."""
        return {
            # LOW risk - read-only operations
            "repo_read": RiskLevel.LOW,
            "repo_status": RiskLevel.LOW,
            "repo_log": RiskLevel.LOW,
            "anatomy_scan": RiskLevel.LOW,
            "anatomy_lookup": RiskLevel.LOW,
            "anatomy_search": RiskLevel.LOW,
            "query_status": RiskLevel.LOW,
            "query_full": RiskLevel.LOW,
            "cerebrum_search": RiskLevel.LOW,
            "cerebrum_summary": RiskLevel.LOW,
            "buglog_search": RiskLevel.LOW,
            "buglog_summary": RiskLevel.LOW,
            "memory_extract": RiskLevel.LOW,
            "notepad_read": RiskLevel.LOW,
            "notepad_stats": RiskLevel.LOW,
            "project_memory_read": RiskLevel.LOW,
            "persistent_tag_list": RiskLevel.LOW,
            "state_full_context": RiskLevel.LOW,
            # MEDIUM risk - potentially destructive but recoverable
            "repo_write_commit": RiskLevel.MEDIUM,
            "repo_commit_push": RiskLevel.MEDIUM,
            "code_edit": RiskLevel.MEDIUM,
            "cerebrum_add": RiskLevel.MEDIUM,
            "buglog_log": RiskLevel.MEDIUM,
            "memory_extract_save": RiskLevel.MEDIUM,
            "notepad_write": RiskLevel.MEDIUM,
            "project_memory_add_note": RiskLevel.MEDIUM,
            "project_memory_add_directive": RiskLevel.MEDIUM,
            "persistent_tag_add": RiskLevel.MEDIUM,
            "plan_notepad_create": RiskLevel.MEDIUM,
            "plan_notepad_add": RiskLevel.MEDIUM,
            "state_cleanup": RiskLevel.MEDIUM,
            # HIGH risk - dangerous operations
            "repo_reset": RiskLevel.HIGH,
            "repo_force_push": RiskLevel.HIGH,
            "delete_file": RiskLevel.HIGH,
            "vault_write": RiskLevel.HIGH,
            "vault_create": RiskLevel.HIGH,
            "drive_write": RiskLevel.HIGH,
            "move_file": RiskLevel.HIGH,
            "copy_file": RiskLevel.HIGH,
        }

    def classify_risk(self, tool_name: str, args: Dict[str, Any]) -> ToolAction:
        """Classify the risk level of a tool action."""
        risk_level = self._risk_rules.get(tool_name, RiskLevel.MEDIUM)
        explanation = self._generate_explanation(tool_name, args, risk_level)
        blocked = self._is_blocked(tool_name, args)
        block_reason = self._get_block_reason(tool_name, args) if blocked else ""

        return ToolAction(
            tool_name=tool_name,
            args=args,
            risk_level=risk_level,
            explanation=explanation,
            blocked=blocked,
            block_reason=block_reason,
        )

    def _generate_explanation(self, tool_name: str, args: Dict[str, Any], risk_level: RiskLevel) -> str:
        """Generate a human-readable explanation of the risk."""
        explanations = {
            RiskLevel.LOW: f"Safe operation: {tool_name} is read-only or informational.",
            RiskLevel.MEDIUM: f"Moderate risk: {tool_name} may modify files but changes are recoverable via git.",
            RiskLevel.HIGH: f"High risk: {tool_name} may cause data loss or system changes. Review carefully.",
        }

        # Add file-specific warnings
        file_path = args.get("file_path", "")
        if file_path:
            if any(protected in file_path for protected in PROTECTED_FILES):
                return f"⚠️ HIGH RISK: {tool_name} is modifying a protected file: {file_path}"
            if self._has_path_traversal(file_path):
                return f"⚠️ BLOCKED: {tool_name} contains path traversal attempt: {file_path}"

        return explanations.get(risk_level, f"Unknown risk level for {tool_name}")

    def _is_blocked(self, tool_name: str, args: Dict[str, Any]) -> bool:
        """Check if a tool action should be blocked."""
        if self.mode == PermissionMode.YOLO:
            return True

        if self.mode == PermissionMode.BYPASS:
            return False

        # Check for path traversal
        file_path = args.get("file_path", "")
        if file_path and self._has_path_traversal(file_path):
            return True

        # Check protected files in auto mode
        if self.mode == PermissionMode.AUTO:
            if file_path and any(protected in file_path for protected in PROTECTED_FILES):
                return True

        return False

    def _get_block_reason(self, tool_name: str, args: Dict[str, Any]) -> str:
        """Get the reason for blocking a tool action."""
        if self.mode == PermissionMode.YOLO:
            return "YOLO mode: All operations are denied."

        file_path = args.get("file_path", "")
        if file_path:
            if self._has_path_traversal(file_path):
                return "Path traversal attempt detected and blocked."
            if any(protected in file_path for protected in PROTECTED_FILES):
                return f"Protected file modification blocked: {file_path}"

        return "Operation blocked by permission system."

    def _has_path_traversal(self, path: str) -> bool:
        """Check if a path contains traversal attempts."""
        # Normalize path
        normalized = path.replace("\\", "/").lower()

        # Check patterns
        for pattern in PATH_TRAVERSAL_PATTERNS:
            if pattern.search(normalized):
                return True

        # Check for .. in path components
        parts = normalized.split("/")
        if ".." in parts:
            return True

        return False

    def set_mode(self, mode: PermissionMode) -> str:
        """Set the permission mode."""
        self.mode = mode
        return f"Permission mode set to: {mode.value}"

    def get_status(self) -> Dict[str, Any]:
        """Get permission system status."""
        return {
            "mode": self.mode.value,
            "protected_files": list(PROTECTED_FILES),
            "risk_rules_count": len(self._risk_rules),
        }


# Global permission system instance
_system: Optional[PermissionSystem] = None


def get_permission_system(repo_dir: Optional[pathlib.Path] = None) -> PermissionSystem:
    """Get or create the global permission system."""
    global _system
    if _system is None:
        if repo_dir is None:
            repo_dir = pathlib.Path.cwd()
        _system = PermissionSystem(repo_dir)
    return _system
