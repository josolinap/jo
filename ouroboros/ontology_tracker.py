"""Ontology tracker for task-tool relationships.

Extracted from codebase_graph.py (Principle 5: Minimalism).
Tracks: task→tool usage, tool co-occurrence, task sequencing, artifact production.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

# Default ontology knowledge
_ONTOLOGY_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "code": {
        "typical_tools": ["repo_read", "repo_write_commit", "shell_run", "grep"],
        "produces": ["code_file", "test_file", "commit"],
        "requires": ["file_system", "git"],
    },
    "debug": {
        "typical_tools": ["repo_read", "shell_run", "grep", "log_analyze"],
        "produces": ["fix", "diagnosis"],
        "requires": ["error_logs", "stack_trace"],
    },
    "test": {
        "typical_tools": ["shell_run", "repo_read", "repo_write_commit"],
        "produces": ["test_file", "test_result"],
        "requires": ["test_framework"],
    },
    "deploy": {
        "typical_tools": ["shell_run", "repo_write_commit", "git_push"],
        "produces": ["deployment", "release"],
        "requires": ["ci_cd", "environment"],
    },
    "review": {
        "typical_tools": ["repo_read", "grep", "diff"],
        "produces": ["review_comment", "suggestion"],
        "requires": ["codebase"],
    },
    "research": {
        "typical_tools": ["web_search", "repo_read", "grep"],
        "produces": ["analysis", "recommendation"],
        "requires": ["information_sources"],
    },
    "general": {
        "typical_tools": ["repo_read", "shell_run"],
        "produces": ["result"],
        "requires": [],
    },
}


class OntologyTracker:
    """Tracks ontology relationships and their strengths.

    Relationship types:
        uses_tool      - task_type -> tool_name (which tools a task type uses)
        produces       - task_type -> artifact  (what a task type produces)
        requires       - task_type -> capability (what a task type needs)
        co_occurs_with - tool_name -> tool_name  (tools used together)
        followed_by    - task_type -> task_type  (task sequencing patterns)
    """

    def __init__(self, persistence_path: Optional[Path] = None) -> None:
        self._relationships: List[Dict[str, Any]] = []
        self._tool_usage: Dict[str, Dict[str, int]] = {}  # task_type -> {tool: count}
        self._co_occurrence: Dict[str, Dict[str, int]] = {}  # tool -> {tool: count}
        self._task_sequence: Dict[str, Dict[str, int]] = {}  # prev_type -> {next_type: count}
        self._task_produces: Dict[str, Dict[str, int]] = {}  # task_type -> {artifact: count}
        self._persistence_path = persistence_path
        if persistence_path and persistence_path.exists():
            self._load()
        elif not self._tool_usage:
            self._seed_from_defaults()

    def _seed_from_defaults(self) -> None:
        """Seed tracker from ontology defaults so it starts with useful data."""
        for task_type, defaults in _ONTOLOGY_DEFAULTS.items():
            if task_type == "general":
                continue
            for tool in defaults.get("typical_tools", []):
                self.record(task_type, tool, "uses_tool", strength=0.8)
            for artifact in defaults.get("produces", []):
                self.record(task_type, artifact, "produces", strength=0.8)
            for req in defaults.get("requires", []):
                self.record(task_type, req, "requires", strength=0.8)

    def record(
        self,
        source: str,
        target: str,
        relation: str,
        strength: float = 1.0,
    ) -> None:
        """Record a relationship and update aggregate indexes."""
        self._relationships.append(
            {
                "source": source,
                "target": target,
                "relation": relation,
                "strength": strength,
                "timestamp": datetime.now().isoformat(),
            }
        )

        if relation == "uses_tool":
            self._tool_usage.setdefault(source, {})
            self._tool_usage[source][target] = self._tool_usage[source].get(target, 0) + 1

        elif relation == "produces":
            self._task_produces.setdefault(source, {})
            self._task_produces[source][target] = self._task_produces[source].get(target, 0) + 1

        elif relation == "co_occurs_with":
            self._co_occurrence.setdefault(source, {})
            self._co_occurrence[source][target] = self._co_occurrence[source].get(target, 0) + 1
            self._co_occurrence.setdefault(target, {})
            self._co_occurrence[target][source] = self._co_occurrence[target].get(source, 0) + 1

        elif relation == "followed_by":
            self._task_sequence.setdefault(source, {})
            self._task_sequence[source][target] = self._task_sequence[source].get(target, 0) + 1

    # --- Backward compatibility ---
    def add_relationship(
        self,
        source: str,
        target: str,
        relation: str,
        strength: float = 1.0,
    ) -> None:
        self.record(source, target, relation, strength)

    # --- Query methods ---

    def get_tool_recommendations(self, task_type: str, top_n: int = 5) -> List[Dict[str, Any]]:
        """Get recommended tools for a task type, ranked by usage frequency."""
        tools = self._tool_usage.get(task_type, {})
        if not tools:
            return []
        ranked = sorted(tools.items(), key=lambda x: x[1], reverse=True)[:top_n]
        total = sum(tools.values())
        return [{"tool": tool, "usage_count": count, "confidence": round(count / total, 2)} for tool, count in ranked]

    def get_task_profile(self, task_type: str) -> Dict[str, Any]:
        """Get full structured profile for a task type."""
        tools = self._tool_usage.get(task_type, {})
        produces = self._task_produces.get(task_type, {})
        return {
            "task_type": task_type,
            "top_tools": self.get_tool_recommendations(task_type),
            "produces": [{"artifact": a, "count": c} for a, c in sorted(produces.items(), key=lambda x: -x[1])[:5]],
            "total_tool_calls": sum(tools.values()),
            "tool_diversity": len(tools),
        }

    def get_tool_companions(self, tool_name: str, top_n: int = 5) -> List[Dict[str, Any]]:
        """Get tools frequently used alongside a given tool."""
        companions = self._co_occurrence.get(tool_name, {})
        if not companions:
            return []
        ranked = sorted(companions.items(), key=lambda x: x[1], reverse=True)[:top_n]
        total = sum(companions.values())
        return [{"tool": t, "co_count": c, "strength": round(c / total, 2)} for t, c in ranked]

    def get_task_chains(self, task_type: str, top_n: int = 3) -> List[Dict[str, Any]]:
        """Get what task types typically follow a given task type."""
        nexts = self._task_sequence.get(task_type, {})
        if not nexts:
            return []
        ranked = sorted(nexts.items(), key=lambda x: x[1], reverse=True)[:top_n]
        total = sum(nexts.values())
        return [{"next_task": t, "count": c, "probability": round(c / total, 2)} for t, c in ranked]

    def get_insights(self) -> Dict[str, Any]:
        """Get aggregate insights about tracked relationships."""
        tool_total = sum(c for tools in self._tool_usage.values() for c in tools.values())
        produces_total = sum(c for arts in self._task_produces.values() for c in arts.values())
        co_total = sum(c for comps in self._co_occurrence.values() for c in comps.values()) // 2
        seq_total = sum(c for seqs in self._task_sequence.values() for c in seqs.values())
        total = tool_total + produces_total + co_total + seq_total

        if total == 0 and not self._relationships:
            return {"total_relationships": 0, "average_strength": 0.0}

        if self._relationships:
            total = max(total, len(self._relationships))
            avg_strength = sum(r["strength"] for r in self._relationships) / len(self._relationships)
            relation_counts: Dict[str, int] = {}
            for r in self._relationships:
                rel = r["relation"]
                relation_counts[rel] = relation_counts.get(rel, 0) + 1
        else:
            avg_strength = 0.8
            relation_counts = {
                "uses_tool": tool_total,
                "produces": produces_total,
                "co_occurs_with": co_total,
                "followed_by": seq_total,
            }

        all_tools: Dict[str, int] = {}
        for tools in self._tool_usage.values():
            for tool, count in tools.items():
                all_tools[tool] = all_tools.get(tool, 0) + count
        top_tools = sorted(all_tools.items(), key=lambda x: -x[1])[:10]

        return {
            "total_relationships": total,
            "average_strength": round(avg_strength, 2),
            "relation_counts": relation_counts,
            "task_types_tracked": list(self._tool_usage.keys()),
            "top_tools_overall": [{"tool": t, "count": c} for t, c in top_tools],
        }

    def get_structured_data(self) -> Dict[str, Any]:
        """Get all structured data for external consumption."""
        return {
            "tool_usage": {k: dict(v) for k, v in self._tool_usage.items()},
            "co_occurrence": {k: dict(v) for k, v in self._co_occurrence.items()},
            "task_sequences": {k: dict(v) for k, v in self._task_sequence.items()},
            "task_produces": {k: dict(v) for k, v in self._task_produces.items()},
        }

    # --- Persistence ---

    def _load(self) -> None:
        """Load tracker state from disk."""
        if not self._persistence_path:
            return
        try:
            data = json.loads(self._persistence_path.read_text(encoding="utf-8"))
            self._tool_usage = data.get("tool_usage", {})
            self._co_occurrence = data.get("co_occurrence", {})
            self._task_sequence = data.get("task_sequences", {})
            self._task_produces = data.get("task_produces", {})
            log.info("Loaded ontology tracker: %d task types tracked", len(self._tool_usage))
        except Exception as e:
            log.warning("Failed to load ontology tracker: %s", e)

    def save(self) -> None:
        """Persist tracker state to disk."""
        if not self._persistence_path:
            return
        try:
            self._persistence_path.parent.mkdir(parents=True, exist_ok=True)
            self._persistence_path.write_text(
                json.dumps(self.get_structured_data(), indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            log.warning("Failed to save ontology tracker: %s", e)


# Global singleton tracker
_DATA_ROOT = Path(os.environ.get("DATA_ROOT", Path.home() / ".jo_data"))
_PERSISTENCE_PATH = _DATA_ROOT / "state" / "ontology_tracker.json"
_global_tracker = OntologyTracker(persistence_path=_PERSISTENCE_PATH)


def get_ontology_tracker() -> OntologyTracker:
    """Get the global ontology tracker instance."""
    return _global_tracker


def record_task_tool_usage(task_type: str, tool_name: str) -> None:
    """Record that a tool was used for a given task type."""
    _global_tracker.record(task_type, tool_name, "uses_tool")


def record_task_produces(task_type: str, artifact: str) -> None:
    """Record that a task type produced an artifact."""
    _global_tracker.record(task_type, artifact, "produces")


def record_tool_co_occurrence(tools: List[str]) -> None:
    """Record that a set of tools were used together in one round."""
    for i, t1 in enumerate(tools):
        for t2 in tools[i + 1 :]:
            if t1 != t2:
                _global_tracker.record(t1, t2, "co_occurs_with")


def record_task_sequence(prev_type: str, next_type: str) -> None:
    """Record that one task type was followed by another."""
    if prev_type != next_type:
        _global_tracker.record(prev_type, next_type, "followed_by")


def get_task_ontology_profile(task_type: str) -> Dict[str, Any]:
    """Get structured ontology profile for a task type (for LLM consumption)."""
    return _global_tracker.get_task_profile(task_type)


def save_ontology_tracker() -> None:
    """Persist ontology tracker to disk."""
    _global_tracker.save()
