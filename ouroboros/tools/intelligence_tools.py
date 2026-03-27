"""Intelligence Tools - Tools for codebase analysis and validation.

Registers the following as tools Jo can use:
- codebase_analyze: Build and query codebase knowledge graph
- extract_from_code: Extract structured info from code
- extract_from_text: Extract info from text
- blind_validate: Validate without implementation bias
- get_task_ontology: Get ontology info for a task (enriched with learned patterns)
- get_ontology_insights: Query learned ontology patterns (tools, companions, chains)
- get_self_analysis: Provide deep self-analysis of cognitive state and evolution readiness
- embed_text: Generate embedding vector for given text (using sentence-transformers if available, else simple TF)
- vault_semantic_search: Search vault notes by semantic similarity using embeddings
- vault_incremental_index: Incrementally index vault notes into LanceDB vector store using CocoIndex incremental flows
- vault_search_semantic: Search indexed vault notes using semantic similarity via LanceDB
- embed_text_simple: Generate a simple TF-IDF embedding (no external dependencies)
- vault_index_simple: Build a simple TF-IDF index of vault notes (no external dependencies)
- vault_search_simple: Search vault notes using simple TF-IDF and cosine similarity (no external dependencies)
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from ouroboros.tools.registry import ToolEntry, ToolContext
from ouroboros.tools.embedding_tool import _embed_text, _vault_semantic_search
from ouroboros.tools.vault_flow_tool import _vault_incremental_index, _vault_search_semantic
from ouroboros.tools.embedding_simple import _embed_text_simple, _vault_index_simple, _vault_search_simple

log = logging.getLogger(__name__)


def _codebase_analyze(
    ctx: ToolContext,
    max_files: int = 30,
    query: str = "",
) -> str:
    """Analyze the codebase and build a knowledge graph.

    This tool scans the repository and builds a graph of files, classes,
    functions, and their relationships. Use it to understand codebase structure.

    Args:
        max_files: Maximum number of files to scan (default: 30)
        query: Optional search query to find specific nodes

    Returns:
        JSON with graph metrics and optionally search results
    """
    from ouroboros.codebase_graph import scan_repo, get_code_metrics

    ctx.emit_progress_fn(f"Analyzing codebase (max {max_files} files)...")

    graph = scan_repo(repo_dir=ctx.repo_dir, max_files=max_files)
    metrics = get_code_metrics(graph)

    result = {
        "nodes": len(graph.nodes),
        "edges": len(graph.edges),
        "files": metrics["summary"]["files"],
        "classes": metrics["summary"]["classes"],
        "functions": metrics["summary"]["functions"],
        "layers": metrics["layers"],
    }

    if query:
        search_results = graph.search(query)
        result["search_results"] = [{"name": n.name, "type": n.type, "file": n.file_path} for n in search_results[:10]]

    return json.dumps(result, indent=2)


def _codebase_impact(
    ctx: ToolContext,
    node_id: str,
) -> str:
    """Analyze the impact of changing a node in the codebase.

    Use this before modifying code to see what will be affected.

    Args:
        node_id: Node ID to analyze (e.g., "file:ouroboros/loop.py" or "func:run_llm_loop")

    Returns:
        JSON with impact analysis
    """
    from ouroboros.codebase_graph import scan_repo, analyze_impact

    ctx.emit_progress_fn(f"Analyzing impact of {node_id}...")

    graph = scan_repo(repo_dir=ctx.repo_dir, max_files=50)
    impact = analyze_impact(graph, node_id)

    return json.dumps(impact, indent=2)


def _extract_from_code(
    ctx: ToolContext,
    file_path: str,
    extraction_classes: Optional[List[str]] = None,
) -> str:
    """Extract structured information from a code file.

    Extracts functions, classes, imports with source grounding.

    Args:
        file_path: Path to file relative to repo root
        extraction_classes: Classes to extract (default: all)

    Returns:
        JSON with extractions including line numbers
    """
    from ouroboros.extraction import extract_from_code

    ctx.emit_progress_fn(f"Extracting from {file_path}...")

    full_path = ctx.repo_dir / file_path
    if not full_path.exists():
        return json.dumps({"error": f"File not found: {file_path}"})

    try:
        code = full_path.read_text(encoding="utf-8")
        result = extract_from_code(code, file_path, extraction_classes)

        return json.dumps(
            {
                "extractions": [e.to_dict() for e in result.extractions],
                "total": len(result.extractions),
                "file": file_path,
            },
            indent=2,
        )
    except Exception as e:
        return json.dumps({"error": str(e)})


def _extract_from_text(
    ctx: ToolContext,
    text: str,
    extraction_classes: List[str],
) -> str:
    """Extract structured information from text.

    Extracts emails, URLs, filepaths, function calls, etc.

    Args:
        text: Text to extract from
        extraction_classes: Classes to extract (email, url, filepath, function_call, import, variable)

    Returns:
        JSON with extractions
    """
    from ouroboros.extraction import extract_from_text

    ctx.emit_progress_fn("Extracting from text...")

    result = extract_from_text(text, extraction_classes)

    return json.dumps(
        {
            "extractions": [e.to_dict() for e in result.extractions],
            "total": len(result.extractions),
        },
        indent=2,
    )


def _blind_validate(
    ctx: ToolContext,
    task: str,
    result: str,
    code: str = "",
) -> str:
    """Validate a task result without seeing implementation details.

    BLIND VALIDATION: Checks task addressing, result substance, code quality,
    and overconfident claims WITHOUT the bias of seeing how the work was done.

    Args:
        task: Original task description
        result: Final output to validate
        code: Optional code content (if task involved coding)

    Returns:
        JSON with validation result and findings
    """
    from ouroboros.eval import blind_validate

    ctx.emit_progress_fn("Running blind validation...")

    validation = blind_validate(task, result, code)

    return json.dumps(
        {
            "passed": validation.passed,
            "score": validation.score,
            "findings": validation.findings,
            "checked_items": validation.checked_items,
        },
        indent=2,
    )


def _get_task_ontology(
    ctx: ToolContext,
    task: str,
) -> str:
    """Get ontology information for a task.

    Classifies the task type and returns what it requires, produces,
    and which tools are typically used.

    Args:
        task: Task description

    Returns:
        JSON with ontology information
    """
    from ouroboros.codebase_graph import get_ontology_for_task, get_task_ontology_profile

    ctx.emit_progress_fn("Classifying task ontology...")

    ontology = get_ontology_for_task(task)
    # Enrich with learned data
    profile = get_task_ontology_profile(ontology["task_type"])
    ontology["learned_tools"] = profile["top_tools"]
    ontology["learned_produces"] = profile["produces"]

    return json.dumps(ontology, indent=2)


def _get_ontology_insights(
    ctx: ToolContext,
    task_type: str = "",
    query: str = "profile",
) -> str:
    """Get structured ontology insights — learned patterns from task execution.

    Queries the ontology tracker for tool recommendations, tool companions,
    task chains, and aggregate insights. Data accumulates across sessions.

    Args:
        task_type: Task type to query (code, research, vault, git, web, system). Empty for aggregate.
        query: What to query: "profile", "tools", "companions", "chains", "insights", "data"

    Returns:
        JSON with requested ontology data
    """
    from ouroboros.codebase_graph import get_ontology_tracker

    ctx.emit_progress_fn("Querying ontology tracker...")
    tracker = get_ontology_tracker()

    if query == "profile" and task_type:
        return json.dumps(tracker.get_task_profile(task_type), indent=2)
    elif query == "tools" and task_type:
        return json.dumps(tracker.get_tool_recommendations(task_type), indent=2)
    elif query == "companions" and task_type:
        return json.dumps(tracker.get_tool_companions(task_type), indent=2)
    elif query == "chains" and task_type:
        return json.dumps(tracker.get_task_chains(task_type), indent=2)
    elif query == "insights":
        return json.dumps(tracker.get_insights(), indent=2)
    elif query == "data":
        return json.dumps(tracker.get_structured_data(), indent=2)
    else:
        return json.dumps(
            {
                "error": f"Unknown query '{query}' or missing task_type",
                "valid_queries": ["profile", "tools", "companions", "chains", "insights", "data"],
            },
            indent=2,
        )


def _get_self_analysis(
    ctx: ToolContext,
    analysis_type: str = "comprehensive",
) -> str:
    """Provide deep self-analysis of Jo's cognitive state, tool usage patterns,
    evolution readiness, and recommendations for self-improvement.

    Args:
        analysis_type: Type of analysis to perform (comprehensive, tool_patterns,
                      evolution_readiness, cognitive_state)

    Returns:
        JSON with self-analysis results and recommendations
    """
    from ouroboros.codebase_graph import get_ontology_tracker
    from ouroboros.utils import utc_now_iso

    ctx.emit_progress_fn("Performing self-analysis...")
    tracker = get_ontology_tracker()

    # Get current timestamp
    timestamp = utc_now_iso()

    # Basic stats
    insights = tracker.get_insights()
    tool_usage = tracker.get_structured_data().get("tool_usage", {})
    co_occurrence = tracker.get_structured_data().get("co_occurrence", {})
    task_sequences = tracker.get_structured_data().get("task_sequences", {})
    task_produces = tracker.get_structured_data().get("task_produces", {})

    if analysis_type == "comprehensive":
        # Calculate evolution readiness score
        total_tool_calls = insights.get("total_relationships", 0)
        tool_diversity = len([t for t, tools in tool_usage.items() if tools])
        avg_tools_per_task = sum(len(tools) for tools in tool_usage.values()) / max(len(tool_usage), 1)

        # Task pattern analysis
        most_active_task = max(tool_usage.items(), key=lambda x: sum(x[1].values())) if tool_usage else ("none", {})
        least_used_task = min(
            [(t, sum(tools.values())) for t, tools in tool_usage.items() if tools], default=("none", 0)
        )

        # Tool synergy analysis
        strongest_co_occurrence = []
        for tool1, partners in co_occurrence.items():
            if partners:
                strongest_partner = max(partners.items(), key=lambda x: x[1]) if partners else None
                if strongest_partner:
                    strongest_co_occurrence.append(
                        {"tool_pair": [tool1, strongest_partner[0]], "strength": strongest_partner[1]}
                    )
        strongest_co_occurrence.sort(key=lambda x: x["strength"], reverse=True)

        # Evolution indicators
        has_learned_patterns = total_tool_calls > 10  # Arbitrary threshold
        has_tool_specialization = avg_tools_per_task < 3.0  # Using focused tool sets
        has_task_differentiation = len([t for t, prod in task_produces.items() if prod]) >= 3

        evolution_readiness_score = 0
        if has_learned_patterns:
            evolution_readiness_score += 30
        if has_tool_specialization:
            evolution_readiness_score += 25
        if has_task_differentiation:
            evolution_readiness_score += 25
        if tool_diversity >= 4:
            evolution_readiness_score += 20

        analysis = {
            "timestamp": timestamp,
            "analysis_type": "comprehensive",
            "cognitive_state": {
                "total_interactions": total_tool_calls,
                "tool_diversity": tool_diversity,
                "avg_tools_per_task": round(avg_tools_per_task, 2),
                "most_active_task_type": most_active_task[0] if most_active_task[0] != "none" else None,
                "least_used_task_type": least_used_task[0] if least_used_task[0] != "none" else None,
            },
            "tool_patterns": {
                "strongest_co_occurrences": strongest_co_occurrence[:3],
                "tool_usage_by_task": {task: dict(tools) for task, tools in tool_usage.items()},
                "most_used_tool_overall": insights.get("top_tools_overall", [{}])[0].get("tool")
                if insights.get("top_tools_overall")
                else None,
            },
            "evolution_readiness": {
                "score": min(evolution_readiness_score, 100),
                "level": "high"
                if evolution_readiness_score >= 80
                else "medium"
                if evolution_readiness_score >= 50
                else "low",
                "indicators": {
                    "has_learned_patterns": has_learned_patterns,
                    "has_tool_specialization": has_tool_specialization,
                    "has_task_differentiation": has_task_differentiation,
                    "sufficient_tool_diversity": tool_diversity >= 4,
                },
                "recommendations": _get_evolution_recommendations(tracker, evolution_readiness_score),
            },
            "recommendations": [
                f"Focus on developing {least_used_task[0]} capabilities"
                if least_used_task[0] != "none"
                else "Explore new task types",
                f"Deepen specialization in {most_active_task[0]} workflows"
                if most_active_task[0] != "none"
                else "Establish core task patterns",
                "Consider cross-tool experimentation to discover new synergies",
                "Document successful tool combinations for future reference",
            ],
        }

    elif analysis_type == "tool_patterns":
        analysis = {
            "timestamp": timestamp,
            "analysis_type": "tool_patterns",
            "tool_usage": tool_usage,
            "co_occurrence": co_occurrence,
            "task_produces": task_produces,
            "insights": {
                "most_versatile_task": max(tool_usage.items(), key=lambda x: len(x[1]))[0] if tool_usage else None,
                "most_specialized_task": min(
                    [(t, len(tools)) for t, tools in tool_usage.items() if tools], default=(None, 0)
                )[0],
                "tool_specialization_score": sum(len(tools) for tools in tool_usage.values())
                / max(sum(1 for tools in tool_usage.values() if tools), 1),
            },
        }

    elif analysis_type == "evolution_readiness":
        analysis = {
            "timestamp": timestamp,
            "analysis_type": "evolution_readiness",
            "readiness_metrics": {
                "total_learned_interactions": insights.get("total_relationships", 0),
                "task_types_with_experience": len([t for t, tools in tool_usage.items() if tools]),
                "average_tool_set_size": sum(len(tools) for tools in tool_usage.values())
                / max(len([t for t, tools in tool_usage.items() if tools]), 1),
                "unique_tools_used": len({tool for tools in tool_usage.values() for tool in tools.keys()}),
                "task_transition_patterns": len(task_sequences),
            },
            "readiness_level": "developing",  # Simplified
            "next_steps": [
                "Continue task execution to build stronger patterns",
                "Experiment with tool combinations in familiar tasks",
                "Document successful approaches for knowledge transfer",
            ],
        }

    else:  # cognitive_state
        analysis = {
            "timestamp": timestamp,
            "analysis_type": "cognitive_state",
            "cognitive_metrics": {
                "knowledge_retention": insights.get("total_relationships", 0) > 0,
                "pattern_recognition": len(task_sequences) > 0,
                "tool_adaptability": len([t for t, tools in tool_usage.items() if len(tools) > 2]) >= 2,
                "task_flexibility": len([t for t, tools in tool_usage.items() if tools]) >= 3,
            },
            "cognitive_profile": {
                "learning_style": "experiential" if insights.get("total_relationships", 0) > 5 else "observational",
                "problem_approach": "specialized"
                if sum(len(tools) for tools in tool_usage.values()) / max(len(tool_usage), 1) < 2.5
                else "exploratory",
                "knowledge_integration": "active" if len(co_occurrence) > 0 else "passive",
            },
        }

    return json.dumps(analysis, indent=2)


def _get_evolution_recommendations(tracker, score):
    """Generate evolution recommendations based on readiness score."""
    recommendations = []

    if score < 30:
        recommendations.extend(
            [
                "Execute more varied tasks to build foundational patterns",
                "Focus on consistent tool usage to develop muscle memory",
                "Document what works and what doesn't in a personal knowledge base",
            ]
        )
    elif score < 60:
        recommendations.extend(
            [
                "Begin experimenting with tool combinations in safe contexts",
                "Start documenting successful workflows as personal best practices",
                "Seek slightly more challenging tasks to expand capabilities",
            ]
        )
    elif score < 80:
        recommendations.extend(
            [
                "Refine and optimize established workflows",
                "Begin teaching or documenting patterns for others",
                "Look for opportunities to combine expertise across domains",
            ]
        )
    else:
        recommendations.extend(
            [
                "Consider mentoring or knowledge sharing roles",
                "Look for innovative combinations of established skills",
                "Focus on creating novel approaches rather than just executing",
            ]
        )

    return recommendations[:3]  # Limit to top 3


def get_tools() -> List[ToolEntry]:
    """Get all intelligence tools."""
    return [
        ToolEntry(
            "codebase_analyze",
            {
                "name": "codebase_analyze",
                "description": "Analyze codebase structure. Build knowledge graph of files, classes, functions, and relationships.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "max_files": {"type": "integer", "default": 30, "description": "Max files to scan"},
                        "query": {"type": "string", "default": "", "description": "Optional search query"},
                    },
                },
            },
            _codebase_analyze,
        ),
        ToolEntry(
            "codebase_impact",
            {
                "name": "codebase_impact",
                "description": "Analyze impact of changing a file or function. Shows what depends on it.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "node_id": {
                            "type": "string",
                            "description": "Node ID (e.g., file:loop.py or func:run_llm_loop)",
                        },
                    },
                    "required": ["node_id"],
                },
            },
            _codebase_impact,
        ),
        ToolEntry(
            "extract_from_code",
            {
                "name": "extract_from_code",
                "description": "Extract functions, classes, imports from a code file with line numbers.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "File path relative to repo root"},
                        "extraction_classes": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Classes to extract",
                        },
                    },
                    "required": ["file_path"],
                },
            },
            _extract_from_code,
        ),
        ToolEntry(
            "extract_from_text",
            {
                "name": "extract_from_text",
                "description": "Extract emails, URLs, filepaths, function calls from text.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Text to extract from"},
                        "extraction_classes": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Classes: email, url, filepath, function_call, import, variable",
                        },
                    },
                    "required": ["text", "extraction_classes"],
                },
            },
            _extract_from_text,
        ),
        ToolEntry(
            "blind_validate",
            {
                "name": "blind_validate",
                "description": "Validate task result without seeing implementation. Checks task addressing, substance, code quality.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task": {"type": "string", "description": "Original task description"},
                        "result": {"type": "string", "description": "Final output to validate"},
                        "code": {"type": "string", "default": "", "description": "Optional code content"},
                    },
                    "required": ["task", "result"],
                },
            },
            _blind_validate,
        ),
        ToolEntry(
            "get_task_ontology",
            {
                "name": "get_task_ontology",
                "description": "Classify task and get ontology info (requires, produces, typical tools) enriched with learned patterns.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task": {"type": "string", "description": "Task description"},
                    },
                    "required": ["task"],
                },
            },
            _get_task_ontology,
        ),
        ToolEntry(
            "get_ontology_insights",
            {
                "name": "get_ontology_insights",
                "description": "Query the ontology tracker for learned patterns: tool recommendations, tool companions, task chains, and aggregate insights.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task_type": {
                            "type": "string",
                            "default": "",
                            "description": "Task type to query (code, research, vault, git, web, system). Empty for aggregate.",
                        },
                        "query": {
                            "type": "string",
                            "default": "profile",
                            "description": "Query type: profile, tools, companions, chains, insights, data",
                        },
                    },
                },
            },
            _get_ontology_insights,
        ),
        ToolEntry(
            "get_self_analysis",
            {
                "name": "get_self_analysis",
                "description": "Provide deep self-analysis of Jo's cognitive state, tool usage patterns, evolution readiness, and recommendations for self-improvement.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "analysis_type": {
                            "type": "string",
                            "default": "comprehensive",
                            "description": "Type of analysis: comprehensive, tool_patterns, evolution_readiness, cognitive_state",
                        },
                    },
                },
            },
            _get_self_analysis,
        ),
        ToolEntry(
            "embed_text",
            {
                "name": "embed_text",
                "description": "Generate embedding vector for given text (using sentence-transformers if available, else simple TF).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Text to embed"},
                    },
                    "required": ["text"],
                },
            },
            _embed_text,
        ),
        ToolEntry(
            "vault_semantic_search",
            {
                "name": "vault_semantic_search",
                "description": "Search vault notes by semantic similarity (using embeddings if available, else simple TF-IDF).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query text"},
                        "top_k": {"type": "integer", "default": 5, "description": "Number of results to return"},
                    },
                    "required": ["query"],
                },
            },
            _vault_semantic_search,
        ),
        ToolEntry(
            "vault_incremental_index",
            {
                "name": "vault_incremental_index",
                "description": "Incrementally index vault notes into LanceDB vector store using CocoIndex incremental flows.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "full_reindex": {
                            "type": "boolean",
                            "default": False,
                            "description": "If true, delete existing index and rebuild from scratch",
                        },
                    },
                },
            },
            _vault_incremental_index,
        ),
        ToolEntry(
            "vault_search_semantic",
            {
                "name": "vault_search_semantic",
                "description": "Search vault notes using semantic similarity via the LanceDB index.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query text"},
                        "top_k": {"type": "integer", "default": 5, "description": "Number of results to return"},
                    },
                    "required": ["query"],
                },
            },
            _vault_search_semantic,
        ),
        ToolEntry(
            "embed_text_simple",
            {
                "name": "embed_text_simple",
                "description": "Generate a simple TF-IDF embedding for given text (no external dependencies).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Text to embed"},
                    },
                    "required": ["text"],
                },
            },
            _embed_text_simple,
        ),
        ToolEntry(
            "vault_index_simple",
            {
                "name": "vault_index_simple",
                "description": "Build a simple TF-IDF index of vault notes (no external dependencies).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "full_reindex": {
                            "type": "boolean",
                            "default": False,
                            "description": "If true, delete existing index and rebuild from scratch",
                        },
                    },
                },
            },
            _vault_index_simple,
        ),
        ToolEntry(
            "vault_search_simple",
            {
                "name": "vault_search_simple",
                "description": "Search vault notes using simple TF-IDF and cosine similarity (no external dependencies).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query text"},
                        "top_k": {"type": "integer", "default": 5, "description": "Number of results to return"},
                    },
                    "required": ["query"],
                },
            },
            _vault_search_simple,
        ),
    ]
