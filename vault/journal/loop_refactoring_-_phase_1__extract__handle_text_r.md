---
title: Loop Refactoring - Phase 1: Extract _handle_text_response
created: 2026-03-27T03:06:54.077751+00:00
modified: 2026-03-27T03:06:54.077751+00:00
type: project
status: active
tags: [refactoring, loop, minimalism]
---

# Loop Refactoring - Phase 1: Extract _handle_text_response

# Loop Refactoring - Phase 1: Extract _handle_text_response

## Status
IN PROGRESS

## Goal
Reduce loop.py from 1386 lines to <1000 lines by extracting `_handle_text_response`.

## Analysis
Current violations:
- `_handle_text_response` is ~300+ lines with 6 distinct responsibilities:
  1. Final response formatting and trace logging
  2. Hallucination analysis and blocking
  3. Quality feedback injection
  4. Skill re-evaluation and switching
  5. Budget checking
  6. Resource cleanup

## Extraction Plan
Create `ouroboros/loop_components/` package:

1. `response_formatter.py` - Final response handling and trace logging
2. `hallucination_guard.py` - Hallucination detection and blocking logic
3. `quality_feedback.py` - Quality feedback injection
4. `skill_reevaluator.py` - Skill evaluation and switching
5. `budget_monitor.py` - Budget checking and limits

## Expected Outcome
- loop.py reduced by ~350 lines
- Each extracted module <200 lines
- Clear separation of concerns
- Easier to test each component independently

## Implementation Steps
1. Create `ouroboros/loop_components/__init__.py`
2. Extract functions in order of decreasing size:
   - Start with hallucination_guard (largest block)
   - Then quality_feedback
   - Then skill_reevaluator  
   - Then budget_monitor
   - Finally response_formatter
3. Update imports in loop.py
4. Run tests to verify no regressions
5. Update vault with results

---

*Started: 2026-03-27T03:00:00*
*Phase: Initial extraction of hallucination detection*