"""Tool definitions for neural map.

Extracted from tools/neural_map.py (Principle 5: Minimalism).
Contains the get_tools() function that returns all neural map tool entries.
"""

from __future__ import annotations

import logging
import pathlib
from typing import List

from ouroboros.tools.registry import ToolContext

log = logging.getLogger(__name__)

# ToolEntry is defined in neural_map.py - we import it lazily to avoid circular imports
ToolEntry = None  # Will be set at import time


def _get_tool_entry_class():
    """Lazy import of ToolEntry to avoid circular imports."""
    global ToolEntry
    if ToolEntry is None:
        from ouroboros.tools.neural_map import ToolEntry as TE

        ToolEntry = TE
    return ToolEntry


def _discover_knowledge_gaps(ctx: ToolContext) -> str:
    """Scan all knowledge structures for gaps."""
    from ouroboros.knowledge_discovery import KnowledgeDiscovery

    repo_dir = pathlib.Path(ctx.repo_dir) if ctx.repo_dir else pathlib.Path(".")
    drive_root = pathlib.Path(ctx.drive_root) if ctx.drive_root else pathlib.Path(".")

    discovery = KnowledgeDiscovery(repo_dir=repo_dir, drive_root=drive_root)
    return discovery.get_discovery_report()


def get_tools() -> List:
    """Get neural mapping tools."""
    from ouroboros.tools.neural_map import (
        _neural_map,
        _find_connections,
        _explore_concept,
        _create_connection,
        _query_knowledge,
        _validate_connection,
        _find_gaps,
        _generate_insight,
        _codebase_impact,
        _symbol_context,
    )

    TE = _get_tool_entry_class()

    return [
        TE(
            name="neural_map",
            schema={
                "name": "neural_map",
                "description": (
                    "Build a neural map of Jo's knowledge graph. "
                    "Shows all concepts, connections, and clusters. "
                    "Use to understand how different parts of the system relate."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "depth": {
                            "type": "integer",
                            "description": "Depth of connections to explore (default: 2)",
                            "default": 2,
                        },
                    },
                },
            },
            handler=_neural_map,
            timeout_sec=30,
        ),
        TE(
            name="find_connections",
            schema={
                "name": "find_connections",
                "description": (
                    "Find connections between two concepts, files, or ideas. "
                    "Shows the path between them and what's related to each."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "concept_a": {
                            "type": "string",
                            "description": "First concept or file name",
                        },
                        "concept_b": {
                            "type": "string",
                            "description": "Second concept or file name",
                        },
                    },
                    "required": ["concept_a", "concept_b"],
                },
            },
            handler=_find_connections,
            timeout_sec=20,
        ),
        TE(
            name="explore_concept",
            schema={
                "name": "explore_concept",
                "description": "Explore a concept and all its connections. Shows what it's related to and how.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "concept": {
                            "type": "string",
                            "description": "Concept, file, or tool name to explore",
                        },
                        "depth": {
                            "type": "integer",
                            "description": "Connection depth (default: 2)",
                            "default": 2,
                        },
                    },
                    "required": ["concept"],
                },
            },
            handler=_explore_concept,
            timeout_sec=20,
        ),
        TE(
            name="create_connection",
            schema={
                "name": "create_connection",
                "description": (
                    "Create a new connection between concepts by adding wikilinks. Links two ideas/files in the vault."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "from_concept": {
                            "type": "string",
                            "description": "Source concept or note name",
                        },
                        "to_concept": {
                            "type": "string",
                            "description": "Target concept or note name",
                        },
                        "connection_type": {
                            "type": "string",
                            "description": "Type of connection (default: related)",
                            "default": "related",
                        },
                    },
                    "required": ["from_concept", "to_concept"],
                },
            },
            handler=_create_connection,
            timeout_sec=15,
        ),
        TE(
            name="validate_connection",
            schema={
                "name": "validate_connection",
                "description": (
                    "Verify a connection exists between two concepts. Returns evidence for the connection "
                    "and checks if it's still valid. Helps reduce hallucinations by confirming knowledge links."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "source": {"type": "string", "description": "Source concept or file"},
                        "target": {"type": "string", "description": "Target concept or file"},
                    },
                    "required": ["source", "target"],
                },
            },
            handler=_validate_connection,
            timeout_sec=15,
        ),
        TE(
            name="find_gaps",
            schema={
                "name": "find_gaps",
                "description": (
                    "Find gaps in the knowledge graph where connections should exist but don't. "
                    "Identifies orphaned concepts, missing links between related ideas, and unreferenced tools. "
                    "Use to discover what needs linking."
                ),
                "parameters": {"type": "object", "properties": {}},
            },
            handler=_find_gaps,
            timeout_sec=30,
        ),
        TE(
            name="generate_insight",
            schema={
                "name": "generate_insight",
                "description": (
                    "Analyze the knowledge graph to generate new insights. Reviews connections, identifies patterns, "
                    "and proposes new understandings. Can help identify gaps and suggest areas for exploration. "
                    "Reduces hallucinations by grounding insights in actual connections."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "focus_area": {
                            "type": "string",
                            "description": "Area to focus on: architecture, tools, principles, self-reflection (default: all)",
                            "default": "all",
                        },
                    },
                },
            },
            handler=_generate_insight,
            timeout_sec=60,
        ),
        TE(
            name="query_knowledge",
            schema={
                "name": "query_knowledge",
                "description": (
                    "Query across all knowledge structures: codebase, vault, memory. Finds relevant concepts and files."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search terms or question",
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum results (default: 10)",
                            "default": 10,
                        },
                    },
                    "required": ["query"],
                },
            },
            handler=_query_knowledge,
            timeout_sec=30,
        ),
        TE(
            name="codebase_impact",
            schema={
                "name": "codebase_impact",
                "description": (
                    "Blast radius analysis - depth-grouped impact with confidence scoring. "
                    "Shows what WILL BREAK (depth 1), LIKELY AFFECTED (depth 2), and "
                    "MAY NEED TESTING (depth 3) if you modify a symbol. "
                    "Run BEFORE editing any function, class, or method."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target": {
                            "type": "string",
                            "description": "Symbol, function, class, or file name to analyze",
                        },
                        "direction": {
                            "type": "string",
                            "description": "'upstream' (who depends on this) or 'downstream' (what this depends on)",
                            "default": "upstream",
                        },
                        "max_depth": {
                            "type": "integer",
                            "description": "Maximum traversal depth (default: 3)",
                            "default": 3,
                        },
                    },
                    "required": ["target"],
                },
            },
            handler=_codebase_impact,
            timeout_sec=30,
        ),
        TE(
            name="symbol_context",
            schema={
                "name": "symbol_context",
                "description": (
                    "360-degree view of a symbol: callers, callees, imports, cluster membership, "
                    "and confidence scores. Use to understand what a symbol connects to before editing it."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Symbol, function, class, or file name to view",
                        },
                    },
                    "required": ["name"],
                },
            },
            handler=_symbol_context,
            timeout_sec=30,
        ),
        TE(
            name="discover_knowledge_gaps",
            schema={
                "name": "discover_knowledge_gaps",
                "description": (
                    "Scan all knowledge structures (neural map, ontology, vault, codebase) for gaps. "
                    "Returns prioritized list of what Jo should know but doesn't. "
                    "Use during background consciousness to proactively fill understanding gaps. "
                    "Shows orphaned concepts, disconnected tools, missing ontology links, and unlinked vault notes."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
            handler=_discover_knowledge_gaps,
            timeout_sec=30,
        ),
    ]
