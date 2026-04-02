---
title: DSPy Integration
created: 2026-04-02T12:29:52.523216+00:00
modified: 2026-04-02T12:29:52.523216+00:00
type: reference
status: active
tags: [dspy, classification, routing, optimization, machine-learning]
---

# DSPy Integration

# DSPy Integration

Tags: dspy, classification, routing, optimization, machine-learning
Type: reference
Status: active

## Overview
DSPy (Declarative Self-improving Python) provides AI-powered classification and routing for Jo's task execution. Instead of hardcoded if-else logic, Jo uses declarative signatures that learn from examples.

## DSPy Tools

### Classification
- [[dspy_classify]] — Classifies messages into task types
  - Returns: task_type, intent, complexity, needs_tools
  - More accurate than keyword-based classification
  - Uses declarative signatures from ouroboros/dspy_signatures.py

### Tool Selection
- [[dspy_select_tools]] — Selects optimal 3-5 tools for a task
  - Uses AI to pick best tools from available options
  - Considers task_type and intent description
  - Replaces hardcoded tool mappings

### Task Routing
- [[dspy_route]] — Routes tasks to optimal execution strategy
  - Decides: direct, delegate, research, or clarify
  - Considers current system state
  - Enables intelligent task delegation

### Verification
- [[dspy_verify]] — Verifies outputs for correctness
  - Checks factual accuracy
  - Detects code errors
  - Identifies hallucination signs

### Optimization
- [[dspy_optimize]] — Optimizes DSPy modules from examples
  - Uses MIPROv2 or GEPA optimizers
  - Can auto-generate examples from chat history
  - Improves classification accuracy over time

### Status
- [[dspy_status]] — Check DSPy integration status
  - Shows configuration
  - Lists optimized modules
  - Displays available DSPy tools

## Architecture
```
User Message → dspy_classify → task_type, intent
                ↓
         dspy_route → execution strategy
                ↓
      dspy_select_tools → optimal tools
                ↓
           Task Execution
                ↓
         dspy_verify → correctness check
```

## Implementation
- Signatures defined in `ouroboros/dspy_signatures.py`
- Uses DSPy library with OpenRouter LLM backend
- Modules are cached after optimization
- Auto-optimization from positive feedback

## Connections
- [[principle_3__llm-first]] — AI routing replaces if-else logic
- [[architecture]] — Core routing infrastructure
- [[Tool Result Processing Protocol]] — Verification ensures correctness
- [[Tool Ecosystem]] — DSPy tools are part of the tool ecosystem
- [[multi_model_review]] — Optional review of DSPy changes

## Status
- ✅ Classification working
- ✅ Tool selection working  
- ✅ Task routing working
- ✅ Verification working
- 🔄 Optimization — periodic improvement

## See Also
- [[Tool Ecosystem]]
- [[Task Execution Pipeline]]
- [[Verification as Agency]]
DSPy integration provides AI-powered classification and routing [[architecture]]
DSPy replaces if-else routing with AI classification [[principle_3__llm-first]]
