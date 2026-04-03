"""
Jo — Tree-of-Thought Reasoning System.

Inspired by Yao et al. (2023) "Tree of Thoughts: Deliberate Problem Solving with LLMs"
and the awesome-agentic-patterns catalogue (4.2k stars).

Problem: Linear chain-of-thought reasoning commits early to one path and fails silently
when intermediate assumptions are wrong. On complex planning/synthesis tasks, this causes
premature convergence, weak recovery from mistakes, and missed alternatives.

Solution: Explore a search tree of intermediate thoughts instead of a single chain.
Generate multiple candidate continuations, score partial states, prune weak branches,
and continue expanding the most promising paths until a stopping condition is met.

This turns reasoning into guided search: backtracking is explicit, branch quality is
measurable, and the final answer can be chosen from competing candidates rather than
the first trajectory.

Performance: 22-28% improvement over Chain-of-Thought on multi-step reasoning tasks.
Cost: 3-10x more tokens than Chain-of-Thought (use only for complex tasks).
"""

from __future__ import annotations

import json
import logging
import pathlib
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)


class ThoughtStatus(Enum):
    EXPLORED = "explored"
    PRUNED = "pruned"
    SELECTED = "selected"
    BACKTRACKED = "backtracked"


@dataclass
class ThoughtNode:
    """A node in the tree of thoughts."""

    id: str
    content: str
    parent_id: Optional[str]
    children: List[str] = field(default_factory=list)
    score: float = 0.0  # 0.0-1.0, higher is better
    status: ThoughtStatus = ThoughtStatus.EXPLORED
    depth: int = 0
    created_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ThoughtTree:
    """A complete tree of thoughts."""

    root_id: str
    nodes: Dict[str, ThoughtNode] = field(default_factory=dict)
    max_depth: int = 3
    max_branches: int = 3
    evaluation_function: Optional[str] = None
    created_at: str = ""
    completed_at: str = ""
    selected_path: List[str] = field(default_factory=list)


class TreeOfThoughtReasoner:
    """Implements Tree-of-Thought reasoning for complex problem solving."""

    def __init__(self, repo_dir: pathlib.Path):
        self.repo_dir = repo_dir
        self.state_dir = repo_dir / ".jo_state" / "tree_of_thought"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self._trees: Dict[str, ThoughtTree] = {}
        self._load_history()

    def _load_history(self) -> None:
        """Load tree of thought history."""
        for tree_file in self.state_dir.glob("tree_*.json"):
            try:
                data = json.loads(tree_file.read_text(encoding="utf-8"))
                tree = ThoughtTree(**data)
                self._trees[tree.root_id] = tree
            except Exception:
                pass

    def _save_tree(self, tree: ThoughtTree) -> None:
        """Save a tree to disk."""
        tree_file = self.state_dir / f"tree_{tree.root_id}.json"
        tree_file.write_text(
            json.dumps(
                {
                    "root_id": tree.root_id,
                    "nodes": {
                        nid: {
                            "id": n.id,
                            "content": n.content,
                            "parent_id": n.parent_id,
                            "children": n.children,
                            "score": n.score,
                            "status": n.status.value,
                            "depth": n.depth,
                            "created_at": n.created_at,
                            "metadata": n.metadata,
                        }
                        for nid, n in tree.nodes.items()
                    },
                    "max_depth": tree.max_depth,
                    "max_branches": tree.max_branches,
                    "evaluation_function": tree.evaluation_function,
                    "created_at": tree.created_at,
                    "completed_at": tree.completed_at,
                    "selected_path": tree.selected_path,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def create_tree(self, root_content: str, max_depth: int = 3, max_branches: int = 3) -> ThoughtTree:
        """Create a new tree of thoughts."""
        root_id = f"tot-{int(time.time())}"
        root_node = ThoughtNode(
            id=root_id,
            content=root_content,
            parent_id=None,
            depth=0,
            created_at=datetime.now().isoformat(),
        )

        tree = ThoughtTree(
            root_id=root_id,
            nodes={root_id: root_node},
            max_depth=max_depth,
            max_branches=max_branches,
            created_at=datetime.now().isoformat(),
        )
        self._trees[root_id] = tree
        self._save_tree(tree)
        log.info("[TreeOfThought] Created tree %s with root: %s", root_id, root_content[:100])
        return tree

    def expand_node(self, tree_id: str, node_id: str, children: List[str], scores: List[float]) -> bool:
        """Expand a node with child thoughts."""
        tree = self._trees.get(tree_id)
        if not tree:
            log.error("[TreeOfThought] Tree %s not found", tree_id)
            return False

        parent = tree.nodes.get(node_id)
        if not parent:
            log.error("[TreeOfThought] Node %s not found in tree %s", node_id, tree_id)
            return False

        if parent.depth >= tree.max_depth:
            log.warning("[TreeOfThought] Node %s at max depth %d", node_id, parent.depth)
            return False

        for i, (content, score) in enumerate(zip(children, scores)):
            child_id = f"{node_id}-{i}"
            child = ThoughtNode(
                id=child_id,
                content=content,
                parent_id=node_id,
                score=score,
                depth=parent.depth + 1,
                created_at=datetime.now().isoformat(),
            )
            tree.nodes[child_id] = child
            parent.children.append(child_id)

        self._save_tree(tree)
        log.info("[TreeOfThought] Expanded node %s with %d children", node_id, len(children))
        return True

    def prune_weak_branches(self, tree_id: str, threshold: float = 0.3) -> int:
        """Prune branches below score threshold."""
        tree = self._trees.get(tree_id)
        if not tree:
            return 0

        pruned = 0
        for node in tree.nodes.values():
            if node.status == ThoughtStatus.EXPLORED and node.score < threshold:
                node.status = ThoughtStatus.PRUNED
                pruned += 1
                # Also prune all descendants
                self._prune_descendants(tree, node.id)

        if pruned > 0:
            self._save_tree(tree)
            log.info("[TreeOfThought] Pruned %d weak branches from tree %s", pruned, tree_id)

        return pruned

    def _prune_descendants(self, tree: ThoughtTree, node_id: str) -> None:
        """Recursively prune all descendants of a node."""
        node = tree.nodes.get(node_id)
        if not node:
            return

        for child_id in node.children:
            child = tree.nodes.get(child_id)
            if child:
                child.status = ThoughtStatus.PRUNED
                self._prune_descendants(tree, child_id)

    def select_best_path(self, tree_id: str) -> List[str]:
        """Select the best path through the tree using beam search."""
        tree = self._trees.get(tree_id)
        if not tree:
            return []

        # Beam search: keep top-k paths at each level
        beam = [(tree.root_id, [tree.root_id])]
        best_path = [tree.root_id]
        best_score = tree.nodes[tree.root_id].score

        for depth in range(tree.max_depth):
            next_beam = []
            for current_id, path in beam:
                current = tree.nodes.get(current_id)
                if not current:
                    continue

                # Get unpruned children
                unpruned_children = [
                    cid
                    for cid in current.children
                    if tree.nodes.get(cid) and tree.nodes[cid].status != ThoughtStatus.PRUNED
                ]

                if not unpruned_children:
                    # Leaf node - this is a complete path
                    path_score = sum(tree.nodes[nid].score for nid in path if nid in tree.nodes) / len(path)
                    if path_score > best_score:
                        best_score = path_score
                        best_path = path
                    continue

                # Sort children by score (descending)
                unpruned_children.sort(key=lambda cid: tree.nodes[cid].score, reverse=True)

                # Keep top-k (beam width)
                for child_id in unpruned_children[: tree.max_branches]:
                    next_beam.append((child_id, path + [child_id]))

            if not next_beam:
                break

            beam = next_beam

        # Check remaining beam paths
        for current_id, path in beam:
            path_score = sum(tree.nodes[nid].score for nid in path if nid in tree.nodes) / len(path)
            if path_score > best_score:
                best_score = path_score
                best_path = path

        # Mark selected path
        tree.selected_path = best_path
        tree.completed_at = datetime.now().isoformat()
        for nid in best_path:
            if nid in tree.nodes:
                tree.nodes[nid].status = ThoughtStatus.SELECTED

        self._save_tree(tree)
        log.info(
            "[TreeOfThought] Selected best path for tree %s: %s (score: %.2f)",
            tree_id,
            " -> ".join(best_path[:5]),
            best_score,
        )

        return best_path

    def get_tree_summary(self, tree_id: str) -> Dict[str, Any]:
        """Get a summary of a tree."""
        tree = self._trees.get(tree_id)
        if not tree:
            return {}

        total_nodes = len(tree.nodes)
        explored = sum(1 for n in tree.nodes.values() if n.status == ThoughtStatus.EXPLORED)
        pruned = sum(1 for n in tree.nodes.values() if n.status == ThoughtStatus.PRUNED)
        selected = sum(1 for n in tree.nodes.values() if n.status == ThoughtStatus.SELECTED)

        return {
            "tree_id": tree_id,
            "total_nodes": total_nodes,
            "explored": explored,
            "pruned": pruned,
            "selected": selected,
            "max_depth": tree.max_depth,
            "max_branches": tree.max_branches,
            "selected_path_length": len(tree.selected_path),
            "created_at": tree.created_at,
            "completed_at": tree.completed_at,
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get overall statistics."""
        return {
            "total_trees": len(self._trees),
            "trees": {
                tid: self.get_tree_summary(tid)
                for tid in list(self._trees.keys())[-10:]  # Last 10 trees
            },
        }


# Global reasoner instance
_reasoner: Optional[TreeOfThoughtReasoner] = None


def get_tot_reasoner(repo_dir: Optional[pathlib.Path] = None) -> TreeOfThoughtReasoner:
    """Get or create the global tree of thought reasoner."""
    global _reasoner
    if _reasoner is None:
        if repo_dir is None:
            repo_dir = pathlib.Path.cwd()
        _reasoner = TreeOfThoughtReasoner(repo_dir)
    return _reasoner
