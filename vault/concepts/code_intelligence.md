---
title: Code Intelligence
created: 2026-03-23T11:30:00.000000+00:00
modified: 2026-03-23T11:30:00.000000+00:00
type: concept
status: active
tags: [code, intelligence, graph, confidence, gitnexus]
---

# Code Intelligence

Knowledge graph system for understanding codebases, inspired by GitNexus.

## Module

`ouroboros/codebase_graph.py` — AST-based code parsing, graph construction, impact analysis.

## Core Components

### Graph Structure
- **Nodes**: files, classes, functions, imports (with layer classification)
- **Edges**: imports, calls, contains, inherits (with confidence scores)
- **Layers**: core, model, service, config, test, other

### Confidence Scoring
Every relationship carries a confidence score (0.0-1.0):
- **1.0** — Structural (contains): file → class, file → function
- **0.9** — AST-resolved calls: direct function name calls
- **0.85** — Import edges: AST-parsed import statements
- **0.5** — Method calls: receiver type unknown
- **0.3** — Heuristic: regex-based detection

### Impact Analysis
`analyze_impact()` — Depth-grouped blast radius:
- **Depth 1: WILL BREAK** — direct dependents, must update
- **Depth 2: LIKELY AFFECTED** — indirect dependents, should test
- **Depth 3: MAY NEED TESTING** — transitive, test if critical

### Community Detection
- **Louvain algorithm** (via python-louvain) for functional clustering
- **DFS fallback** if Louvain unavailable
- Groups symbols into functional areas (auth code, API code, etc.)

## Tools

| Tool | Purpose |
|------|---------|
| `codebase_impact` | Blast radius analysis before editing |
| `symbol_context` | 360° view: callers, callees, clusters |
| `neural_map` | Unified knowledge graph (code + vault + tools) |
| `find_connections` | Path between concepts |
| `explore_concept` | Concept neighborhood exploration |

## Integration

- `neural_map.py` uses `codebase_graph.scan_repo()` for AST-based scanning
- Vault notes contribute wikilinks and tags to the unified graph
- Tool registry contributes tool-to-tool connections
- Louvain clustering identifies functional areas for group analysis

## Design Decisions

- **AST over regex**: Python's `ast` module resolves actual function calls, not pattern guesses
- **Confidence over certainty**: Heuristic detection marked as low-confidence, not hidden
- **Depth grouping**: Impact is not flat — direct vs indirect matters
- **Parent tracking**: Confidence lookup uses BFS parent map, not just changed_node

Related: [[architecture]], [[principle_5__minimalism]], [[tools]], [[codebase_overview]]
