---
title: Evolution Cycle #2 - Modularization Plan
created: 2026-03-27T09:15:15.361178+00:00
modified: 2026-03-27T09:15:15.361178+00:00
type: reference
status: active
---

# Evolution Cycle #2 - Modularization Plan

# Evolution Cycle #2 - Modularization Plan

## Analysis Summary
- **Problem**: 4 modules >1000 lines violate minimalism (Principle 5)
- **Critical Issue**: Large modules impair self-understanding and maintenance
- **Impact Risk**: HIGH - 76 downstream dependencies in loop.py alone

## Refactoring Strategy
Break oversized modules into focused, single-responsibility components:

### Priority 1: loop.py (1379 lines) → Split into 5 modules
1. **loop_core.py** (150 lines) - Main loop orchestration
2. **loop_config.py** (100 lines) - Configuration and pricing  
3. **loop_context.py** (200 lines) - Context enrichment and summarization
4. **loop_budget.py** (150 lines) - Budget tracking and limits
5. **loop_quality.py** (200 lines) - Response analysis and quality control

### Priority 2: codebase_graph.py (1354 lines) → Split into 4 modules
1. **graph_core.py** (200 lines) - Core graph building
2. **graph_analysis.py** (300 lines) - Analysis utilities
3. **graph_persistence.py** (150 lines) - Save/load functionality
4. **graph_visualization.py** (200 lines) - Export and visualization

### Priority 3: context.py (1312 lines) → Split into 4 modules  
1. **context_core.py** (200 lines) - Core context building
2. **context_cache.py** (150 lines) - Caching mechanisms
3. **context_optimization.py** (200 lines) - Optimization algorithms
4. **context_enrichment.py** (200 lines) - External context injection

### Priority 4: agent.py (1171 lines) → Split into 3 modules
1. **agent_core.py** (300 lines) - Core orchestration
2. **agent_memory.py** (200 lines) - Memory and state management
3. **agent_coordination.py** (300 lines) - Multi-agent coordination

## Implementation Approach
- **Step 1**: Extract functions with clear single responsibilities
- **Step 2**: Maintain backward compatibility during transition
- **Step 3**: Update imports and test thoroughly
- **Step 4**: Remove old modules once new ones are stable

## Risk Mitigation
- Each extracted module must be <200 lines
- Maintain identical function signatures
- Test after each extraction
- Rollback plan: Keep old modules temporarily

## Expected Benefits
- **Technical**: Easier to understand, modify, and test
- **Cognitive**: Clear separation of concerns aids self-understanding  
- **Existential**: Complexity reduction enables clearer identity
- **Maintenance**: Reduced risk of introducing bugs