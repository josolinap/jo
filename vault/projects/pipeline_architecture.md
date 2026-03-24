---
title: Kong-Inspired Pipeline Architecture
created: 2026-03-25
category: projects
tags:  []

---

# Kong-Inspired Pipeline Architecture

## Overview

This document describes Jo's enhanced pipeline architecture, inspired by Kong's agentic reverse engineering system.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              JO AGENT                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐                   │
│  │  Context   │────▶│    LLM      │────▶│    Tool     │                   │
│  │  Enricher  │     │    Loop     │     │  Executor   │                   │
│  └─────────────┘     └─────────────┘     └─────────────┘                   │
│         │                   │                   │                           │
│         │                   ▼                   │                           │
│         │           ┌─────────────┐            │                           │
│         │           │ Normalizer  │◀───────────┘                           │
│         │           └─────────────┘                                        │
│         │                   │                                              │
│         ▼                   ▼                                              │
│  ┌─────────────────────────────────────────────────────┐                   │
│  │                   PIPELINE                           │                   │
│  ├─────────────────────────────────────────────────────┤                   │
│  │  1. DIAGNOSE  →  2. PLAN  →  3. EXECUTE            │                   │
│  │  4. VERIFY    →  5. SYNTHESIZE                      │                   │
│  └─────────────────────────────────────────────────────┘                   │
│                           │                                                │
│                           ▼                                                │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐                   │
│  │    Eval     │     │  Synthesis  │     │Task Graph   │                   │
│  │ (Quality)   │     │(Consistency)│     │(Dependencies)│                   │
│  └─────────────┘     └─────────────┘     └─────────────┘                   │
│                                                                             │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐                   │
│  │ Consciousness│───▶│  Awareness  │     │Cost Tracker │                   │
│  │ (Background) │    │  (Scanner)  │     │  (Budget)   │                   │
│  └─────────────┘     └─────────────┘     └─────────────┘                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Components

### Core Pipeline (`pipeline.py`)

Formalized 5-phase execution:

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  DIAGNOSE    │───▶│    PLAN      │───▶│   EXECUTE    │───▶│    VERIFY    │───▶│  SYNTHESIZE  │
│              │    │              │    │              │    │              │    │              │
│ • Classify   │    │ • Decompose  │    │ • Run tools  │    │ • Eval task  │    │ • Consistency│
│ • Complexity │    │ • TaskGraph  │    │ • Gather     │    │ • Quality    │    │ • Refactor   │
│ • Constraints│    │ • Dependencies│   │   data      │    │   checks    │    │   hints      │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
```

### Pre-Processing (`normalizer.py`)

Cleans code before LLM:

- Removes trailing whitespace
- Removes debug statements  
- Normalizes docstrings
- Truncates with structure preservation

### Context Enrichment (`context_enricher.py`)

Pre-fetches relevant context:

- Finds relevant files by keywords
- Gets recent git changes
- Extracts code patterns
- Builds enriched context text

### Quality Evaluation (`eval.py`)

Scores task outputs:

| Metric | What it checks |
|--------|---------------|
| Syntax | Python files compile |
| Completeness | Task appears done |
| Consistency | Naming conventions |
| Test Coverage | Tests added |
| Readability | Line lengths |

### Semantic Synthesis (`synthesis.py`)

Post-task consistency checks:

| Check | Description |
|-------|-------------|
| Naming | snake_case vs camelCase |
| Imports | Organization (stdlib → third-party → local) |
| Docstrings | Coverage of public functions |
| Formatting | Quote style consistency |
| Refactor | Long functions, repeated code |

### Task Graph (`task_graph.py`)

Dependency-ordered execution:

```
For complex tasks:
    ┌─────────┐
    │ Analyze │ ← No dependencies
    └────┬────┘
         │
    ┌────▼────┐
    │  Plan   │ ← Depends on Analyze
    └────┬────┘
         │
    ┌────▼────┐
    │Implement│ ← Depends on Plan
    └────┬────┘
         │
    ┌────▼────┐
    │  Test   │ ← Depends on Implement
    └────┬────┘
         │
    ┌────▼────┐
    │ Review  │ ← Depends on Test
    └─────────┘
```

### Background Systems

#### Consciousness (`consciousness.py`)
- Persistent background thinking
- Uses Awareness for state scanning
- Low-priority task processing

#### Awareness (`awareness.py`)
- System-wide state monitoring
- Repository file scanning
- Git state tracking
- Environment detection

#### Cost Tracker (`cost_tracker.py`)
- Per-task cost breakdown
- Model pricing
- Budget estimation

## Feature Flags

| Variable | Default | Description |
|----------|---------|-------------|
| `OUROBOROS_NORMALIZE_CODE` | `1` | Normalize code before LLM |
| `OUROBOROS_ENRICH_CONTEXT` | `1` | Pre-fetch context |
| `OUROBOROS_EVAL` | `0` | Run quality evaluation |
| `OUROBOROS_SYNTHESIS` | `0` | Run consistency checks |
| `OUROBOROS_COST_TRACKING` | `1` | Track costs |
| `OUROBOROS_USE_PIPELINE` | `0` | Use structured pipeline |
| `OUROBOROS_TASK_GRAPH` | `0` | Use task graph |

## Integration Points

### Pipeline → TaskGraph
- PlanHandler uses `decompose_into_graph()` for complex tasks
- Sets active graph for orchestration

### Consciousness → Awareness  
- BackgroundConsciousness initializes AwarenessSystem
- Scans awareness at start of each think cycle

### Loop → Normalizer
- `repo_read` tool normalizes file contents
- Removes noise before LLM processing

### Loop → ContextEnricher
- Enriches messages at round 0
- Pre-fetches relevant files

### Loop → Eval/Synthesis
- Called at task completion
- Appends reports to final response

## Files

```
ouroboros/
├── pipeline.py           # 5-phase execution
├── task_graph.py         # Dependency execution
├── normalizer.py         # Code cleanup
├── context_enricher.py   # Context pre-fetch
├── eval.py               # Quality scoring
├── synthesis.py           # Consistency checks
├── cost_tracker.py       # Budget tracking
├── awareness.py          # System scanning
└── consciousness.py     # Background thinking
```
