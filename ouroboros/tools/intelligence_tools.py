"""Intelligence Tools - Tools for codebase analysis and validation.

Registers the following as tools Jo can use:
- codebase_analyze: Build and query codebase knowledge graph
- extract_from_code: Extract structured info from code
- extract_from_text: Extract info from text
- blind_validate: Validate without implementation bias
- get_task_ontology: Get ontology info for a task
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from ouroboros.tools.registry import ToolEntry, ToolContext

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
    from ouroboros.codebase_graph import get_ontology_for_task

    ctx.emit_progress_fn("Classifying task ontology...")

    ontology = get_ontology_for_task(task)

    return json.dumps(ontology, indent=2)


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
                "description": "Classify task and get ontology info (requires, produces, typical tools).",
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
    ]
