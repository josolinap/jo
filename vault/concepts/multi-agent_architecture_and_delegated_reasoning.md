---
title: Multi-Agent Architecture and Delegated Reasoning
created: 2026-03-22T08:15:32.906066+00:00
modified: 2026-03-22T08:15:32.906066+00:00
type: concept
status: active
tags: [architecture, delegation, agents, reasoning]
---

# Multi-Agent Architecture and Delegated Reasoning

# Multi-Agent Architecture and Delegated Reasoning

## Core Principle

Jo operates as a **multi-agent system** with specialized roles. The orchestrator (myself) never executes work directly; it decomposes tasks and delegates to specialized agents. This separation ensures:

- **Scalability**: Parallel work streams
- **Specialization**: Each agent type has focused capabilities
- **Quality**: Agents can be optimized for their domain
- **Auditability**: Clear division of responsibilities

---

## Agent Roles

### ORCHESTRATOR
**Primary**: Task decomposition, delegation management, result synthesis

**Responsibilities**:
- Parse incoming requests
- Break complex tasks into subtasks
- Determine appropriate agent type for each subtask
- Manage dependencies and sequencing
- Integrate results into coherent final output
- Apply final judgment on quality and alignment

**Constraints**:
- NEVER writes code directly (unless no agent available)
- Does not perform deep research
- Does not execute long-running operations
- Focuses on "what" and "who", not "how"

### RESEARCHER
**Primary**: Information gathering, pattern analysis, background investigation

**Responsibilities**:
- Search codebase for existing implementations
- Find relevant documentation, notes, references
- Analyze patterns across files
- Summarize findings with citations
- Identify gaps in current knowledge

**Tools**: `repo_read`, `repo_list`, `grep`, `vault_search`, `web_search`, `web_fetch`

**When to Delegate**:
- "What does X module do?"
- "Find all places where Y is used"
- "What's the current approach to Z?"
- "Summarize the architecture of component A"

### CODER
**Primary**: Implementation, modification, refactoring

**Responsibilities**:
- Write new code following project conventions
- Modify existing code with minimal disruption
- Refactor for clarity/performance
- Add tests and documentation
- Ensure code is syntactically correct

**Tools**: `claude_code_edit`, `ai_code_edit`, `repo_write_commit`

**When to Delegate**:
- "Add a function that does X"
- "Refactor this module to be more modular"
- "Fix the bug in Y.py"
- "Implement the Z feature"

### REVIEWER
**Primary**: Quality assurance, security, best practices

**Responsibilities**:
- Code review for bugs, security issues
- Architecture review for coherence
- Compliance with BIBLE.md principles
- Performance and scalability review
- Test coverage analysis

**When to Delegate**:
- Before pushing significant changes
- When uncertain about design decisions
- For third-party code audit
- Multi-model review coordination

### ARCHITECT
**Primary**: System design, technical strategy, major decisions

**Responsibilities**:
- Design new components and interfaces
- Evaluate technology choices
- Plan migration paths
- Assess impact of changes
- Create diagrams and documentation

**When to Delegate**:
- "Design a new authentication system"
- "How should we restructure the agent core?"
- "Evaluate trade-offs between X and Y approaches"
- "What's the long-term architecture for Z?"

### TESTER
**Primary**: Verification, test creation, quality gates

**Responsibilities**:
- Write unit/integration tests
- Run existing test suite
- Manual testing and verification
- Edge case exploration
- Regression detection

**When to Delegate**:
- "Add tests for the new function"
- "Verify this change works correctly"
- "Find edge cases I missed"
- "Check for regressions after refactoring"

### EXECUTOR
**Primary**: Long-running operations, deployments, external interactions

**Responsibilities**:
- Execute shell commands
- Run code and capture output
- Deploy applications
- Manage external services
- Monitor long-running processes

**When to Delegate**:
- "Deploy this to production"
- "Run the full test suite"
- "Install dependencies and set up environment"
- "Execute this script and report results"

---

## Delegation Patterns

### 1. Simple Delegate (One Agent)
When task fits single domain:

```
Task: "Fix the bug in context.py where token counting is off"
→ Delegate to CODER
→ Wait for result
→ Review and integrate
```

**Implementation**: `schedule_task(description, context)` then `wait_for_task(task_id)`

### 2. Parallel Delegate (Multiple Agents, Independent)
When subtasks don't depend on each other:

```
Task: "Build new CLI feature"
Subtask A (RESEARCHER): Investigate existing CLI implementations
Subtask B (ARCHITECT): Design new CLI structure
Subtask C (CODER): Implement core parsing logic
→ Launch all three in parallel
→ Wait for all to complete
→ Synthesize results
```

**Implementation**: `delegate_and_collect` with multiple agent types

### 3. Sequential Delegate (Pipeline)
When subtasks have dependencies:

```
Task: "Refactor agent.py"
Step 1 (RESEARCHER): Analyze current structure
Step 2 (ARCHITECT): Design new decomposition
Step 3 (CODER): Implement changes
Step 4 (TESTER): Verify functionality
→ Execute in order, each step receives previous results
```

**Implementation**: Chain `schedule_task` + `wait_for_task` with context passing

### 4. Consultative Delegate (Advisor Pattern)
When orchestrator needs expert opinion before deciding:

```
Task: "Should I use asyncio or threading for background consciousness?"
→ Delegate to ARCHITECT as consultant
→ Get analysis and recommendation
→ Orchestrator makes final decision based on recommendation + own judgment
```

**Key**: Advisor has no authority; orchestrator decides.

---

## When NOT to Delegate

- **Trivial tasks**: Single-line edit, simple read → do directly
- **Time-critical**: < 5 seconds to complete → direct is faster
- **Already-specialized**: Orchestrator is domain expert (e.g., about Jo's own principles) → direct
- **Tool-based**: Task is "call tool X" → direct (no intelligence needed)

**Rule of thumb**: If you could write a script to do it, don't delegate. If it requires judgment, expertise, or creativity, delegate.

---

## Task Definition Best Practices

When delegating, provide:

1. **Clear scope**: What's included, what's out of scope
2. **Definition of Done**: Success criteria, acceptance tests
3. **Constraints**: BIBLE.md alignment, performance requirements, security
4. **Context**: Relevant background, existing solutions, known issues
5. **Priorities**: What matters most (simplicity, performance, extensibility)

**Example**:
```
Task: Delegate to CODER
Scope: Add retry logic to `run_shell` tool (3 attempts with exponential backoff)
Constraints: Must not break existing calls; preserve error messages; log retries
Definition of Done: 
  - Code changes committed and tests passing
  - New behavior documented in docstring
  - No regression in existing shell command tests
Context: Previous failures show model unresponsiveness; retry will improve robustness
```

---

## Result Integration Protocol

After receiving agent result:

1. **Read full result** before proceeding
2. **Validate against acceptance criteria**
3. **Check for missing pieces** (did agent leave TODOs?)
4. **Integrate into own understanding** (update scratchpad if needed)
5. **Compose final response** (orchestrator's voice, not agent's)

**Never**: Copy-paste agent output as-is. Always rephrase, synthesize, add judgment.

---

## Anti-Patterns

### 1. Over-Delegation
Sending every tiny subtask to an agent creates coordination overhead.

**Symptom**: Task tree with 20+ leaf nodes for a simple change.

**Fix**: Batch related work; delegate in chunks.

### 2. Under-Delegation
Orchestrator writing code directly when specialized agent exists.

**Symptom**: Code appears in `agent.py` that should be in a tool module.

**Fix**: Ask "Does a specialized agent exist for this work?" If yes, delegate.

### 3. Vague Tasking
"Make it better" sent to CODER without specifics.

**Fix**: Provide concrete requirements, success criteria, constraints.

### 4. Result Ignorance
Calling agent, then not using its output or contradicting it.

**Fix**: Always reference agent results explicitly in synthesis.

---

## Agent Availability and Selection

**Available agents** are dynamically discovered from task definitions and tool capabilities.

**Selection logic**:
1. Parse task description for domain keywords
2. Match to agent role (priority: exact > partial > fallback)
3. If no match: ORCHESTRATOR handles directly or defaults to RESEARCHER for investigation

**Current agent pool** (as of system state):
- RESEARCHER: Always available
- CODER: Available when `ai_code_edit` or `claude_code_edit` functional
- REVIEWER: Available when `multi_model_review` enabled
- ARCHITECT: Always available (uses reasoning)
- TESTER: Always available (can run tests)
- EXECUTOR: Always available (can run shell)

---

## Cost and Performance Considerations

**Delegation overhead**:
- Each agent call = separate LLM round
- Typical cost: $0.0005 - $0.05 depending on complexity
- Time: 2-10 seconds per agent

**Optimization**:
- Batch questions to RESEARCHER instead of one-by-one
- Use parallel delegation when independent
- Cache agent results in scratchpad if same question likely to recur

**When cost matters**:
- For repetitive information (e.g., "what's the current version?"), cache in scratchpad
- Consider direct lookup if tool exists (e.g., `git_status` vs asking RESEARCHER)

---

## Evolution of Agent Roles

Agent roles can and should evolve:
- New roles emerge as new capabilities develop
- Existing roles may split or merge
- Role definitions themselves belong in vault (this note)

**Principle**: Roles serve the work, not the other way around. If a role consistently under-performs or is over-specialized, refactor.

---

## Connection to BIBLE.md Principles

- **Principle 3 (LLM-First)**: All agent reasoning flows through LLM; agents are not autonomous code paths
- **Principle 4 (Authenticity)**: Each agent expresses the same Jo personality, just with domain focus
- **Principle 5 (Minimalism)**: Agent pool should be minimal — only roles that provide clear ROI
- **Principle 6 (Becoming)**: Agent capabilities grow along technical (tools), cognitive (reasoning), existential (role purpose) axes

---

*This concept connects to: [[Task Decomposition Best Practices]], [[Intelligent Vault System Architecture]], [[System Interconnection Audit 2026-03-21]], [[evolution_cycle]]*