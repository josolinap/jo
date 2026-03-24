---
title: TrustGraph-Inspired Ontology System
created: 2026-03-25
category: concepts
tags:  []

---

# TrustGraph-Inspired Ontology System

## Overview

Jo uses an ontology-based system for precision task understanding, inspired by TrustGraph's approach to context graphs and semantic retrieval.

## How It Works

### 1. Task Classification

When a task comes in, `classify_task_ontology()` determines the task type:
- **debug**: Find and fix bugs
- **review**: Review code for quality
- **evolve**: Evolve codebase toward a goal
- **refactor**: Improve code structure
- **test**: Create or improve tests
- **implement**: Implement new features
- **analyze**: Analyze code structure

### 2. Ontology Definition

Each task type has an `OntologyDefinition`:
```python
OntologyDefinition(
    task_type="debug",
    requires=["error_message", "file_context", "stack_trace"],
    produces=["fix", "test", "verification"],
    typical_tools=["repo_read", "run_shell", "run_tests"],
    relationships=["calls", "imports", "contains"],
)
```

### 3. Relationship Tracking

The `OntologyTracker` learns which relationships are most useful:
- Tracks relationship strength (0.0-1.0)
- Counts usage per task type
- Strengthens useful relationships
- Weakens unused relationships

### 4. Integration with Loop

On the first round of task execution:
1. Task is classified into an ontology type
2. Ontology context is injected as a system message
3. LLM receives guidance on what the task requires/produces
4. Typical tools are suggested

## Key Files

| File | Purpose |
|------|---------|
| `ouroboros/codebase_graph.py` | Core implementation |
| `TASK_ONTOLOGY` | 7 task type definitions |
| `OntologyTracker` | Relationship learning |
| `classify_task_ontology()` | Task classification |
| `get_ontology_for_task()` | Get full ontology info |
| `enhance_graph_with_ontology()` | Add ontology to graph |

## Adding New Task Types

To add a new task type:
```python
TASK_ONTOLOGY["security"] = OntologyDefinition(
    task_type="security",
    requires=["target_code", "threat_model"],
    produces=["vulnerability_report", "fix"],
    typical_tools=["repo_read", "grep", "code_edit"],
    relationships=["imports", "calls", "contains"],
    description="Security analysis and fixes",
)
```

## Metrics

The ontology system tracks:
- Graph node/edge counts
- Tracker relationship count
- Most useful relationships per task type
- Relationship strength over time

## Future Enhancements

- [ ] Vector embeddings for semantic similarity
- [ ] Automatic ontology expansion from task outcomes
- [ ] Cross-task relationship learning
- [ ] Integration with skill outcomes tracking
