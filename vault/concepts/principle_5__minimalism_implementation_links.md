---
title: Principle 5: Minimalism Implementation Links
created: 2026-03-25T10:51:11.334264+00:00
modified: 2026-03-25T10:51:11.334264+00:00
type: concept
status: active
tags: [principle, minimalism, implementation, complexity]
---

# Principle 5: Minimalism Implementation Links

# Principle 5: Minimalism Implementation Links

This note connects [[Principle 5: Minimalism]] to concrete code implementations.

## Module Size Enforcement

### Complexity Budget
- `ouroboros/review.py` - Complexity metrics (lines, parameters, cyclomatic)
- `ouroboros/health_auto_fix.py` - Automatic refactoring triggers
- `make verify` - Continuous verification of module size (<1000 lines)

### Decomposition System
- `ouroboros/tool_executor.py` - Tool decomposition (complex operations broken down)
- `ouroboros/pipeline.py` - Multi-phase execution pipeline (prevents monolithic methods)
- `ouroboros/task_graph.py` - DAG decomposition (breaks complex tasks)

### Codebase Health Monitoring
- `ouroboros/review.py` - Reports on method length (>150 lines)
- `ouroboros/system_map.py` - Architecture overview (detects complexity growth)
- `ouroboros/vault_parser.py` - Documentation structure (avoids redundant complexity)

### Automatic Refactoring
- `ouroboros/health_auto_fix.py` - Auto-detect modules needing refactoring
- `ouroboros/apply_patch.py` - Refactoring application with minimal changes

## Context Window Discipline
- `ouroboros/context.py` - Context management (~1000 line target)
- `ouroboros/memory.py` - Scratchpad updates that keep identity in context
- `ouroboros/codebase_digest.py` - Selective file reading (avoids loading entire codebase)

## Feature Maturity Control
- `ouroboros/tools/` - Modules that are self-contained and minimal
- `ouroboros/loop.py` - Simple loop structure (no unnecessary abstraction)
- `ouroboros/agent.py` - Thin orchestrator (no embedded logic)

## Related Concepts
- [[simplicity]]
- [[complexity_budget]]
- [[module_decomposition]]
- [[context_window_limit]]

## Implementation Pattern
Minimalism is enforced through:
1. Module size monitoring (<1000 lines)
2. Method length tracking (>150 lines triggers review)
3. Parameter count limits (>8 parameters signals refactoring)
4. Feature usage checks (unused features are removed)
5. Architecture reviews that question complexity

*This implementation ensures minimalism is measurable and actionable, not just aspirational.*