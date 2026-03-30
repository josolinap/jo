---
title: Confidence
created: 2026-03-30T15:34:51.754073+00:00
modified: 2026-03-30T15:34:51.754073+00:00
type: concept
status: active
tags: [confidence, system]
---

# Confidence

# Confidence

Trust level in Jo's decisions, classifications, and outputs.

## Definition
Confidence is a numeric score (0.0-1.0) representing how sure Jo is about:
- Task classification accuracy
- Tool selection relevance
- Output correctness
- Strategy effectiveness

## Components

### Classification Confidence
From `dspy_classify`: How certain the system is about task type and intent.

### Selection Confidence
From `dspy_select_tools`: Belief that chosen tools will accomplish the task.

### Verification Confidence
From `dspy_verify`: Assessment that output has no issues.

### Routing Confidence
From `dspy_route`: Certainty about the execution strategy.

## Thresholds

- **High (>0.8)**: Proceed automatically, no additional checks
- **Medium (0.5-0.8)**: Verify with fallback mechanisms or secondary checks
- **Low (<0.5)**: Request clarification, use conservative defaults, log for review

## Evolution

Confidence scoring is itself optimized through the `dspy_optimize` cycle, learning from outcomes of past decisions.

## Related
- [[Confidence Scoring System]]
- [[Verification Protocols]]