"""Vault Improvements — guardrails, auto-linking, auto-fixing."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ouroboros.vault_engine import VaultGraphEngine, VaultNote, get_vault_engine

log = logging.getLogger(__name__)


@dataclass
class LinkSuggestion:
    """A suggested link between notes."""

    source_path: str  # Note that needs the link
    target_path: str  # Note to link to
    similarity: float  # Content similarity score
    reason: str  # Why this link is suggested
    confidence: float  # How confident we are

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source_path,
            "target": self.target_path,
            "similarity": round(self.similarity, 3),
            "reason": self.reason,
            "confidence": round(self.confidence, 3),
        }


@dataclass
class QualityViolation:
    """A quality violation found in a note."""

    note_path: str
    violation_type: str  # "missing_frontmatter", "no_tags", "stale", "orphan"
    severity: str  # "error", "warning", "info"
    message: str
    suggested_fix: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "note_path": self.note_path,
            "type": self.violation_type,
            "severity": self.severity,
            "message": self.message,
            "suggested_fix": self.suggested_fix,
        }


@dataclass
class VaultHealthReport:
    """Complete vault health report."""

    timestamp: str
    total_notes: int
    orphan_count: int
    stale_count: int
    missing_frontmatter: int
    missing_tags: int
    quality_score: float  # 0-100
    violations: List[QualityViolation] = field(default_factory=list)
    link_suggestions: List[LinkSuggestion] = field(default_factory=list)
    improvement_actions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "total_notes": self.total_notes,
            "orphan_count": self.orphan_count,
            "stale_count": self.stale_count,
            "missing_frontmatter": self.missing_frontmatter,
            "missing_tags": self.missing_tags,
            "quality_score": round(self.quality_score, 1),
            "violations": [v.to_dict() for v in self.violations],
            "link_suggestions": [s.to_dict() for s in self.link_suggestions],
            "improvement_actions": self.improvement_actions,
        }


class VaultGuardrails:
    """Quality guardrails for vault maintenance.

    Prevents quality drift and maintains vault integrity.
    """

    # Quality thresholds
    MAX_ORPHAN_PERCENTAGE = 0.3  # Max 30% orphans
    MAX_STALE_PERCENTAGE = 0.2  # Max 20% stale notes
    MIN_WORD_COUNT = 50  # Minimum words per note
    REQUIRE_FRONTMATTER = True  # Require YAML frontmatter
    REQUIRE_TAGS = False  # Tags are optional

    def __init__(self, engine: VaultGraphEngine):
        self._engine = engine

    def check_note(self, note: VaultNote) -> List[QualityViolation]:
        """Check a single note for quality violations."""
        violations = []

        # Check frontmatter
        if self.REQUIRE_FRONTMATTER and not note.frontmatter:
            violations.append(
                QualityViolation(
                    note_path=note.path,
                    violation_type="missing_frontmatter",
                    severity="warning",
                    message="Note has no YAML frontmatter",
                    suggested_fix="Add frontmatter with description, tags, and created date",
                )
            )

        # Check tags
        if self.REQUIRE_TAGS and not note.tags:
            violations.append(
                QualityViolation(
                    note_path=note.path,
                    violation_type="missing_tags",
                    severity="info",
                    message="Note has no tags",
                    suggested_fix="Add tags to categorize the note",
                )
            )

        # Check word count
        if note.word_count < self.MIN_WORD_COUNT:
            violations.append(
                QualityViolation(
                    note_path=note.path,
                    violation_type="low_word_count",
                    severity="warning",
                    message=f"Note has only {note.word_count} words (minimum: {self.MIN_WORD_COUNT})",
                    suggested_fix="Expand the note with more detail",
                )
            )

        # Check if orphan
        if note.is_orphan:
            violations.append(
                QualityViolation(
                    note_path=note.path,
                    violation_type="orphan",
                    severity="error",
                    message="Note has no incoming or outgoing links",
                    suggested_fix="Link to related notes using [[wikilinks]]",
                )
            )

        # Check if stale
        if note.is_stale:
            violations.append(
                QualityViolation(
                    note_path=note.path,
                    violation_type="stale",
                    severity="info",
                    message="Note hasn't been modified in over 30 days",
                    suggested_fix="Review and update if needed",
                )
            )

        return violations

    def check_all_notes(self) -> List[QualityViolation]:
        """Check all notes for quality violations."""
        if not self._engine._graph:
            self._engine.build_graph()

        all_violations = []
        for note in self._engine._graph.notes.values():
            violations = self.check_note(note)
            all_violations.extend(violations)

        return all_violations

    def calculate_quality_score(self, violations: List[QualityViolation], total_notes: int = 0) -> float:
        """Calculate overall vault quality score (0-100).

        More realistic scoring based on:
        - Percentage of notes with issues
        - Severity weighting
        - Diminishing returns for many violations
        """
        if not violations:
            return 100.0

        if total_notes == 0:
            total_notes = len(set(v.note_path for v in violations))

        # Count violations by type
        orphan_count = sum(1 for v in violations if v.violation_type == "orphan")
        frontmatter_count = sum(1 for v in violations if v.violation_type == "missing_frontmatter")
        low_word_count = sum(1 for v in violations if v.violation_type == "low_word_count")
        other_count = len(violations) - orphan_count - frontmatter_count - low_word_count

        # Calculate penalties (lower = better score)
        # Orphan penalty: 3 points per orphan (most impactful)
        orphan_penalty = orphan_count * 3

        # Frontmatter penalty: 2 points per missing frontmatter
        frontmatter_penalty = frontmatter_count * 2

        # Low word count penalty: 0.05 points per low word count (minimal impact)
        # Many notes are legitimately short (tool docs, journal entries)
        low_word_penalty = low_word_count * 0.05

        # Other penalties: 1 point each
        other_penalty = other_count * 1

        total_penalty = orphan_penalty + frontmatter_penalty + low_word_penalty + other_penalty

        # Normalize based on total notes (more realistic)
        # Max penalty would be if ALL notes had all issues
        max_possible_penalty = total_notes * 6.5  # orphan + frontmatter + low_word per note

        # Calculate score
        if max_possible_penalty > 0:
            score = max(0, 100 - (total_penalty / max_possible_penalty * 100))
        else:
            score = 100.0

        return score


class VaultAutoLinker:
    """Automatically suggest and create links for orphan notes.

    Reduces orphan count by suggesting related notes to link.
    """

    def __init__(self, engine: VaultGraphEngine):
        self._engine = engine

    def suggest_links_for_note(self, note: VaultNote, max_suggestions: int = 5) -> List[LinkSuggestion]:
        """Suggest links for a single note."""
        if not self._engine._graph:
            self._engine.build_graph()

        suggestions = []
        note_words = set(note.content.lower().split())

        for other_path, other_note in self._engine._graph.notes.items():
            if other_path == note.path:
                continue
            if other_path in note.links:
                continue  # Already linked

            # Calculate similarity
            other_words = set(other_note.content.lower().split())
            overlap = len(note_words & other_words)
            total_words = len(note_words | other_words)
            similarity = overlap / max(total_words, 1)

            # Skip low similarity
            if similarity < 0.05:
                continue

            # Determine reason
            reason = ""
            if note.title.lower() in other_note.content.lower():
                reason = "Note title mentioned in content"
                similarity += 0.2
            elif other_note.title.lower() in note.content.lower():
                reason = "Related note title mentioned"
                similarity += 0.2
            elif any(tag in other_note.tags for tag in note.tags):
                reason = "Shared tags"
                similarity += 0.1
            else:
                reason = "Content similarity"

            confidence = min(1.0, similarity)

            suggestions.append(
                LinkSuggestion(
                    source_path=note.path,
                    target_path=other_path,
                    similarity=similarity,
                    reason=reason,
                    confidence=confidence,
                )
            )

        # Sort by similarity
        suggestions.sort(key=lambda s: s.similarity, reverse=True)
        return suggestions[:max_suggestions]

    def suggest_links_for_orphans(self, max_per_note: int = 3) -> List[LinkSuggestion]:
        """Suggest links for all orphan notes."""
        if not self._engine._graph:
            self._engine.build_graph()

        all_suggestions = []
        orphans = self._engine.detect_orphans()

        for orphan in orphans:
            suggestions = self.suggest_links_for_note(orphan, max_suggestions=max_per_note)
            all_suggestions.extend(suggestions)

        # Sort by confidence
        all_suggestions.sort(key=lambda s: s.confidence, reverse=True)
        return all_suggestions

    def create_link(self, source_path: str, target_path: str) -> bool:
        """Create a wikilink in the source note pointing to the target note."""
        if not self._engine._graph:
            self._engine.build_graph()

        source_note = self._engine._graph.get_note(source_path)
        target_note = self._engine._graph.get_note(target_path)

        if not source_note or not target_note:
            return False

        # Read source file
        source_file = self._engine._vault_dir / source_path
        if not source_file.exists():
            return False

        try:
            content = source_file.read_text(encoding="utf-8")

            # Check if link already exists
            link_text = f"[[{target_note.title}]]"
            if link_text in content:
                return False

            # Add link at the end of the note
            # Find the end of the content (before any trailing whitespace)
            content = content.rstrip()
            content += f"\n\n---\n## Related\n\n- {link_text}\n"

            source_file.write_text(content, encoding="utf-8")
            log.info(f"Created link: {source_path} -> {target_path}")
            return True

        except Exception as e:
            log.error(f"Failed to create link: {e}")
            return False


def get_vault_health_report(vault_dir: Optional[Path] = None) -> VaultHealthReport:
    """Generate a complete vault health report."""
    engine = get_vault_engine(vault_dir)
    guardrails = VaultGuardrails(engine)
    linker = VaultAutoLinker(engine)

    # Build graph
    graph = engine.build_graph()

    # Get metrics
    metrics = engine.get_quality_metrics()

    # Check violations
    violations = guardrails.check_all_notes()

    # Get link suggestions for orphans
    link_suggestions = linker.suggest_links_for_orphans(max_per_note=2)

    # Calculate quality score
    quality_score = guardrails.calculate_quality_score(violations, total_notes=metrics.total_notes)

    # Generate improvement actions
    actions = []
    if metrics.orphan_count > 0:
        actions.append(f"Link {metrics.orphan_count} orphan notes")
    if metrics.frontmatter_coverage < 0.5:
        actions.append(f"Add frontmatter to {int((1 - metrics.frontmatter_coverage) * metrics.total_notes)} notes")
    if metrics.tag_coverage < 0.5:
        actions.append(f"Add tags to {int((1 - metrics.tag_coverage) * metrics.total_notes)} notes")
    if metrics.stale_count > 0:
        actions.append(f"Review {metrics.stale_count} stale notes")

    return VaultHealthReport(
        timestamp=datetime.now().isoformat(),
        total_notes=metrics.total_notes,
        orphan_count=metrics.orphan_count,
        stale_count=metrics.stale_count,
        missing_frontmatter=metrics.total_notes - int(metrics.frontmatter_coverage * metrics.total_notes),
        missing_tags=metrics.total_notes - int(metrics.tag_coverage * metrics.total_notes),
        quality_score=quality_score,
        violations=violations,
        link_suggestions=link_suggestions,
        improvement_actions=actions,
    )


# ============================================================================
# PHASE 3A: Execute Improvements (Auto-Fix)
# ============================================================================


@dataclass
class ImprovementResult:
    """Result of executing an improvement."""

    note_path: str
    improvement_type: str  # "link_added", "frontmatter_added", "tag_added"
    success: bool
    message: str
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "note_path": self.note_path,
            "type": self.improvement_type,
            "success": self.success,
            "message": self.message,
            "details": self.details,
        }


class VaultAutoFixer:
    """Execute improvements to fix vault issues.

    Phase 3A: Actually applies fixes, not just suggestions.
    """

    def __init__(self, engine: VaultGraphEngine):
        self._engine = engine

    def fix_orphan_notes(self, max_fixes: int = 50) -> List[ImprovementResult]:
        """Auto-link orphan notes based on content similarity.

        Args:
            max_fixes: Maximum number of fixes to apply

        Returns:
            List of improvement results
        """
        if not self._engine._graph:
            self._engine.build_graph()

        linker = VaultAutoLinker(self._engine)
        suggestions = linker.suggest_links_for_orphans(max_per_note=1)

        results = []
        fixed_notes = set()

        for suggestion in suggestions[:max_fixes]:
            if suggestion.source_path in fixed_notes:
                continue

            # Only fix high-confidence suggestions
            if suggestion.confidence < 0.5:
                continue

            success = linker.create_link(
                suggestion.source_path,
                suggestion.target_path,
            )

            results.append(
                ImprovementResult(
                    note_path=suggestion.source_path,
                    improvement_type="link_added",
                    success=success,
                    message=f"Linked to {suggestion.target_path}" if success else "Failed to add link",
                    details={
                        "target": suggestion.target_path,
                        "similarity": suggestion.similarity,
                        "reason": suggestion.reason,
                    },
                )
            )

            if success:
                fixed_notes.add(suggestion.source_path)

        return results

    def add_frontmatter(self, note_path: str) -> ImprovementResult:
        """Add YAML frontmatter to a note that's missing it."""
        note_file = self._engine._vault_dir / note_path
        if not note_file.exists():
            return ImprovementResult(
                note_path=note_path,
                improvement_type="frontmatter_added",
                success=False,
                message="Note file not found",
            )

        try:
            content = note_file.read_text(encoding="utf-8")

            # Check if already has frontmatter
            if content.startswith("---"):
                return ImprovementResult(
                    note_path=note_path,
                    improvement_type="frontmatter_added",
                    success=False,
                    message="Note already has frontmatter",
                )

            # Generate frontmatter
            title = Path(note_path).stem
            # Try to get title from first heading
            for line in content.split("\n"):
                line = line.strip()
                if line.startswith("# "):
                    title = line[2:].strip()
                    break

            # Extract any existing tags from content
            tags = re.findall(r"#([a-zA-Z0-9_-]+)", content)
            tags_str = f"\n  - {chr(10) + '  - '.join(tags)}" if tags else " []"

            # Get folder for category
            folder = str(Path(note_path).parent)
            category = folder.split("/")[-1] if "/" in folder else folder.split("\\")[-1]

            # Create frontmatter
            frontmatter = f"""---
title: {title}
created: {datetime.now().strftime("%Y-%m-%d")}
category: {category}
tags: {tags_str}

---

"""
            new_content = frontmatter + content
            note_file.write_text(new_content, encoding="utf-8")

            return ImprovementResult(
                note_path=note_path,
                improvement_type="frontmatter_added",
                success=True,
                message=f"Added frontmatter with title '{title}'",
                details={"title": title, "category": category, "tags": tags},
            )

        except Exception as e:
            return ImprovementResult(
                note_path=note_path,
                improvement_type="frontmatter_added",
                success=False,
                message=f"Error: {e}",
            )

    def fix_missing_frontmatter(self, max_fixes: int = 20) -> List[ImprovementResult]:
        """Add frontmatter to notes missing it.

        Args:
            max_fixes: Maximum number of fixes to apply

        Returns:
            List of improvement results
        """
        if not self._engine._graph:
            self._engine.build_graph()

        results = []
        fixed_count = 0

        for path, note in self._engine._graph.notes.items():
            if fixed_count >= max_fixes:
                break

            if not note.frontmatter:
                result = self.add_frontmatter(path)
                results.append(result)
                if result.success:
                    fixed_count += 1

        return results

    def auto_fix_violations(self, max_fixes: int = 30) -> Dict[str, Any]:
        """Auto-fix vault quality violations.

        Applies fixes in priority order:
        1. Add frontmatter to notes missing it
        2. Link orphan notes (high confidence only)

        Args:
            max_fixes: Maximum total fixes to apply

        Returns:
            Summary of fixes applied
        """
        results = {
            "timestamp": datetime.now().isoformat(),
            "total_fixes": 0,
            "successful_fixes": 0,
            "failed_fixes": 0,
            "fixes_by_type": {},
            "details": [],
        }

        # Priority 1: Add frontmatter (most impactful)
        frontmatter_results = self.fix_missing_frontmatter(max_fixes // 2)
        for r in frontmatter_results:
            results["details"].append(r.to_dict())
            results["total_fixes"] += 1
            if r.success:
                results["successful_fixes"] += 1
                results["fixes_by_type"]["frontmatter_added"] = results["fixes_by_type"].get("frontmatter_added", 0) + 1
            else:
                results["failed_fixes"] += 1

        # Priority 2: Link orphan notes
        remaining = max_fixes - results["total_fixes"]
        if remaining > 0:
            link_results = self.fix_orphan_notes(remaining)
            for r in link_results:
                results["details"].append(r.to_dict())
                results["total_fixes"] += 1
                if r.success:
                    results["successful_fixes"] += 1
                    results["fixes_by_type"]["link_added"] = results["fixes_by_type"].get("link_added", 0) + 1
                else:
                    results["failed_fixes"] += 1

        return results


def execute_vault_improvements(
    vault_dir: Optional[Path] = None,
    max_fixes: int = 30,
) -> Dict[str, Any]:
    """Execute vault improvements (Phase 3A).

    This is the main entry point for auto-fixing vault issues.

    Args:
        vault_dir: Vault directory path
        max_fixes: Maximum number of fixes to apply

    Returns:
        Summary of improvements made
    """
    engine = get_vault_engine(vault_dir)
    fixer = VaultAutoFixer(engine)

    # Get initial state
    initial_report = get_vault_health_report(vault_dir)
    initial_score = initial_report.quality_score

    # Execute fixes
    results = fixer.auto_fix_violations(max_fixes)

    # Rebuild graph to reflect changes
    engine._graph = None  # Invalidate cache
    final_report = get_vault_health_report(vault_dir)
    final_score = final_report.quality_score

    # Add comparison to results
    results["quality_score_before"] = initial_score
    results["quality_score_after"] = final_score
    results["quality_improvement"] = final_score - initial_score

    return results


# ============================================================================
# PHASE 3B: Semantic Search & Knowledge Analysis
# ============================================================================
