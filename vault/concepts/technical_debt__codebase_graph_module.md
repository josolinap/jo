---
title: Technical Debt: Codebase Graph Module
created: 2026-03-26T15:33:46.643321+00:00
modified: 2026-03-26T15:33:46.643321+00:00
type: reference
status: active
tags: [technical-debt, refactoring, principle-5, codebase-graph]
---

# Technical Debt: Codebase Graph Module

# Technical Debt: Codebase Graph Module

## Issue
**File**: `ouroboros/codebase_graph.py`
**Problem**: 1354 lines violating Principle 5 (Minimalism)
**Root Cause**: Combines two unrelated systems

### Current Structure
```python
# Lines 24-574: CodebaseGraph class
# Graph operations, file parsing, dependency analysis

# Lines 1067-end: OntologyTracker class  
# Tool usage tracking, task relationship learning
```

## Recommended Refactoring

### Option 1: Module Separation (Preferred)
- Create `ouuroboros/tools/ontology_tracker.py` (not possible - directory protected)
- Move OntologyTracker class (247 lines)
- Keep CodebaseGraph in current location
- **Reduces main module to ~900 lines**

### Option 2: Package Structure
- Create `ouroboros/graph/` package
- `graph/base.py` - GraphNode, GraphEdge classes
- `graph/codebase.py` - CodebaseGraph class  
- `graph/ontology.py` - OntologyTracker class
- **Clean separation of concerns**

## Impact Analysis
- **Downstream dependencies**: None (OntologyTracker has no dependents)
- **Risk level**: LOW
- **Testing impact**: Minimal (preserves all APIs)

## Implementation Notes
- Global singleton pattern must be preserved
- Utility functions must remain accessible
- Persistence path handling unchanged

## Status
**Blocked by**: `.jo_protected` directory protection on ouroboros/
**Requires**: Human approval for core module modifications
**Alternative**: Wait for protection to be lifted or use emergency override

## Context
This is the most egregious violation of Principle 5 and the logical first step in the 5-module technical debt reduction plan. Decomposition of this module alone would make a significant improvement to system maintainability.