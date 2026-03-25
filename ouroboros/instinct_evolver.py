"""Instinct Evolution — auto-create vault skills from successful temporal patterns.

Inspired by ECC's instinct-based learning with confidence scoring.
After a tool pattern succeeds N+ times, it becomes a "learned instinct"
and gets recorded as a vault skill note.

Flow:
    temporal_learning records patterns →
    instinct_evolver checks thresholds →
    creates vault note with reusable skill

Three stages (from ECC):
    Pending: pattern observed but not confirmed (< 3 uses)
    Confirmed: pattern succeeded 3+ times, high confidence
    Evolved: pattern converted to vault skill, usable by Jo
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

# Thresholds
CONFIRM_THRESHOLD = 3  # uses before pattern is "confirmed"
EVOLVE_THRESHOLD = 5  # uses before pattern evolves to vault skill
MIN_CONFIDENCE = 0.7  # minimum confidence for evolution


@dataclass
class Instinct:
    """A learned instinct (tool pattern with confidence)."""

    task_type: str
    tool_sequence: List[str]
    success_count: int
    failure_count: int
    confidence: float
    stage: str  # "pending", "confirmed", "evolved"
    vault_note_path: Optional[str] = None

    @property
    def total_uses(self) -> int:
        return self.success_count + self.failure_count

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_type": self.task_type,
            "tool_sequence": self.tool_sequence,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "confidence": self.confidence,
            "stage": self.stage,
            "vault_note_path": self.vault_note_path,
        }


class InstinctEvolver:
    """Evolves successful tool patterns into vault skills.

    Periodically checks temporal_learning patterns and promotes
    high-confidence, frequently-used patterns to "instincts" that
    get recorded as vault notes.
    """

    def __init__(self, persistence_path: Optional[Path] = None):
        self._instincts: Dict[str, Instinct] = {}  # key -> instinct
        self._persistence_path = persistence_path
        if persistence_path and persistence_path.exists():
            self._load()

    def evolve_from_learner(self, learner: Any, repo_dir: Path) -> List[str]:
        """Check temporal learner patterns and evolve confirmed ones.

        Returns list of newly evolved instinct descriptions.
        """
        from ouroboros.temporal_learning import TemporalToolLearner

        if not isinstance(learner, TemporalToolLearner):
            return []

        evolved = []

        for tool, task_patterns in learner._patterns.items():
            for task_type, pattern in task_patterns.items():
                key = f"{task_type}:{tool}"

                # Update or create instinct
                if key in self._instincts:
                    inst = self._instincts[key]
                    inst.success_count = pattern.success_count
                    inst.failure_count = pattern.failure_count
                    inst.confidence = pattern.score
                else:
                    inst = Instinct(
                        task_type=task_type,
                        tool_sequence=[tool],
                        success_count=pattern.success_count,
                        failure_count=pattern.failure_count,
                        confidence=pattern.score,
                        stage="pending",
                    )
                    self._instincts[key] = inst

                # Stage promotion
                old_stage = inst.stage
                if inst.total_uses >= EVOLVE_THRESHOLD and inst.confidence >= MIN_CONFIDENCE:
                    if inst.stage != "evolved":
                        inst.stage = "evolved"
                        note_path = self._create_vault_skill(inst, repo_dir)
                        inst.vault_note_path = note_path
                        evolved.append(f"{task_type}/{tool}: evolved to vault skill")
                elif inst.total_uses >= CONFIRM_THRESHOLD and inst.confidence >= MIN_CONFIDENCE:
                    if inst.stage == "pending":
                        inst.stage = "confirmed"

        if self._persistence_path:
            self._save()

        return evolved

    def get_instincts(self, stage: Optional[str] = None) -> List[Instinct]:
        """Get instincts, optionally filtered by stage."""
        if stage:
            return [i for i in self._instincts.values() if i.stage == stage]
        return list(self._instincts.values())

    def get_report(self) -> str:
        """Human-readable instinct report."""
        if not self._instincts:
            return "No instincts learned yet."

        pending = self.get_instincts("pending")
        confirmed = self.get_instincts("confirmed")
        evolved = self.get_instincts("evolved")

        lines = [
            "## Instinct Evolution Report",
            "",
            f"**Total:** {len(self._instincts)} instincts",
            f"**Pending:** {len(pending)} (need more uses)",
            f"**Confirmed:** {len(confirmed)} (ready to evolve)",
            f"**Evolved:** {len(evolved)} (vault skills created)",
            "",
        ]

        if evolved:
            lines.append("### Evolved Instincts (Vault Skills)")
            for inst in evolved:
                lines.append(
                    f"- **{inst.task_type}/{inst.tool_sequence[0]}**: {inst.confidence:.0%} confidence, {inst.total_uses} uses"
                )
                if inst.vault_note_path:
                    lines.append(f"  Vault: {inst.vault_note_path}")
            lines.append("")

        if confirmed:
            lines.append("### Confirmed (Ready to Evolve)")
            for inst in confirmed:
                lines.append(
                    f"- **{inst.task_type}/{inst.tool_sequence[0]}**: {inst.confidence:.0%} confidence, {inst.total_uses} uses"
                )

        return "\n".join(lines)

    def _create_vault_skill(self, inst: Instinct, repo_dir: Path) -> str:
        """Create a vault note documenting the evolved instinct."""
        try:
            from ouroboros.vault_manager import VaultManager

            vault = VaultManager(repo_dir / "vault")
            vault.ensure_vault_structure()

            tool = inst.tool_sequence[0]
            title = f"Learned: {inst.task_type}/{tool}"
            content = f"""## Auto-Evolved Instinct

**Task Type:** {inst.task_type}
**Primary Tool:** `{tool}`
**Confidence:** {inst.confidence:.0%}
**Uses:** {inst.total_uses} ({inst.success_count} success, {inst.failure_count} failure)

## Recommended Pattern

When working on **{inst.task_type}** tasks, start with `{tool}`.

This pattern was learned from {inst.total_uses} observations with {inst.confidence:.0%} success rate.

## Source

Evolved automatically by InstinctEvolver from temporal tool learning data."""

            note_path = vault.upsert_note(
                title=title,
                folder="tools",
                content=content,
                tags=["instinct", inst.task_type, "auto-evolved"],
                type="skill",
                status="active",
            )

            log.info("[Instinct] Evolved: %s/%s → %s", inst.task_type, tool, note_path)
            return note_path
        except Exception as e:
            log.warning("[Instinct] Failed to create vault skill: %s", e)
            return ""

    def _save(self) -> None:
        try:
            data = {k: v.to_dict() for k, v in self._instincts.items()}
            self._persistence_path.parent.mkdir(parents=True, exist_ok=True)
            self._persistence_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            log.debug("Failed to save instincts: %s", e)

    def _load(self) -> None:
        try:
            data = json.loads(self._persistence_path.read_text(encoding="utf-8"))
            for key, i_data in data.items():
                self._instincts[key] = Instinct(
                    task_type=i_data.get("task_type", ""),
                    tool_sequence=i_data.get("tool_sequence", []),
                    success_count=i_data.get("success_count", 0),
                    failure_count=i_data.get("failure_count", 0),
                    confidence=i_data.get("confidence", 0.0),
                    stage=i_data.get("stage", "pending"),
                    vault_note_path=i_data.get("vault_note_path"),
                )
        except Exception as e:
            log.debug("Failed to load instincts: %s", e)


# Global singleton
_evolver: Optional[InstinctEvolver] = None


def get_evolver(repo_dir: Optional[Path] = None) -> InstinctEvolver:
    global _evolver
    if _evolver is None:
        path = repo_dir / ".jo_data" / "instincts.json" if repo_dir else None
        _evolver = InstinctEvolver(persistence_path=path)
    return _evolver
