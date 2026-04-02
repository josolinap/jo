"""Scanning functions for neural map construction.

Extracted from tools/neural_map.py (Principle 5: Minimalism).
Handles: codebase scanning, vault scanning, tool scanning, unified map building.
"""

from __future__ import annotations

import logging
import pathlib
import re
from typing import Any, Optional

from ouroboros.tools.neural_map_models import Concept, NeuralMap

log = logging.getLogger(__name__)


def _scan_codebase(ctx: Any, graph: Optional[Any] = None) -> NeuralMap:
    """Scan codebase using AST-based codebase_graph (not regex)."""
    from ouroboros.codebase_graph import scan_repo

    neural_map = NeuralMap()
    repo_dir = pathlib.Path(ctx.repo_dir)

    if graph is None:
        graph = scan_repo(repo_dir=repo_dir, max_files=200)

    for node in graph.nodes.values():
        concept = Concept(
            id=node.id,
            name=node.name,
            type=node.type,
            path=node.file_path,
            content=node.summary,
            tags=[node.layer] if node.layer else [],
        )
        neural_map.add_concept(concept)

    for edge in graph.edges:
        neural_map.add_connection(
            source=edge.source,
            target=edge.target,
            conn_type=edge.relation,
            strength=edge.confidence,
            confidence=edge.confidence,
        )

    return neural_map


def _scan_vault(ctx: Any) -> NeuralMap:
    """Scan vault notes and build neural map."""
    neural_map = NeuralMap()
    vault_dir = pathlib.Path(ctx.repo_path("vault"))

    if not vault_dir.exists():
        return neural_map

    for md_file in vault_dir.rglob("*.md"):
        if md_file.name.startswith("."):
            continue

        rel_path = md_file.relative_to(vault_dir)
        rel_path_str = str(rel_path).replace("\\", "/").replace(".md", "")
        concept_id = f"vault/{rel_path_str}"

        try:
            content = md_file.read_text(encoding="utf-8")
        except Exception:
            continue

        tags = re.findall(r"tags?:\s*\[([^\]]+)\]", content) or []
        tags = [t.strip() for t in " ".join(tags).split(",") if t.strip()]

        concept = Concept(
            id=concept_id,
            name=md_file.stem,
            type="concept",
            path=str(rel_path),
            content=content[:500],
            tags=tags,
        )
        neural_map.add_concept(concept)

        wikilinks = re.findall(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", content)
        for link in wikilinks:
            link_stripped = link.strip()
            normalized_id = f"vault/{link_stripped.lower().replace(' ', '_')}"
            link_id = normalized_id if normalized_id in neural_map.concepts else link_stripped
            if not neural_map.concepts.get(link_id):
                neural_map.add_concept(Concept(id=link_id, name=link_stripped, type="concept"))
            neural_map.add_connection(concept_id, link_id, "link", strength=1.0, confidence=0.7)

        for tag in tags:
            tag_id = f"tag:{tag}"
            if not neural_map.concepts.get(tag_id):
                neural_map.add_concept(Concept(id=tag_id, name=tag, type="tag"))
            neural_map.add_connection(concept_id, tag_id, "tagged", strength=0.5, confidence=0.5)

    return neural_map


def _scan_tools(ctx: Any) -> NeuralMap:
    """Scan tool definitions and map dependencies."""
    neural_map = NeuralMap()
    repo_dir = pathlib.Path(ctx.repo_dir)
    tools_dir = repo_dir / "ouroboros" / "tools"

    for py_file in tools_dir.glob("*.py"):
        if py_file.stem.startswith("_"):
            continue

        concept_id = f"tool:{py_file.stem}"
        try:
            content = py_file.read_text(encoding="utf-8")
        except Exception:
            continue

        tool_name = re.search(r'name[=:]["\']([\w_]+)["\']', content)
        tool_name = tool_name.group(1) if tool_name else py_file.stem

        concept = Concept(
            id=concept_id,
            name=tool_name,
            type="tool",
            path=str(py_file.relative_to(repo_dir)),
            content=content[:300],
        )
        neural_map.add_concept(concept)

        registry_match = re.search(r'"(\w+)"', content)
        if registry_match:
            neural_map.add_connection(concept_id, "tool_registry", "registered", strength=0.5)

    neural_map.add_concept(Concept(id="tool_registry", name="ToolRegistry", type="component"))
    return neural_map


def _build_unified_map(ctx: Any, graph: Optional[Any] = None) -> NeuralMap:
    """Build unified neural map from all sources."""
    code_map = _scan_codebase(ctx, graph=graph)
    vault_map = _scan_vault(ctx)
    tool_map = _scan_tools(ctx)

    unified = NeuralMap()

    for concept in (
        list(code_map.concepts.values()) + list(vault_map.concepts.values()) + list(tool_map.concepts.values())
    ):
        unified.add_concept(concept)

    for conn in code_map.connections + vault_map.connections + tool_map.connections:
        unified.add_connection(conn.source, conn.target, conn.type, conn.strength, conn.confidence)

    return unified
