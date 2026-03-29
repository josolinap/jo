---
title: Research - Model-Independent Agent Architectures
created: 2026-03-29T13:00:00+00:00
modified: 2026-03-29T13:00:00+00:00
type: concept
status: active
tags: [research, architecture, model-independent, tools, self-improvement]
---

# Research: Model-Independent Agent Architectures

## Core Insight: Make the Tools Good, Not the Model

The key insight from research: **Quality belongs in the tools, not the LLM**.

```
Bad:   Model quality = Agent quality
Good:  Tool quality = Agent quality (model-independent)
```

---

## Key Projects & Ideas

### 1. Claude Code - "Code Mode" (1406 stars)
**Key Innovation**: Keep tool results OUT of context window

- Tool executes → result goes to separate channel
- LLM only sees SUMMARY, not raw output
- Prevents context bloat, faster iterations

**For Jo**: Add `code_mode` tool handler that returns summaries instead of full output

```python
# Instead of returning 50KB of file contents
# Return: "file.py: 234 lines, imports: os, sys, json"
```

---

### 2. Deterministic Governance Kernels (Zylos Research)
**Key Innovation**: Control plane separated from LLM

- Exit conditions checked BEFORE asking LLM
- Budget limits enforced deterministically
- Tool timeouts enforced without LLM

**For Jo**: Move budget/burn_rate checks BEFORE loop, not after

```python
# BEFORE calling LLM:
if budget_check_fails():
    return "Budget exceeded"  # No LLM call needed
```

---

### 3. Self-Improving Coding Agent (295 stars)
**Key Innovation**: Agent edits itself with verification

- Agent can modify code BUT must pass tests
- Changes verified before commit
- Builds in "improvement only if safer" constraint

**For Jo**: Already does this, but could add:
- automatic test generation before code changes
- "safety score" that must increase, not decrease

---

### 4. Agent0 - Self-Evolving from Zero Data (1103 stars)
**Key Innovation**: Starts minimal, learns to improve itself

- No hardcoded capabilities
- Discovers patterns, then uses them
- Memory → → meta-cognition → error recovery

**For Jo**: Could learn which skills work together

---

### 5. autocontext - Recursive Self-Improving (674 stars)
**Key Innovation**: "Context as a control mechanism"

- Agent improves its prompts/context
- Uses outcome feedback to adapt
- Not just improving code, improving thinking

**For Jo**: Add skill effectiveness tracking

---

### 6. Open-Sable - AGI-Inspired Cognitive Subsystems
**Key Innovation**: Multiple independent subsystems

- Goals subsystem
- Memory subsystem  
- Metacognition subsystem
- Tool use subsystem

**For Jo**: Already has these via tools! Could formalize into explicit packages

---

## Architecture Patterns for Model-Independence

### Pattern 1: Tool Result Summarization
```
LLM asks: "search code for X"
Tool does: Search 10K lines
Tool returns to LLM: "Found 3 matches in files: A.py, B.py, C.py"
Tool returns to context: FULL Results (if needed)
```

### Pattern 2: Pre-Flight Checks (Deterministic First)
```python
def should_continue():
    # These are deterministic - no LLM needed
    if not task.is_valid():
        return False, "Invalid task"
    if budget.exceeded():
        return False, "Budget exceeded"
    if token_limit_reached():
        return False, "Context limit"
    return True, None
```

### Pattern 3: Tool-Level Validation (Not LLM-Level)
```python
# LLM suggests code - we VALIDATE without asking LLM
def validate_code(code):
    # Syntax check - deterministic
    if not syntax_valid(code):
        return False, "Syntax error"
    # Security check - deterministic  
    if dangerous_patterns(code):
        return False, "Security warning"
    # Test run - deterministic
    if not test_passes(code):
        return False, "Tests failed"
    return True, "Valid"
```

### Pattern 4: Cross-Tool Learning
```python
# Track which tool combinations WORK
skill_effectiveness = {
    "code_edit + repo_commit": 0.95,  # high success
    "web_search + analyze_screenshot": 0.72,
    ...
}
# Suggest based on historical success, not just "sounds good"
```

---

## Ideas to Implement in Jo

### HIGH PRIORITY

1. **Code Mode for Tools**
   - Add `summarize_tool_result=True` parameter
   - Return short summary, full result in separate channel
   - Prevents context bloat with large tool outputs

2. **Pre-Flight Checks**
   - Move budget/burn rate checks to BEFORE LLM call
   - Add timeout checks deterministically
   - Fail fast without wasting LLM calls

3. **Tool-Level blind_validate**
   - Already exists but strengthen it
   - Make validation deterministic: syntax, security, tests
   - LLM writes, TOOL validates

### MEDIUM PRIORITY

4. **Skill Effectiveness Tracking**
   - Track: which skill combinations succeed
   - Suggest based on history, not just intuition
   - Add to `skill_logging.py`

5. **Checkpoint with Context Hash**
   - If same context (task + tools + results) seen before
   - Skip to next step instead of re-doing work
   - Deterministic deduplication

### LOWER PRIORITY

6. **Agent Team Orchestration**
   - Delegate pattern: specialized sub-agents
   - Each with specific tools, better than one LLM doing all

---

## Related Notes

- [[jo_core_algorithm]] - Jo core methodology
- [[module_decomposition_plan]] - Technical refactoring
- [[blind_validate]] - Tool validation
- [[Background Consciousness Loop]]

## Sources

- Claude Code architecture (82K stars)
- Deterministic Governance Kernels (Zylos Research)
- Self-Improving Coding Agent (Robeyns et al.)
- Agent0 (1103 stars)
- autocontext (674 stars)
- Open-Sable (local-first autonomous agent)

