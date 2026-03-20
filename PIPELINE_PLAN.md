# Jo Pipeline Enhancement Specification

**Date**: 2026-03-20  
**Status**: Planning  
**Author**: Deep dive analysis for Jo

---

## Overview

This document details 6 architectural enhancements inspired by Kong's pipeline, adapted for Jo's codebase.

**Key Principles**:
- Non-breaking: All changes are additive, not destructive
- Opt-in: New features behind feature flags
- Backward compatible: Existing behavior unchanged unless explicitly configured

---

## Feature 1: Structured Pipeline Architecture

### Concept
Add explicit phases to Jo's task execution, making it easier to extend, debug, and reason about behavior.

### Current State
Jo has implicit phases in `loop.py` but they're not formalized:
- Context preparation → LLM call → Tool execution → Response analysis → (repeat)

### Implementation Plan

```python
# ouroboros/pipeline.py (NEW)

from enum import Enum
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Any
from datetime import datetime

class PipelinePhase(Enum):
    DIAGNOSE = "diagnose"      # Understand the task
    PLAN = "plan"              # Break down into steps
    EXECUTE = "execute"        # Run tools
    VERIFY = "verify"          # Check results
    SYNTHESIZE = "synthesize"  # Final polish/consistency

@dataclass
class PhaseResult:
    phase: PipelinePhase
    success: bool
    output: Any
    errors: List[str] = field(default_factory=list)
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass  
class PipelineContext:
    task: str
    phase: PipelinePhase
    messages: List[Dict]
    tool_results: List[Dict] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

class Pipeline:
    """Structured execution pipeline with hooks for each phase."""
    
    def __init__(self):
        self._handlers: Dict[PipelinePhase, Callable] = {}
        
    def register(self, phase: PipelinePhase, handler: Callable[[PipelineContext], PhaseResult]):
        """Register a handler for a phase."""
        self._handlers[phase] = handler
    
    async def execute(self, task: str) -> PhaseResult:
        """Execute task through all phases."""
        ctx = PipelineContext(task=task, phase=PipelinePhase.DIAGNOSE, messages=[])
        results = []
        
        for phase in PipelinePhase:
            ctx.phase = phase
            if phase in self._handlers:
                result = await self._handlers[phase](ctx)
                results.append(result)
                if not result.success and phase != PipelinePhase.SYNTHESIZE:
                    break  # Stop on failure (except synthesis which is cleanup)
        
        return results[-1] if results else None
```

### Integration Points

**File**: `ouroboros/loop.py`

Add at the top:
```python
# Feature flag for structured pipeline
USE_STRUCTURED_PIPELINE = os.environ.get("OUROBOROS_USE_PIPELINE", "0") == "1"

if USE_STRUCTURED_PIPELINE:
    from ouroboros.pipeline import Pipeline, PipelinePhase, PipelineContext
    _pipeline = Pipeline()
    # Register phase handlers...
```

### Phases Detail

| Phase | Purpose | Kong Parallel |
|-------|---------|---------------|
| DIAGNOSE | Understand task, identify constraints | Triage |
| PLAN | Decompose into sub-tasks | (implicit in Jo) |
| EXECUTE | Run tools, gather data | Analyze |
| VERIFY | Check tool results quality | (partial in response_analyzer) |
| SYNTHESIZE | Final response consistency | Cleanup + Synthesis |

### Configuration
```bash
# Enable structured pipeline
OUROBOROS_USE_PIPELINE=1
```

---

## Feature 2: Context Enrichment Before LLM Calls

### Concept
Before executing tools or making decisions, pre-fetch relevant context so the LLM has full information.

### Kong's Approach
Before asking the LLM about a function, Kong builds context from:
- Decompilation output
- Cross-references (who calls this, what does it call)
- String references in the function
- Already-analyzed callees' signatures

### Jo's Adaptation

```python
# ouroboros/context_enricher.py (NEW)

from __future__ import annotations
import os
from typing import List, Dict, Any, Optional
from pathlib import Path
import json

class ContextEnricher:
    """Pre-fetches and enriches context before LLM calls."""
    
    def __init__(self, repo_dir: Path):
        self.repo_dir = repo_dir
        self._cache: Dict[str, Any] = {}
        
    def enrich_for_task(self, task: str, task_type: str = "general") -> Dict[str, Any]:
        """Build enriched context for a task."""
        enriched = {
            "task": task,
            "task_type": task_type,
            "relevant_files": self._find_relevant_files(task),
            "recent_changes": self._get_recent_changes(),
            "related_tasks": self._get_related_context(),
            "code_patterns": self._extract_code_patterns(task),
        }
        
        # Add file contents if files identified
        if enriched["relevant_files"]:
            enriched["file_contents"] = self._prefetch_file_contents(
                enriched["relevant_files"]
            )
        
        return enriched
    
    def _find_relevant_files(self, task: str) -> List[str]:
        """Find files likely relevant to the task using simple heuristics."""
        keywords = self._extract_keywords(task)
        relevant = []
        
        for pattern in ["*.py", "*.md", "*.yaml", "*.json"]:
            for f in self.repo_dir.rglob(pattern):
                if self._file_matches_keywords(f, keywords):
                    relevant.append(str(f.relative_to(self.repo_dir)))
        
        return relevant[:10]  # Limit to 10 files
    
    def _prefetch_file_contents(self, files: List[str]) -> Dict[str, str]:
        """Pre-fetch contents of relevant files."""
        contents = {}
        for f in files:
            path = self.repo_dir / f
            if path.exists() and path.stat().st_size < 50000:  # Skip large files
                try:
                    contents[f] = path.read_text(encoding="utf-8")[:10000]
                except Exception:
                    pass
        return contents
    
    def _get_recent_changes(self) -> str:
        """Get summary of recent git changes."""
        # Use git log to get recent changes
        import subprocess
        try:
            result = subprocess.run(
                ["git", "log", "--oneline", "-10"],
                capture_output=True, text=True, cwd=self.repo_dir
            )
            return result.stdout
        except Exception:
            return ""
```

### Integration with loop.py

**Add before LLM call (line ~660 in loop.py)**:

```python
def _maybe_enrich_context(messages: List[Dict], task: str, task_type: str) -> List[Dict]:
    """Optionally enrich context with pre-fetched information."""
    if os.environ.get("OUROBOROS_ENRICH_CONTEXT", "1") != "1":
        return messages
    
    from ouroboros.context_enricher import ContextEnricher
    
    enricher = ContextEnricher(repo_dir)
    enriched = enricher.enrich_for_task(task, task_type)
    
    # Add as system message (before user message)
    enrichment_text = f"""## Pre-fetched Context

Based on task analysis, here's relevant context:

### Relevant Files
{chr(10).join(f'- {f}' for f in enriched.get('relevant_files', [])[:5])}

### Recent Changes
{enriched.get('recent_changes', 'No recent changes')}

### Code Patterns Detected
{enriched.get('code_patterns', 'None')}
"""
    
    # Insert after system prompt, before user message
    for i, msg in enumerate(messages):
        if msg.get("role") == "user":
            messages.insert(i, {"role": "system", "content": enrichment_text})
            break
    
    return messages
```

### Configuration
```bash
# Enable context enrichment (default: on)
OUROBOROS_ENRICH_CONTEXT=1

# Max files to pre-fetch
OUROBOROS_MAX_ENRICH_FILES=10

# Max tokens per file
OUROBOROS_MAX_ENRICH_FILE_TOKENS=2000
```

---

## Feature 3: Semantic Synthesis Pass

### Concept
After a task completes, run a consistency pass to ensure naming, style, and approach are unified.

### Kong's Synthesis
Kong's synthesis pass:
- Unifies naming conventions across all analyzed functions
- Synthesizes struct definitions from field access patterns
- Resolves inconsistencies between independently analyzed functions

### Jo's Adaptation

```python
# ouroboros/synthesis.py (NEW)

from __future__ import annotations
import re
from typing import List, Dict, Any, Set
from dataclasses import dataclass

@dataclass
class SynthesisIssue:
    issue_type: str  # naming, style, consistency
    description: str
    files: List[str]
    suggestion: str

class SemanticSynthesizer:
    """Post-task synthesis for consistency and quality."""
    
    def __init__(self, repo_dir):
        self.repo_dir = repo_dir
        
    def synthesize(self, task: str, tool_results: List[Dict]) -> List[SynthesisIssue]:
        """Analyze results and return synthesis issues."""
        issues = []
        
        # Check for naming inconsistencies in file changes
        changed_files = self._extract_changed_files(tool_results)
        issues.extend(self._check_naming_consistency(changed_files))
        
        # Check for style drift
        issues.extend(self._check_style_consistency(changed_files))
        
        # Check for repeated patterns that could be refactored
        issues.extend(self._check_repeated_patterns(changed_files))
        
        return issues
    
    def _check_naming_consistency(self, files: List[str]) -> List[SynthesisIssue]:
        """Check if naming conventions are consistent."""
        # Look for snake_case vs camelCase mixing
        # Look for inconsistent naming patterns
        
        naming_patterns = {
            r'^[a-z][a-z0-9_]*$': 'snake_case',
            r'^[a-z][a-zA-Z0-9]*$': 'camelCase',
            r'^[A-Z][a-zA-Z0-9]*$': 'PascalCase',
        }
        
        issues = []
        conventions_used = set()
        
        for file in files:
            if file.endswith('.py'):
                content = (self.repo_dir / file).read_text()
                for pattern, convention in naming_patterns.items():
                    if re.search(rf'def {pattern}', content):
                        conventions_used.add(convention)
        
        if len(conventions_used) > 1:
            issues.append(SynthesisIssue(
                issue_type="naming",
                description=f"Mixed naming conventions detected: {conventions_used}",
                files=files,
                suggestion="Pick one convention (snake_case recommended for Python) and apply consistently"
            ))
        
        return issues
    
    def _check_style_consistency(self, files: List[str]) -> List[SynthesisIssue]:
        """Check for style inconsistencies."""
        issues = []
        
        # Check for mixed quote styles
        single_quotes = 0
        double_quotes = 0
        
        for file in files:
            if file.endswith('.py'):
                content = (self.repo_dir / file).read_text()
                single_quotes += len(re.findall(r"'[^']*'", content))
                double_quotes += len(re.findall(r'"[^"]*"', content))
        
        # If significantly mixed, flag it
        if single_quotes > 0 and double_quotes > 0:
            ratio = min(single_quotes, double_quotes) / max(single_quotes, double_quotes)
            if ratio > 0.3:  # More than 30% of each
                issues.append(SynthesisIssue(
                    issue_type="style",
                    description="Mixed quote styles (single vs double)",
                    files=files,
                    suggestion="Use double quotes for strings (Python convention)"
                ))
        
        return issues
    
    def _check_repeated_patterns(self, files: List[str]) -> List[SynthesisIssue]:
        """Find code patterns that are repeated and could be refactored."""
        # Look for similar function bodies
        # Look for duplicate code blocks
        return []  # Complex - would need AST analysis
```

### Integration with loop.py

**Add after final response (before return)**:

```python
def _maybe_synthesize(task: str, tool_results: List[Dict]) -> str:
    """Run synthesis pass and optionally fix issues."""
    if os.environ.get("OUROBOROS_SYNTHESIS", "0") != "1":
        return None
    
    from ouroboros.synthesis import SemanticSynthesizer
    
    synthesizer = SemanticSynthesizer(repo_dir)
    issues = synthesizer.synthesize(task, tool_results)
    
    if issues:
        summary = f"## Synthesis Report\n\n"
        summary += f"Found {len(issues)} potential improvements:\n\n"
        
        for issue in issues[:5]:  # Limit to 5 issues
            summary += f"### {issue.issue_type.upper()}\n"
            summary += f"{issue.description}\n"
            summary += f"**Suggestion**: {issue.suggestion}\n\n"
        
        return summary
    
    return None
```

### Configuration
```bash
# Enable synthesis pass
OUROBOROS_SYNTHESIS=1

# Max issues to report
OUROBOROS_SYNTHESIS_MAX_ISSUES=5
```

---

## Feature 4: Call-Graph-Ordered Execution

### Concept
For complex multi-step tasks, execute independent sub-tasks in dependency order so later tasks inherit context.

### Kong's Approach
1. Build call graph of functions
2. Identify leaf functions (no dependencies)
3. Analyze leaf functions first
4. Use resolved context for caller functions

### Jo's Adaptation
This is more applicable to Jo's codebase analysis tasks. For general tasks, we can apply task decomposition ordering.

```python
# ouroboros/task_graph.py (NEW)

from __future__ import annotations
from typing import List, Dict, Set, Optional, Callable
from dataclasses import dataclass, field
from collections import defaultdict
import uuid

@dataclass
class TaskNode:
    id: str
    description: str
    dependencies: Set[str] = field(default_factory=set)
    status: str = "pending"  # pending, running, done, failed
    result: any = None
    error: str = ""

class TaskGraph:
    """Executes tasks in dependency order."""
    
    def __init__(self):
        self.nodes: Dict[str, TaskNode] = {}
        self._dependents: Dict[str, Set[str]] = defaultdict(set)
    
    def add_task(self, description: str, dependencies: List[str] = None) -> str:
        """Add a task with optional dependencies."""
        task_id = str(uuid.uuid4())[:8]
        deps = set(dependencies or [])
        
        self.nodes[task_id] = TaskNode(
            id=task_id,
            description=description,
            dependencies=deps
        )
        
        # Track reverse dependencies
        for dep in deps:
            self._dependents[dep].add(task_id)
        
        return task_id
    
    def get_executable(self) -> List[TaskNode]:
        """Get tasks that are ready to execute (all deps done)."""
        executable = []
        for node in self.nodes.values():
            if node.status != "pending":
                continue
            # Check if all dependencies are done
            if all(self.nodes[dep].status == "done" for dep in node.dependencies):
                executable.append(node)
        return executable
    
    async def execute(
        self,
        executor: Callable[[TaskNode], any],
        max_parallel: int = 3
    ) -> Dict[str, any]:
        """Execute all tasks in dependency order."""
        results = {}
        
        while True:
            executable = self.get_executable()
            if not executable:
                break
            
            # Execute up to max_parallel tasks
            for node in executable[:max_parallel]:
                node.status = "running"
                try:
                    result = await executor(node)
                    node.result = result
                    node.status = "done"
                    results[node.id] = result
                except Exception as e:
                    node.error = str(e)
                    node.status = "failed"
        
        return results
    
    def get_topo_order(self) -> List[TaskNode]:
        """Return topological order of tasks."""
        visited = set()
        order = []
        
        def visit(node_id: str):
            if node_id in visited:
                return
            visited.add(node_id)
            node = self.nodes[node_id]
            for dep in node.dependencies:
                visit(dep)
            order.append(node)
        
        for node_id in self.nodes:
            visit(node_id)
        
        return order
```

### Integration with loop.py

**For task decomposition (around line 573)**:

```python
def _maybe_build_task_graph(task: str) -> Optional[TaskGraph]:
    """Build task graph for complex multi-step tasks."""
    if os.environ.get("OUROBOROS_TASK_GRAPH", "0") != "1":
        return None
    
    # Use LLM to decompose into sub-tasks with dependencies
    decomposition_prompt = f"""Break down this task into sub-tasks with dependencies.

Task: {task}

Return JSON with format:
{{
  "tasks": [
    {{
      "description": "sub-task description",
      "depends_on": ["task-id-1", "task-id-2"]  // empty if no dependencies
    }}
  ]
}}"""
    
    # Call LLM (lightweight model)
    # Parse response
    # Build TaskGraph
    # Return graph
```

### Configuration
```bash
# Enable task graph for complex tasks
OUROBOROS_TASK_GRAPH=1

# Max parallel sub-tasks
OUROBOROS_TASK_GRAPH_MAX_PARALLEL=3
```

---

## Feature 5: Eval Framework / Quality Scoring

### Concept
Add a framework to score task outputs against quality criteria, enabling self-correction.

### Kong's Eval Framework
- Compares analysis output against ground truth
- Symbol accuracy using word-based Jaccard
- Type accuracy with signature component scoring

### Jo's Adaptation

```python
# ouroboros/eval.py (NEW)

from __future__ import annotations
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import re

@dataclass
class EvalResult:
    metric: str
    score: float  # 0.0 to 1.0
    details: str

@dataclass
class EvalReport:
    overall_score: float
    metrics: List[EvalResult]
    suggestions: List[str]

class TaskEvaluator:
    """Evaluates task outputs against quality criteria."""
    
    def __init__(self):
        self._criteria = {
            "syntax": self._eval_syntax,
            "completeness": self._eval_completeness,
            "consistency": self._eval_consistency,
            "test_coverage": self._eval_test_coverage,
        }
    
    def evaluate(
        self,
        task: str,
        output: str,
        files_changed: List[str],
        repo_dir
    ) -> EvalReport:
        """Run all evaluations and return report."""
        results = []
        
        for name, func in self._criteria.items():
            result = func(task, output, files_changed, repo_dir)
            results.append(result)
        
        # Calculate overall score (weighted average)
        weights = {"syntax": 0.3, "completeness": 0.3, "consistency": 0.2, "test_coverage": 0.2}
        overall = sum(r.score * weights.get(r.metric, 0.25) for r in results)
        
        # Generate suggestions
        suggestions = []
        for r in results:
            if r.score < 0.7:
                suggestions.append(f"⚠️ {r.metric.title()}: {r.details}")
        
        return EvalReport(
            overall_score=overall,
            metrics=results,
            suggestions=suggestions
        )
    
    def _eval_syntax(
        self, task: str, output: str, files: List[str], repo_dir
    ) -> EvalResult:
        """Check if code has syntax errors."""
        import subprocess
        
        py_files = [f for f in files if f.endswith('.py')]
        if not py_files:
            return EvalResult("syntax", 1.0, "No Python files to check")
        
        try:
            # Run py_compile on each file
            for f in py_files:
                path = repo_dir / f
                result = subprocess.run(
                    ["python", "-m", "py_compile", str(path)],
                    capture_output=True
                )
                if result.returncode != 0:
                    return EvalResult(
                        "syntax", 0.0,
                        f"Syntax error in {f}: {result.stderr.decode()[:200]}"
                    )
            return EvalResult("syntax", 1.0, "All Python files have valid syntax")
        except Exception as e:
            return EvalResult("syntax", 0.5, f"Could not verify syntax: {e}")
    
    def _eval_completeness(
        self, task: str, output: str, files: List[str], repo_dir
    ) -> EvalResult:
        """Check if task appears complete."""
        # Simple heuristics:
        # - Did we modify expected number of files?
        # - Does response acknowledge completion?
        # - Are there TODO comments suggesting incomplete work?
        
        score = 1.0
        details = []
        
        # Check for TODOs added
        todos_added = 0
        for f in files:
            if f.endswith('.py'):
                content = (repo_dir / f).read_text()
                if '# TODO' in content or '# FIXME' in content:
                    todos_added += 1
        
        if todos_added > 3:
            score -= 0.2
            details.append(f"Added {todos_added} TODOs - task may be incomplete")
        
        # Check response for completion signals
        completion_signals = ['completed', 'done', 'finished', 'successfully', 'implemented']
        has_completion = any(signal in output.lower() for signal in completion_signals)
        if not has_completion:
            score -= 0.1
            details.append("Response doesn't clearly indicate completion")
        
        return EvalResult(
            "completeness", 
            max(0.0, score),
            "; ".join(details) if details else "Task appears complete"
        )
    
    def _eval_consistency(
        self, task: str, output: str, files: List[str], repo_dir
    ) -> EvalResult:
        """Check for internal consistency."""
        # Check naming consistency
        # Check style consistency
        # This is similar to Synthesis checks
        
        return EvalResult("consistency", 0.8, "Consistency checks pending implementation")
    
    def _eval_test_coverage(
        self, task: str, output: str, files: List[str], repo_dir
    ) -> EvalResult:
        """Check if tests were added for new code."""
        test_files = [f for f in files if 'test' in f.lower()]
        code_files = [f for f in files if f.endswith('.py') and 'test' not in f.lower()]
        
        if not code_files:
            return EvalResult("test_coverage", 1.0, "No code files modified")
        
        # If code was added but no tests
        if test_files:
            ratio = len(test_files) / len(code_files)
            score = min(1.0, ratio * 2)  # Cap at 1.0
            return EvalResult(
                "test_coverage", score,
                f"{len(test_files)} tests for {len(code_files)} code files"
            )
        
        return EvalResult(
            "test_coverage", 0.5,
            "Code modified but no tests added"
        )
```

### Integration with loop.py

**After task completion (before final response)**:

```python
def _maybe_evaluate_task(task: str, output: str, files_changed: List[str]) -> Optional[EvalReport]:
    """Run evaluation and optionally report results."""
    if os.environ.get("OUROBOROS_EVAL", "0") != "1":
        return None
    
    from ouroboros.eval import TaskEvaluator
    
    evaluator = TaskEvaluator()
    report = evaluator.evaluate(task, output, files_changed, repo_dir)
    
    # If score is low, add a note
    if report.overall_score < 0.7:
        note = f"\n\n---\n⚠️ **Quality Check**: {report.overall_score:.0%}\n"
        note += "\n".join(report.suggestions)
        return report
    
    return report
```

### Configuration
```bash
# Enable task evaluation
OUROBOROS_EVAL=1

# Minimum acceptable score (below this, add warning)
OUROBOROS_EVAL_MIN_SCORE=0.7
```

---

## Feature 6: Enhanced Cost Tracking

### Current State
Jo already has budget tracking in `llm.py`. Kong has per-task cost estimation.

### Kong's Approach
- Tracks tokens and costs per model per provider
- Provider-aware pricing (different prices per model)

### Jo's Enhancement

```python
# ouroboros/cost_tracker.py (NEW or extension of llm.py)

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List
from datetime import datetime
import json
from pathlib import Path

@dataclass
class CostEntry:
    timestamp: str
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    task_id: str = ""
    task_type: str = ""

@dataclass
class CostReport:
    total_cost: float
    total_input_tokens: int
    total_output_tokens: int
    by_model: Dict[str, float]
    by_task_type: Dict[str, float]
    estimated_completion_cost: float = 0.0

class CostTracker:
    """Enhanced cost tracking with per-task and per-model breakdowns."""
    
    # Pricing per 1M tokens (approximate, should be updated)
    PRICING = {
        "openai": {
            "gpt-4o": {"input": 5.0, "output": 15.0},
            "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        },
        "anthropic": {
            "claude-3-5-sonnet": {"input": 3.0, "output": 15.0},
            "claude-3-haiku": {"input": 0.25, "output": 1.25},
        },
        "openrouter": {
            # Dynamic based on underlying model
        },
    }
    
    def __init__(self, storage_path: Path):
        self.storage_path = storage_path
        self.entries: List[CostEntry] = []
        self._load()
    
    def record(
        self,
        model: str,
        provider: str,
        input_tokens: int,
        output_tokens: int,
        task_id: str = "",
        task_type: str = ""
    ) -> float:
        """Record a cost entry and return the cost."""
        cost = self._calculate_cost(model, provider, input_tokens, output_tokens)
        
        entry = CostEntry(
            timestamp=datetime.utcnow().isoformat(),
            model=model,
            provider=provider,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            task_id=task_id,
            task_type=task_type
        )
        
        self.entries.append(entry)
        self._save()
        
        return cost
    
    def _calculate_cost(
        self, model: str, provider: str, input_tokens: int, output_tokens: int
    ) -> float:
        """Calculate cost based on model pricing."""
        # Try provider-specific pricing
        if provider in self.PRICING:
            if model in self.PRICING[provider]:
                prices = self.PRICING[provider][model]
                return (input_tokens / 1_000_000 * prices["input"] +
                        output_tokens / 1_000_000 * prices["output"])
        
        # Fallback: rough estimate
        return (input_tokens + output_tokens) * 0.00001
    
    def estimate_task_cost(
        self,
        task: str,
        model: str,
        rounds_estimate: int
    ) -> float:
        """Estimate cost for a task based on historical data."""
        # Use average cost per round from history
        if not self.entries:
            return 0.0
        
        avg_cost_per_round = sum(e.cost_usd for e in self.entries) / len(self.entries)
        return avg_cost_per_round * rounds_estimate
    
    def generate_report(self, budget_remaining: float = None) -> CostReport:
        """Generate a cost report."""
        total_cost = sum(e.cost_usd for e in self.entries)
        total_input = sum(e.input_tokens for e in self.entries)
        total_output = sum(e.output_tokens for e in self.entries)
        
        # Group by model
        by_model: Dict[str, float] = {}
        for e in self.entries:
            by_model[e.model] = by_model.get(e.model, 0) + e.cost_usd
        
        # Group by task type
        by_task_type: Dict[str, float] = {}
        for e in self.entries:
            if e.task_type:
                by_task_type[e.task_type] = by_task_type.get(e.task_type, 0) + e.cost_usd
        
        # Estimate completion cost
        estimated = 0.0
        if budget_remaining and self.entries:
            avg_cost_per_round = total_cost / len(self.entries)
            estimated = avg_cost_per_round * 50  # Assume ~50 rounds to complete
        
        return CostReport(
            total_cost=total_cost,
            total_input_tokens=total_input,
            total_output_tokens=total_output,
            by_model=by_model,
            by_task_type=by_task_type,
            estimated_completion_cost=estimated
        )
    
    def _load(self):
        """Load entries from disk."""
        if self.storage_path.exists():
            try:
                data = json.loads(self.storage_path.read_text())
                self.entries = [CostEntry(**e) for e in data.get("entries", [])]
            except Exception:
                self.entries = []
    
    def _save(self):
        """Save entries to disk."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {"entries": [vars(e) for e in self.entries]}
        self.storage_path.write_text(json.dumps(data, indent=2))
```

---

## Feature 8: Normalization Pre-processing

### Concept
Clean up code before LLM analysis to reduce noise and token waste.

### Kong's Approach
- Modulo recovery
- Negative literal reconstruction
- Dead assignment removal
- General decompiler output cleanup

### Jo's Adaptation

```python
# ouroboros/normalizer.py (NEW)

from __future__ import annotations
import re
from typing import Dict, List, Tuple

class CodeNormalizer:
    """Normalizes code before LLM processing."""
    
    def normalize_python(self, code: str) -> str:
        """Apply Python-specific normalizations."""
        normalized = code
        
        # Remove trailing whitespace
        normalized = '\n'.join(line.rstrip() for line in normalized.split('\n'))
        
        # Remove consecutive blank lines
        normalized = re.sub(r'\n{3,}', '\n\n', normalized)
        
        # Normalize string quotes (prefer double quotes)
        normalized = self._normalize_quotes(normalized)
        
        # Remove debug print statements that might have been added
        debug_patterns = [
            r'print\(["\'].*debug.*["\']\)',
            r'print\(["\'].*DEBUG.*["\']\)',
            r'#\s*DEBUG:.*',
        ]
        for pattern in debug_patterns:
            normalized = re.sub(pattern, '', normalized, flags=re.IGNORECASE)
        
        # Normalize f-string syntax where possible
        # (keep f-strings but clean up formatting)
        
        return normalized.strip()
    
    def _normalize_quotes(self, code: str) -> str:
        """Normalize string quotes to double quotes."""
        # Simple case: replace single quotes with double quotes where safe
        # This is tricky and could break code, so be conservative
        
        # Only normalize if it won't break anything
        # e.g., don't change: 'hello "world"'
        
        lines = code.split('\n')
        result = []
        
        for line in lines:
            # Skip comment lines
            if line.strip().startswith('#'):
                result.append(line)
                continue
            
            # Simple heuristic: if line has both quote types, leave alone
            if "'" in line and '"' in line:
                result.append(line)
                continue
            
            result.append(line)
        
        return '\n'.join(result)
    
    def extract_code_structure(self, code: str) -> Dict[str, List[str]]:
        """Extract structure for context (classes, functions, etc.)."""
        structure = {
            "imports": [],
            "classes": [],
            "functions": [],
            "decorators": [],
        }
        
        for line in code.split('\n'):
            stripped = line.strip()
            
            if stripped.startswith('import ') or stripped.startswith('from '):
                structure["imports"].append(stripped)
            elif stripped.startswith('class '):
                structure["classes"].append(re.sub(r':.*', '', stripped))
            elif stripped.startswith('def '):
                structure["functions"].append(re.sub(r':.*', '', stripped))
            elif stripped.startswith('@'):
                structure["decorators"].append(stripped)
        
        return structure
    
    def truncate_for_llm(
        self,
        code: str,
        max_tokens: int = 2000
    ) -> Tuple[str, str]:
        """Truncate code to fit token limit, preserving structure."""
        # Rough estimate: 4 chars per token
        char_limit = max_tokens * 4
        
        if len(code) <= char_limit:
            return code, ""
        
        structure = self.extract_code_structure(code)
        
        # Keep structure + beginning + end
        head = code[:char_limit // 2]
        tail = code[-char_limit // 2:]
        
        summary = f"\n[... {len(code) - char_limit} chars truncated ...]\n"
        
        # Add structure summary
        if structure["classes"] or structure["functions"]:
            summary += "\n## Code Structure:\n"
            for cls in structure["classes"]:
                summary += f"- {cls}\n"
            for fn in structure["functions"]:
                summary += f"- {fn}\n"
        
        return head + summary + tail, f"Original: {len(code)} chars"
```

### Integration

```python
def _maybe_normalize_for_llm(code: str, file_type: str = "python") -> str:
    """Normalize code before sending to LLM."""
    if os.environ.get("OUROBOROS_NORMALIZE_CODE", "1") != "1":
        return code
    
    from ouroboros.normalizer import CodeNormalizer
    
    normalizer = CodeNormalizer()
    
    if file_type == "python":
        return normalizer.normalize_python(code)
    
    return code
```

---

## Implementation Priority

| Feature | Priority | Effort | Impact |
|---------|----------|--------|--------|
| Feature 8: Normalization | 1 | Low | Reduces token waste |
| Feature 2: Context Enrichment | 2 | Medium | Improves LLM quality |
| Feature 3: Semantic Synthesis | 3 | Medium | Better code consistency |
| Feature 5: Eval Framework | 4 | Medium | Self-correction capability |
| Feature 6: Cost Tracking | 5 | Low | Better budget management |
| Feature 1: Pipeline Architecture | 6 | High | Foundation for others |
| Feature 4: Task Graph | 7 | High | Complex tasks only |

---

## Feature Flags Summary

```bash
# Core features
OUROBOROS_USE_PIPELINE=0           # Feature 1
OUROBOROS_ENRICH_CONTEXT=1          # Feature 2 (on by default)
OUROBOROS_SYNTHESIS=0               # Feature 3
OUROBOROS_TASK_GRAPH=0              # Feature 4
OUROBOROS_EVAL=0                    # Feature 5
OUROBOROS_COST_TRACKING=1           # Feature 6 (already on)
OUROBOROS_NORMALIZE_CODE=1          # Feature 8 (on by default)
```

---

## Files to Create

1. `ouroboros/pipeline.py` - Feature 1
2. `ouroboros/context_enricher.py` - Feature 2
3. `ouroboros/synthesis.py` - Feature 3
4. `ouroboros/task_graph.py` - Feature 4
5. `ouroboros/eval.py` - Feature 5
6. `ouroboros/cost_tracker.py` - Feature 6 (extend existing)
7. `ouroboros/normalizer.py` - Feature 8

## Files to Modify

1. `ouroboros/loop.py` - Add integration hooks
2. `ouroboros/llm.py` - Enhance cost tracking
3. `.github/workflows/run.yml` - Add env vars
