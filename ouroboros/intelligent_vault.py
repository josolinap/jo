"""Intelligent Vault System — re-export layer for backward compatibility.

Split from 1616 lines into:
- vault_engine.py (540 lines) — graph engine, quality metrics
- vault_improvements.py (665 lines) — guardrails, auto-linking, auto-fixing
- vault_search.py (445 lines) — semantic search, topic clustering, knowledge gaps

This file re-exports all public symbols for backward compatibility.
New code should import directly from the submodules.
"""

from __future__ import annotations

# Re-export from vault_engine
from ouroboros.vault_engine import (
    VaultGraphEngine,
    VaultNote,
    VaultGraph,
    QualityMetrics,
    get_vault_engine,
)

# Re-export from vault_improvements
from ouroboros.vault_improvements import (
    LinkSuggestion,
    QualityViolation,
    VaultHealthReport,
    VaultGuardrails,
    VaultAutoLinker,
    ImprovementResult,
    VaultAutoFixer,
    get_vault_health_report,
    execute_vault_improvements,
)

# Re-export from vault_search
from ouroboros.vault_search import (
    SearchResult,
    TopicCluster,
    KnowledgeGap,
    VaultSemanticSearch,
    VaultTopicClustering,
    VaultKnowledgeGaps,
    vault_semantic_search,
    vault_topic_clusters,
    vault_knowledge_gaps,
)
