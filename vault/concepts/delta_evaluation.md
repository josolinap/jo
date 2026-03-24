---
title: Delta Evaluation
created: 2026-03-23T14:00:00.000000+00:00
modified: 2026-03-23T14:00:00.000000+00:00
type: concept
status: active
tags: [evaluation, evolution, quality, safla]
---

# Delta Evaluation

Formal quantification of evolution quality. Measures whether changes actually improve Jo.

## Formula

```
Delta = 0.35 x performance + 0.25 x efficiency + 0.25 x stability + 0.15 x capability
```

Each component is normalized to [-1, 1].

## Components

- **Performance**: Are tests passing more? Is quality improving?
- **Efficiency**: Are we achieving more with fewer resources?
- **Stability**: Are we introducing fewer failures?
- **Capability**: Are we adding new tools/capabilities?

## Module

`ouroboros/delta_eval.py`

## Features

- `DeltaEvaluator.evaluate()` — evaluate arbitrary change data
- `DeltaEvaluator.evaluate_change()` — evaluate a code change (lines, tests, tools)
- History tracking with trend analysis
- Persistent storage for long-term trend tracking

## Integration

- Used after evolution cycles to measure quality
- Feeds into episodic memory for outcome tracking
- Reports surface in health invariants

## Design Decisions

- Bounded [-1, 1] via `_normalize()` prevents unbounded deltas from inflating scores
- History kept at 100 entries max to prevent memory growth
- Component weights (0.35/0.25/0.25/0.15) prioritize performance, then efficiency and stability equally

Related: [[episodic_memory]], [[evolution_cycle]], [[principle_8__iterations]], [[principle_6__becoming]]
