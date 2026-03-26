"""Knowledge discovery — fills gaps in Jo's understanding.

Scans ontology, neural map, vault, and codebase graph for gaps.
Provides consciousness with a systematic workflow to discover and fill them.

Gap types:
- orphan_concepts: concepts with no connections
- disconnected_tools: tools not linked to any task/usage pattern
- missing_ontology: task types without tool associations
- stale_vault: vault notes not updated recently
- unlinked_principles: BIBLE.md principles without implementation links
- missing_crossrefs: concepts that should be connected but aren't

Consciousness uses this to proactively improve its understanding.
"""

from __future__ import annotations

import logging
import pathlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


@dataclass
class KnowledgeGap:
    """A specific gap in Jo's knowledge."""

    gap_type: str  # orphan_concept, disconnected_tool, missing_ontology, etc.
    description: str
    severity: float  # 0.0-1.0
    fillable: bool  # Can we fill this gap with available tools?
    suggested_action: str  # What to do about it
    related_concepts: List[str] = field(default_factory=list)


class KnowledgeDiscovery:
    """Systematic gap-filling engine for consciousness."""

    def __init__(self, repo_dir: pathlib.Path, drive_root: pathlib.Path):
        self._repo_dir = repo_dir
        self._drive_root = drive_root

    def scan_all(self) -> List[KnowledgeGap]:
        """Scan all knowledge structures and return prioritized gaps."""
        gaps: List[KnowledgeGap] = []

        gaps.extend(self._scan_neural_map())
        gaps.extend(self._scan_ontology())
        gaps.extend(self._scan_vault())
        gaps.extend(self._scan_codebase())

        # Sort by severity (highest first)
        gaps.sort(key=lambda g: -g.severity)
        return gaps

    def _scan_neural_map(self) -> List[KnowledgeGap]:
        """Find gaps in the neural map (orphaned concepts, missing connections)."""
        gaps: List[KnowledgeGap] = []
        try:
            from ouroboros.tools.neural_map import _build_unified_map
            from ouroboros.tools.registry import ToolContext

            ctx = ToolContext(repo_dir=self._repo_dir, drive_root=self._drive_root)
            neural_map = _build_unified_map(ctx)

            # Orphaned concepts (no connections)
            orphan_count = 0
            orphan_names = []
            for concept_id, concept in neural_map.concepts.items():
                if not neural_map._adjacency.get(concept_id):
                    orphan_count += 1
                    if len(orphan_names) < 5:
                        orphan_names.append(concept.name)

            if orphan_count > 0:
                gaps.append(
                    KnowledgeGap(
                        gap_type="orphan_concept",
                        description=f"{orphan_count} concepts have no connections: {', '.join(orphan_names)}",
                        severity=min(0.8, 0.1 + orphan_count * 0.05),
                        fillable=True,
                        suggested_action="Use vault search and codebase analysis to find relationships between these concepts and existing ones",
                        related_concepts=orphan_names,
                    )
                )

            # Disconnected tools (tools not linked to any usage)
            tool_gaps = []
            for concept_id, concept in neural_map.concepts.items():
                if concept.type == "tool" and not neural_map._adjacency.get(concept_id):
                    tool_gaps.append(concept.name)

            if tool_gaps:
                gaps.append(
                    KnowledgeGap(
                        gap_type="disconnected_tool",
                        description=f"{len(tool_gaps)} tools not linked to any usage pattern: {', '.join(tool_gaps[:5])}",
                        severity=0.5,
                        fillable=True,
                        suggested_action="Record tool usage in ontology tracker when tools are used",
                        related_concepts=tool_gaps[:5],
                    )
                )

            # Principles without implementation links
            principle_gaps = []
            for concept_id, concept in neural_map.concepts.items():
                if "principle" in concept_id.lower():
                    if not neural_map._adjacency.get(concept_id):
                        principle_gaps.append(concept.name)

            if principle_gaps:
                gaps.append(
                    KnowledgeGap(
                        gap_type="unlinked_principle",
                        description=f"{len(principle_gaps)} principles lack implementation links: {', '.join(principle_gaps)}",
                        severity=0.7,
                        fillable=True,
                        suggested_action="Search codebase for files that implement each principle and create connections",
                        related_concepts=principle_gaps,
                    )
                )

            # Low connectivity clusters
            clusters = neural_map.get_clusters()
            for i, cluster in enumerate(clusters):
                if len(cluster) < 3:
                    members = [neural_map.concepts[cid].name for cid in cluster if cid in neural_map.concepts]
                    if members:
                        gaps.append(
                            KnowledgeGap(
                                gap_type="weak_cluster",
                                description=f"Cluster {i + 1} has only {len(cluster)} members: {', '.join(members)}",
                                severity=0.3,
                                fillable=True,
                                suggested_action="Find related concepts and vault notes to strengthen this cluster",
                                related_concepts=members,
                            )
                        )

        except Exception as e:
            log.debug("Neural map scan failed: %s", e)

        return gaps

    def _scan_ontology(self) -> List[KnowledgeGap]:
        """Find gaps in the ontology tracker."""
        gaps: List[KnowledgeGap] = []
        try:
            from ouroboros.codebase_graph import get_ontology_tracker

            tracker = get_ontology_tracker()

            # Check for task types with low tool coverage
            for task_type, tools in tracker._tool_usage.items():
                if len(tools) < 2:
                    gaps.append(
                        KnowledgeGap(
                            gap_type="missing_ontology",
                            description=f"Task type '{task_type}' uses only {len(tools)} tools",
                            severity=0.4,
                            fillable=True,
                            suggested_action=f"Record more tool usage for {task_type} tasks",
                            related_concepts=[task_type],
                        )
                    )

            # Check for tools never used
            all_tools_used = set()
            for tools in tracker._tool_usage.values():
                all_tools_used.update(tools.keys())

            try:
                from ouroboros.tools.registry import ToolRegistry

                registry = ToolRegistry(repo_dir=self._repo_dir, drive_root=self._drive_root)
                all_tools = {s["function"]["name"] for s in registry.schemas()}
                unused_tools = all_tools - all_tools_used
                if len(unused_tools) > 5:
                    gaps.append(
                        KnowledgeGap(
                            gap_type="unused_tool",
                            description=f"{len(unused_tools)} tools never recorded in ontology: {', '.join(list(unused_tools)[:5])}",
                            severity=0.3,
                            fillable=False,  # Requires actual usage to fill
                            suggested_action="These tools may be niche or need better integration",
                            related_concepts=list(unused_tools)[:5],
                        )
                    )
            except Exception:
                pass

        except Exception as e:
            log.debug("Ontology scan failed: %s", e)

        return gaps

    def _scan_vault(self) -> List[KnowledgeGap]:
        """Find gaps in the vault (stale notes, missing links)."""
        gaps: List[KnowledgeGap] = []
        try:
            import time

            vault_dir = self._repo_dir / "vault"
            if not vault_dir.exists():
                return gaps

            # Check for notes without wikilinks
            unlinked_notes = []
            for md_file in vault_dir.rglob("*.md"):
                content = md_file.read_text(encoding="utf-8", errors="replace")
                if "[[" not in content and md_file.stem not in ("README", "index"):
                    unlinked_notes.append(md_file.stem)

            if len(unlinked_notes) > 10:
                gaps.append(
                    KnowledgeGap(
                        gap_type="unlinked_vault_note",
                        description=f"{len(unlinked_notes)} vault notes have no wikilinks: {', '.join(unlinked_notes[:5])}",
                        severity=0.4,
                        fillable=True,
                        suggested_action="Read each note and add wikilinks to related concepts",
                        related_concepts=unlinked_notes[:5],
                    )
                )

            # Check concepts directory specifically
            concepts_dir = vault_dir / "concepts"
            if concepts_dir.exists():
                concept_files = list(concepts_dir.glob("*.md"))
                linked_concepts = 0
                for cf in concept_files:
                    content = cf.read_text(encoding="utf-8", errors="replace")
                    if "[[" in content:
                        linked_concepts += 1

                if concept_files:
                    link_ratio = linked_concepts / len(concept_files)
                    if link_ratio < 0.5:
                        gaps.append(
                            KnowledgeGap(
                                gap_type="low_concept_connectivity",
                                description=f"Only {linked_concepts}/{len(concept_files)} concept notes have wikilinks ({link_ratio:.0%})",
                                severity=0.5,
                                fillable=True,
                                suggested_action="Add wikilinks between related concepts to strengthen the knowledge graph",
                            )
                        )

        except Exception as e:
            log.debug("Vault scan failed: %s", e)

        return gaps

    def _scan_codebase(self) -> List[KnowledgeGap]:
        """Find gaps in codebase understanding."""
        gaps: List[KnowledgeGap] = []
        try:
            # Check for files not in any graph analysis
            tools_dir = self._repo_dir / "ouroboros" / "tools"
            if tools_dir.exists():
                tool_files = [f.stem for f in tools_dir.glob("*.py") if not f.stem.startswith("_")]
                # This is informational - the codebase graph may not cover all tools
                if len(tool_files) > 20:
                    gaps.append(
                        KnowledgeGap(
                            gap_type="codebase_coverage",
                            description=f"{len(tool_files)} tool modules exist - codebase graph may not cover all relationships",
                            severity=0.2,
                            fillable=False,
                            suggested_action="Run codebase_analyze periodically to update the graph",
                        )
                    )

        except Exception as e:
            log.debug("Codebase scan failed: %s", e)

        return gaps

    def get_discovery_report(self) -> str:
        """Generate a human-readable discovery report."""
        gaps = self.scan_all()

        lines = [
            "## Knowledge Discovery Report",
            "",
            f"**Total gaps found:** {len(gaps)}",
        ]

        # Group by type
        by_type: Dict[str, List[KnowledgeGap]] = {}
        for gap in gaps:
            by_type.setdefault(gap.gap_type, []).append(gap)

        for gap_type, type_gaps in sorted(by_type.items(), key=lambda x: -sum(g.severity for g in x[1])):
            total_severity = sum(g.severity for g in type_gaps)
            fillable = sum(1 for g in type_gaps if g.fillable)
            lines.append(f"\n### {gap_type.replace('_', ' ').title()} ({len(type_gaps)} gaps)")
            lines.append(f"**Total severity:** {total_severity:.1f} | **Fillable:** {fillable}/{len(type_gaps)}")
            for g in type_gaps[:3]:
                lines.append(f"- [{g.severity:.1f}] {g.description}")
                lines.append(f"  Action: {g.suggested_action}")

        # Top 3 actionable items
        fillable_gaps = [g for g in gaps if g.fillable]
        if fillable_gaps:
            lines.append("\n### Top Actionable Gaps")
            for g in fillable_gaps[:3]:
                lines.append(f"1. [{g.severity:.1f}] {g.suggested_action}")

        return "\n".join(lines)
