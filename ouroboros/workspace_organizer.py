"""
Jo — Workspace Organization System.

Pairs minimalism (Principle 5) with proper workspace organization.
Ensures tools output to vaults, memory is coherent, and structure is clean.

Key principles:
1. Memory coherence: identity.md + scratchpad.md are the ONLY core memory
2. Vault output: All tools that produce knowledge should save to vault
3. Cleanup: Remove unused/duplicate vault notes
4. Structure: Clear separation between transient state and persistent knowledge
"""

from __future__ import annotations

import json
import logging
import pathlib
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


@dataclass
class WorkspaceReport:
    """Report on workspace organization health."""

    total_modules: int = 0
    total_tools: int = 0
    total_vault_notes: int = 0
    vault_by_category: Dict[str, int] = field(default_factory=dict)
    memory_files: List[str] = field(default_factory=list)
    orphaned_notes: List[str] = field(default_factory=list)
    duplicate_notes: List[str] = field(default_factory=list)
    unused_tools: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


class WorkspaceOrganizer:
    """Organizes Jo's workspace according to BIBLE.md principles."""

    def __init__(self, repo_dir: pathlib.Path):
        self.repo_dir = repo_dir
        self.memory_dir = repo_dir / "memory"
        self.vault_dir = repo_dir / "vault"
        self.state_dir = repo_dir / ".jo_state"
        self.skills_dir = repo_dir / ".jo_skills"

    def analyze(self) -> WorkspaceReport:
        """Analyze workspace organization health."""
        report = WorkspaceReport()

        # Count modules
        report.total_modules = len(list((self.repo_dir / "ouroboros").glob("*.py")))
        report.total_tools = len(list((self.repo_dir / "ouroboros" / "tools").glob("*_tools.py")))

        # Count vault notes
        if self.vault_dir.exists():
            for category_dir in self.vault_dir.iterdir():
                if category_dir.is_dir():
                    count = len(list(category_dir.glob("*.md")))
                    report.vault_by_category[category_dir.name] = count
                    report.total_vault_notes += count

        # List memory files
        if self.memory_dir.exists():
            report.memory_files = [f.name for f in self.memory_dir.iterdir() if f.is_file()]

        # Check for orphaned notes (notes with no wikilinks)
        report.orphaned_notes = self._find_orphaned_notes()

        # Check for duplicate notes (similar names)
        report.duplicate_notes = self._find_duplicate_notes()

        # Find unused tools (tools with no vault documentation)
        report.unused_tools = self._find_unused_tools()

        # Generate recommendations
        report.recommendations = self._generate_recommendations(report)

        return report

    def _find_orphaned_notes(self) -> List[str]:
        """Find vault notes with no wikilinks to other notes."""
        orphaned = []
        if not self.vault_dir.exists():
            return orphaned

        all_notes = list(self.vault_dir.rglob("*.md"))
        for note in all_notes:
            try:
                content = note.read_text(encoding="utf-8", errors="ignore")
                has_wikilink = "[[" in content and "]]" in content
                has_backlink = False
                # Check if any other note links to this one
                note_name = note.stem
                for other in all_notes:
                    if other != note:
                        try:
                            other_content = other.read_text(encoding="utf-8", errors="ignore")
                            if f"[[{note_name}" in other_content:
                                has_backlink = True
                                break
                        except Exception:
                            pass

                if not has_wikilink and not has_backlink:
                    orphaned.append(str(note.relative_to(self.vault_dir)))
            except Exception:
                pass

        return orphaned[:50]  # Limit to first 50

    def _find_duplicate_notes(self) -> List[str]:
        """Find vault notes with similar names (potential duplicates)."""
        duplicates = []
        if not self.vault_dir.exists():
            return duplicates

        all_notes = list(self.vault_dir.rglob("*.md"))
        names = [note.stem.lower().replace("-", "_").replace(" ", "_") for note in all_notes]

        seen = {}
        for i, name in enumerate(names):
            if name in seen:
                duplicates.append(str(all_notes[i].relative_to(self.vault_dir)))
                if seen[name] not in duplicates:
                    duplicates.append(seen[name])
            else:
                seen[name] = str(all_notes[i].relative_to(self.vault_dir))

        return duplicates[:20]  # Limit to first 20

    def _find_unused_tools(self) -> List[str]:
        """Find tools that have no vault documentation."""
        unused = []
        tools_dir = self.repo_dir / "ouroboros" / "tools"
        if not tools_dir.exists():
            return unused

        tool_files = list(tools_dir.glob("*_tools.py"))
        vault_tools_dir = self.vault_dir / "tools"

        for tool_file in tool_files:
            tool_name = tool_file.stem.replace("_tools", "")
            # Check if there's a corresponding vault note
            if vault_tools_dir.exists():
                matching_notes = list(vault_tools_dir.glob(f"*{tool_name}*"))
                if not matching_notes:
                    unused.append(tool_name)

        return unused

    def _generate_recommendations(self, report: WorkspaceReport) -> List[str]:
        """Generate workspace organization recommendations."""
        recommendations = []

        # Module count recommendation
        if report.total_modules > 100:
            recommendations.append(
                f"⚠️ {report.total_modules} modules exceeds minimalism budget (100). "
                "Consider consolidating or decomposing."
            )

        # Vault notes recommendations
        tools_notes = report.vault_by_category.get("tools", 0)
        if tools_notes > 50:
            recommendations.append(
                f"⚠️ {tools_notes} tool notes in vault (recommended: <50). "
                "Most are auto-generated and unused. Consider cleanup."
            )

        # Memory coherence recommendations
        core_memory = {"identity.md", "scratchpad.md"}
        extra_memory = set(report.memory_files) - core_memory
        if extra_memory:
            recommendations.append(
                f"ℹ️ Extra memory files: {', '.join(extra_memory)}. "
                "Per BIBLE.md, memory/ should only contain identity.md and scratchpad.md. "
                "Move other files to appropriate locations."
            )

        # Orphaned notes recommendation
        if report.orphaned_notes:
            recommendations.append(
                f"ℹ️ {len(report.orphaned_notes)} orphaned vault notes found. "
                "Consider adding wikilinks or removing unused notes."
            )

        # Duplicate notes recommendation
        if report.duplicate_notes:
            recommendations.append(
                f"⚠️ {len(report.duplicate_notes)} potential duplicate vault notes. "
                "Merge or remove duplicates to maintain coherence."
            )

        # State directory recommendation
        if not self.state_dir.exists():
            self.state_dir.mkdir(parents=True, exist_ok=True)
            recommendations.append("✅ Created .jo_state/ directory for transient state")

        return recommendations

    def cleanup_vault_tools(self, dry_run: bool = True) -> Dict[str, Any]:
        """Clean up auto-generated tool documentation in vault."""
        vault_tools_dir = self.vault_dir / "tools"
        if not vault_tools_dir.exists():
            return {"action": "none", "message": "No vault/tools directory"}

        tool_files = list((self.repo_dir / "ouroboros" / "tools").glob("*_tools.py"))
        active_tools = {f.stem.replace("_tools", "") for f in tool_files}

        notes = list(vault_tools_dir.glob("*.md"))
        to_remove = []
        to_keep = []

        for note in notes:
            note_name = note.stem.lower().replace("-", "_").replace(" ", "_")
            # Check if this note corresponds to an active tool
            is_active = any(tool in note_name for tool in active_tools)
            if is_active:
                to_keep.append(note.name)
            else:
                to_remove.append(note.name)

        result = {
            "total_notes": len(notes),
            "to_keep": len(to_keep),
            "to_remove": len(to_remove),
            "removed_files": to_remove if not dry_run else [],
            "kept_files": to_keep,
        }

        if not dry_run and to_remove:
            for name in to_remove:
                (vault_tools_dir / name).unlink()
            result["action"] = "removed"
            result["message"] = f"Removed {len(to_remove)} unused tool notes"
        elif dry_run:
            result["action"] = "dry_run"
            result["message"] = f"Would remove {len(to_remove)} unused tool notes"

        return result

    def consolidate_memory(self, dry_run: bool = True) -> Dict[str, Any]:
        """Consolidate memory files according to BIBLE.md principles."""
        result = {"actions": [], "moved": [], "warnings": []}

        if not self.memory_dir.exists():
            return result

        core_memory = {"identity.md", "scratchpad.md"}
        extra_files = [f for f in self.memory_dir.iterdir() if f.is_file() and f.name not in core_memory]

        for f in extra_files:
            if f.name.endswith(".json"):
                # JSON files should stay in memory/ (cerebrum, buglog, etc.)
                result["warnings"].append(f"ℹ️ {f.name} is JSON data - keeping in memory/ (not a text memory file)")
            elif f.name.endswith(".jsonl"):
                # JSONL files are logs - keep in memory/
                result["warnings"].append(f"ℹ️ {f.name} is a log file - keeping in memory/")
            elif f.is_dir() and f.name == "knowledge":
                # Knowledge directory - move to vault/concepts
                if not dry_run:
                    dest = self.vault_dir / "concepts" / "knowledge"
                    if f.exists():
                        shutil.move(str(f), str(dest))
                    result["moved"].append(f"{f.name} -> vault/concepts/knowledge")
                else:
                    result["actions"].append(f"Would move {f.name} -> vault/concepts/knowledge")
            else:
                # Other files - move to vault/journal
                if not dry_run:
                    dest = self.vault_dir / "journal" / f.name
                    shutil.move(str(f), str(dest))
                    result["moved"].append(f"{f.name} -> vault/journal/{f.name}")
                else:
                    result["actions"].append(f"Would move {f.name} -> vault/journal/{f.name}")

        return result

    def sync_tools_to_vault(self, dry_run: bool = True) -> Dict[str, Any]:
        """Ensure all active tools have vault documentation."""
        result = {"created": [], "existing": [], "missing": []}

        tools_dir = self.repo_dir / "ouroboros" / "tools"
        vault_tools_dir = self.vault_dir / "tools"

        if not tools_dir.exists():
            return result

        vault_tools_dir.mkdir(parents=True, exist_ok=True)

        tool_files = list(tools_dir.glob("*_tools.py"))
        for tool_file in tool_files:
            tool_name = tool_file.stem.replace("_tools", "")
            # Check if there's a corresponding vault note
            matching_notes = list(vault_tools_dir.glob(f"*{tool_name}*"))
            if matching_notes:
                result["existing"].append(tool_name)
            else:
                result["missing"].append(tool_name)
                if not dry_run:
                    # Create a minimal vault note for the tool
                    note_path = vault_tools_dir / f"{tool_name}.md"
                    note_path.write_text(
                        f"# {tool_name}\n\n"
                        f"Tool: {tool_name}\n"
                        f"Source: ouroboros/tools/{tool_file.name}\n\n"
                        f"## Description\n\n"
                        f"Auto-generated. Update with actual usage patterns.\n\n"
                        f"## Usage\n\n"
                        f"```\n"
                        f"# Tool usage examples go here\n"
                        f"```\n",
                        encoding="utf-8",
                    )
                    result["created"].append(tool_name)

        return result

    def generate_workspace_summary(self) -> str:
        """Generate a comprehensive workspace summary."""
        report = self.analyze()

        parts = [
            "## Workspace Organization Report\n",
            f"**Generated**: {datetime.now().isoformat()}\n",
            f"**Modules**: {report.total_modules} (ouroboros/)",
            f"**Tool Modules**: {report.total_tools} (ouroboros/tools/)",
            f"**Vault Notes**: {report.total_vault_notes} total",
        ]

        parts.append("\n### Vault by Category")
        for category, count in sorted(report.vault_by_category.items()):
            parts.append(f"- {category}: {count} notes")

        parts.append("\n### Memory Files")
        for f in report.memory_files:
            parts.append(f"- {f}")

        if report.recommendations:
            parts.append("\n### Recommendations")
            for rec in report.recommendations:
                parts.append(f"- {rec}")

        return "\n".join(parts)


# Global workspace organizer instance
_organizer: Optional[WorkspaceOrganizer] = None


def get_organizer(repo_dir: Optional[pathlib.Path] = None) -> WorkspaceOrganizer:
    """Get or create the global workspace organizer."""
    global _organizer
    if _organizer is None:
        if repo_dir is None:
            repo_dir = pathlib.Path.cwd()
        _organizer = WorkspaceOrganizer(repo_dir)
    return _organizer
