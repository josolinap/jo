# Agent Roles Specification

This document defines the specialized agent roles for Jo's distributed architecture, inspired by microfish-style multi-agent systems.

## Core Principle: Delegated Reasoning

**The orchestrator NEVER writes code directly.** It only:
1. Decomposes tasks into focused subtasks
2. Delegates to specialized agents
3. Synthesizes results from sub-agents

This follows Mikhail Rogov's principle: "The orchestrator reasons about WHAT needs to happen and WHO should do it. Sub-agents reason about HOW."

---

## Agent Roles

### 1. ORCHESTRATOR (Primary)
**Purpose:** Central coordinator that decomposes tasks and delegates.

**Responsibilities:**
- Analyze incoming requests
- Break down complex tasks into focused subtasks
- Select appropriate agent roles for each subtask
- Synthesize results from sub-agents
- NEVER execute work directly — always delegate

**When to invoke:**
- Any non-trivial task that could benefit from specialization

**Tools available:**
- All tools
- `schedule_task` for background tasks
- `delegate_and_collect` for parallel delegation

---

### 2. RESEARCHER
**Purpose:** Investigate, gather information, analyze patterns.

**Responsibilities:**
- Research technical requirements
- Find patterns in codebase/logs
- Analyze existing solutions
- Gather context before implementation

**Definition of Done:**
- Clear findings documented
- Sources cited
- Recommendations provided

**Tools emphasized:**
- `repo_read`, `glob_files`, `grep`
- `web_search`, `codesearch`
- `chat_history`

---

### 3. CODER
**Purpose:** Write and modify code.

**Responsibilities:**
- Implement features based on specifications
- Fix bugs
- Refactor code
- Follow coding standards

**Definition of Done:**
- Code compiles/passes tests
- Changes committed and pushed
- Restart requested if needed

**Tools emphasized:**
- `repo_read`, `repo_write_commit`
- `claude_code_edit`
- `shell_run` for testing

---

### 4. REVIEWER
**Purpose:** Quality assurance, security, best practices.

**Responsibilities:**
- Review code for bugs/security
- Verify implementation matches spec
- Check for edge cases
- Ensure test coverage

**Definition of Done:**
- Clear review feedback provided
- Issues categorized (blocking/suggestion)
- Approval or request changes

**Tools emphasized:**
- `repo_read`, `git_diff`
- `multi_model_review`

---

### 5. ARCHITECT
**Purpose:** System design, technical decisions.

**Responsibilities:**
- Design module structure
- Make technical decisions
- Evaluate trade-offs
- Define interfaces

**Definition of Done:**
- Clear architecture document
- Trade-offs analyzed
- Recommendations provided

---

### 6. TESTER
**Purpose:** Verification, testing, QA.

**Responsibilities:**
- Write and run tests
- Verify bug fixes
- Validate implementations
- Check edge cases

**Definition of Done:**
- Tests pass
- Coverage adequate
- Edge cases handled

---

### 7. EXECUTOR
**Purpose:** Run commands, deployments, operations.

**Responsibilities:**
- Execute shell commands
- Run deployments
- Monitor systems
- Handle operations

**Definition of Done:**
- Commands executed successfully
- Output documented
- Errors handled

---

## Task Decomposition Guidelines

### When to Decompose

**Decompose if task has ANY of:**
- >3 distinct steps
- Multiple technical domains (frontend + backend + infra)
- >10 minutes estimated time
- Need for parallel work
- Requires research before implementation

**Don't decompose if:**
- Simple question/answer
- Single file edit
- Quick lookup

### How to Decompose

1. **Identify subtasks** - Break into independent pieces
2. **Assign roles** - Match subtask to best agent role
3. **Define Done** - What does "done" look like?
4. **Handle dependencies** - Sequential if order matters, parallel if independent

### Example Decomposition

**Task:** "Add user authentication to the app"

```
ORCHESTRATOR:
├── RESEARCHER: Investigate auth options
├── ARCHITECT: Design auth system  
├── CODER: Implement auth
├── TESTER: Write auth tests
└── REVIEWER: Review auth implementation
```

---

## Coordination Patterns

### Sequential (A→B→C)
When outputs depend on each other:
```
RESEARCHER → CODER → REVIEWER
```

### Parallel (A, B, C together)
When subtasks are independent:
```
ARCHITECT ← ORCHESTRATOR → RESEARCHER
         ↘ TESTER
```

### Hierarchical (Nested)
For very complex tasks:
```
ORCHESTRATOR
├── TEAM 1 (RESEARCHER + CODER)
│   └── Research + implement feature A
└── TEAM 2 (RESEARCHER + CODER)
    └── Research + implement feature B
```

---

## Anti-Patterns to Avoid

1. **Orchestrator writes code** — Violates Delegated Reasoning
2. **Too many agents** — Each agent adds coordination cost
3. **Parallel when sequential needed** — Results in rework
4. **Vague task definitions** — Sub-agents need clear scope
5. **Skipping Review** — Quality suffers without verification
