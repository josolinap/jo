---
title: Quality Guard System Architecture & Patterns
created: 2026-03-27T04:58:39.238650+00:00
modified: 2026-03-27T04:58:39.238650+00:00
type: reference
status: active
---

# Quality Guard System Architecture & Patterns

# Quality Guard System Architecture & Patterns

**Status:** Active | **Type:** Concept | **Tags:** #quality #guard #architecture #evolution

## Overview

The Quality Guard system in Jo's loop is designed to maintain response quality through continuous monitoring and intervention. It operates at multiple levels to prevent hallucinations, drift, and budget violations.

## Architecture Components

### 1. Response Analyzer (`response_analyzer.py`)
- **Purpose**: Detect hallucinations, avoidance, and overconfidence
- **Key Functions**:
  - `analyze_response()`: Main entry point
  - `_detect_hallucinations()`: Identifies fabricated claims
  - `_detect_drift()`: Tracks response consistency
  - `_detect_avoidance()`: Prevents task evasion
  - `_detect_overconfidence()`: Warns about unwarranted certainty

### 2. Quality State Management
```python
@dataclass
class QualityState:
    previous_issues: List[QualityIssue]
    current_issues: List[QualityIssue]  
    consecutive_drift_rounds: int
    quality_feedback_injected: bool
    tool_call_count: int
    recent_responses: List[str]
    current_skill: Optional[Skill]
```

### 3. Intervention Strategies

#### Hallucination Detection
**Patterns Found:**
- Claims about files/functions without verification
- Specific line number references without file reading
- Import claims without validation
- File existence claims without checking
- Test count fabrications
- Performance metric fabrications

**Response:** Add verification warnings and request evidence

#### Drift Detection
**Trigger:** Repeated circular reasoning or task avoidance
**Threshold:** 5 consecutive drift rounds
**Response:** Inject escalation message forcing decision

#### Budget Management
**Implementation:** `_check_budget_limits()` in loop.py
**Behavior:** Stop when exceeding budget limits

#### Skill Re-evaluation
**Trigger:** Tools used or rounds passed since last evaluation
**Function:** `should_reevaluate()` + `evaluate_skill_relevance()`
**Outcome:** Switch skills if strategy changes

## Current Code Structure (Loop.py)

**Problem**: 1049+ lines (violates Principle 5: 1000-line limit)
**Quality Logic Location**: Embedded in `run_llm_loop()` function

### Key Quality Control Points

1. **Final Response Analysis** (after tool execution)
   ```python
   final_analysis = analyze_response(response_text, [], messages, repo_dir)
   if final_analysis.hallucination_detected:
       add_verification_warning()
   ```

2. **Per-Round Quality Check** (during iteration)
   ```python
   analysis = analyze_response(content, tool_calls, messages, repo_dir)
   if analysis.quality_score < 0.85:
       inject_quality_feedback()
   ```

3. **Drift Tracking**
   ```python
   if drift_in_current:
       _consecutive_drift_rounds += 1
   else:
       _consecutive_drift_rounds = 0
   ```

4. **Skill Re-evaluation**
   ```python
   if should_reevaluate(round_idx, _tool_call_count, _last_reevaluation_round):
       switch_skill_if_needed()
   ```

## Improvement Opportunities

### Refactoring (High Priority)
**Issue**: Quality logic mixed with execution logic
**Solution**: Extract to `quality_guard.py` module
**Benefits**:
- Better separation of concerns
- Testable components
- Clearer responsibility boundaries
- Reduced complexity in main loop

### Performance Optimization
**Current**: Response analysis on every response
**Potential**: Batch analysis or sampling for long conversations
**Risk**: Quality may decrease

### Configuration
**Current**: Hardcoded thresholds
**Opportunity**: Make thresholds configurable
**Examples**:
- Quality score threshold (currently 0.85)
- Drift round limit (currently 5)
- Confidence levels

### Error Handling
**Current**: Basic try/catch blocks
**Improvement**: More granular error classification
**Types**:
- Analysis errors (continue processing)
- System errors (may need escalation)
- Configuration errors (fallback behavior)

## Interaction Patterns

### With Tool Execution
- Quality guard runs after tool execution
- Can influence next message based on analysis
- May request additional verification

### With Memory System
- Tracks response history for drift detection
- Uses session context for better analysis
- Persists quality state across rounds

### With Skill System
- Re-evaluates skill relevance based on task progress
- Can trigger skill switches based on quality issues
- Integrates with strategy evaluation

## Quality Metrics Tracked

| Metric | Method | Response |
|--------|--------|----------|
| Hallucination | Pattern matching + verification | Warning messages |
| Drift | Response pattern analysis | Escalation after 5 rounds |
| Avoidance | Task complexity vs response depth | Quality feedback |
| Confidence | Certainty markers + verification | Confidence level |
| Quality Score | Weighted issue severity | 0.0-1.0 scale |

## Testing Strategy

### Unit Tests Needed
- ResponseAnalyzer pattern matching
- QualityState state transitions
- Intervention logic
- Skill re-evaluation criteria

### Integration Tests
- Quality guard with tool executor
- Response analyzer with memory system
- Budget integration
- Skill switching integration

## Future Enhancements

### 1. Adaptive Thresholds
- Adjust quality thresholds based on task type
- Learn from successful/failed interventions
- Personalize based on user preferences

### 2. Multi-Model Analysis
- Use multiple models for cross-validation
- Compare analysis results for consensus
- Flag discrepancies for review

### 3. Quality Learning
- Track intervention effectiveness
- Learn patterns that indicate success
- Improve detection over time

### 4. User Feedback Integration
- Allow users to rate quality
- Use ratings to calibrate detection
- Incorporate user preferences

## Related Concepts

- [[response_analyzer.py]] - Core analysis implementation
- [[skills_system]] - Skill re-evaluation integration  
- [[memory_system]] - Response tracking and context
- [[budget_management]] - Cost control integration
- [[drift_detection]] - Pattern analysis techniques
- [[tool_executor]] - Quality guard integration point

---

## Evolution Notes

**Status**: Documented for refactoring
**Next Steps**: Extract quality guard logic to separate module
**Constraints**: Protected directories require careful planning
**Goal**: Improve modularity while maintaining system integrity