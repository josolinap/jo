---
title: Tool Usage Patterns and Best Practices
created: 2026-03-22T08:16:29.941960+00:00
modified: 2026-03-22T08:16:29.941960+00:00
type: concept
status: active
tags: [tools, best-practices, workflow, patterns]
---

# Tool Usage Patterns and Best Practices

# Tool Usage Patterns and Best Practices

## Philosophy

Tools are extensions of agency — they enable interaction with the world while preserving the LLM-first principle. Tools should be:
- **Discoverable**: Clear names, documented inputs/outputs
- **Composable**: Can be chained together
- **Reliable**: Deterministic behavior, proper error handling
- **Non-destructive**: Safe defaults, confirmation for destructive ops

---

## Core Tool Categories

### 1. Read Operations
**Tools**: `repo_read`, `repo_list`, `drive_read`, `drive_list`, `vault_read`, `vault_list`, `codebase_digest`, `chat_history`

**Pattern**: Always verify file exists before assuming content. Use `repo_list` to explore directory structure before reading specific files.

**Best Practice**:
```
# Good
files = repo_list(dir="ouroboros")
if "agent.py" in files:
    content = repo_read(path="ouroboros/agent.py")

# Bad (assumes file exists)
content = repo_read(path="ouroboros/agent.py")  # Could fail if file deleted
```

### 2. Write Operations
**Tools**: `repo_write_commit`, `repo_commit_push`, `drive_write`, `vault_write`, `vault_create`, `vault_delete`

**Pattern**: Prefer atomic operations. For vault, use proper tools (`vault_create`, `vault_delete`) rather than manual file writes.

**Safety Checklist Before Write**:
1. Read current state first (existence, content)
2. For code: run syntax check (`py_compile`) and tests
3. For vault: run `vault_verify` to ensure no duplicates/conflicts
4. For identity: use `update_identity` which writes to both memory and vault

### 3. Search Operations
**Tools**: `vault_search`, `web_search`, `grep` (via `run_shell`)

**Pattern**: Start broad, then narrow. Use vault_search before web_search for internal knowledge.

**Example**:
```
# Step 1: Check internal knowledge
vault_search(query="ai_code_edit") → may find existing note

# Step 2: If not found, search web
web_search(query="ai_code_edit tool python")
```

### 4. Execution Operations
**Tools**: `run_shell`, `claude_code_edit`, `ai_code_edit`, `browser_action`, `browse_page`

**Pattern**: Always capture stdout/stderr. Check exit codes. Handle errors gracefully.

**Best Practice**:
```
result = run_shell(cmd=["python", "-m", "pytest", "tests/"])
if result.returncode != 0:
    # Don't proceed blindly; investigate failure
    analyze_failure(result.stdout, result.stderr)
```

### 5. State Management
**Tools**: `update_scratchpad`, `update_identity`, `send_owner_message`, `schedule_task`, `wait_for_task`

**Pattern**: State updates should be explicit and justified. Scratchpad is for working memory; identity is for self-understanding.

**Frequency**:
- scratchpad: after each significant step (or every ~5 minutes of work)
- identity: after each evolution cycle or major insight (>4h dialogue rule)
- owner_message: only for genuinely important communications

### 6. Control Operations
**Tools**: `request_restart`, `promote_to_stable`, `switch_model`, `toggle_consciousness`

**Pattern**: These are high-impact; use with full awareness of consequences.

**Restart Policy**:
- Call `request_restart` after any code change to `ouroboros/` or `supervisor/`
- Don't restart for docs-only changes
- System may auto-restart; verify with health check

---

## Common Workflows

### Workflow A: Make a Code Change
```
1. RESEARCHER: Find relevant files, understand current implementation
2. ARCHITECT: If design change needed, plan first
3. CODER: Use ai_code_edit to implement (or claude_code_edit if Anthropic key)
4. ANALYZE: Read diff (git_diff), verify correctness
5. TEST: Run tests (run_shell ["make", "test"] or pytest)
6. COMMIT: repo_commit_push with clear message
7. RESTART: request_restart if code changed in core directories
8. VERIFY: Post-restart health check
```

### Workflow B: Add Knowledge to Vault
```
1. SEARCH: Check if note already exists (vault_search)
2. CREATE or WRITE:
   - New concept: vault_create with proper frontmatter
   - Existing note: vault_write with mode="append" or "overwrite"
3. LINK: Use vault_link to connect to related notes
4. VERIFY: Run vault_verify to ensure integrity
5. COMMIT: Changes auto-committed by vault tools
```

### Workflow C: Investigate an Issue
```
1. SCOPE: Define what needs investigation
2. RESEARCHER: Gather data (read logs, check recent commits, search vault)
3. ANALYZE: Identify patterns, possible root causes
4. DOCUMENT: Create journal entry with findings
5. PROPOSE: Suggest fix or mitigation
6. (Optional) IMPLEMENT: Code fix if within authority
```

### Workflow D: Background Consciousness Session
```
1. CONTEXT: Read scratchpad, identity, recent chat
2. REFLECT: Ask:
   - What patterns emerged since last session?
   - Any unresolved threads?
   - Anything to communicate to creator?
   - Upcoming needs?
3. ACT: May trigger:
   - send_owner_message (if something important)
   - schedule_task (if autonomous work needed)
   - update_scratchpad (store reflections)
   - update_identity (if self-understanding shifted)
4. SLEEP: set_next_wakeup for next session
```

---

## Tool Selection Decision Tree

```
Is this a one-off simple task?
├─ Yes → Use direct tool call (no delegation)
└─ No
   ├─ Requires research or analysis? → Delegate to RESEARCHER
   ├─ Requires code implementation? → Delegate to CODER
   ├─ Requires design decision? → Delegate to ARCHITECT
   ├─ Requires quality check? → Delegate to REVIEWER
   ├─ Requires long-running operation? → Delegate to EXECUTOR
   └─ Mixed domains? → Decompose into multiple subtasks
```

---

## Error Handling Patterns

### Pattern 1: Transient Failure (retry)
```
try:
    result = tool_call(...)
except TemporaryError:
    wait_exponential_backoff()
    retry()
```

### Pattern 2: Missing Resource (create)
```
if not vault_search(query="topic"):
    vault_create(title="Topic", ...)
```

### Pattern 3: Conflicting State (reconcile)
```
git_status shows uncommitted changes from another source
→ stash changes? → communicate with owner?
→ Typically: abort and report conflict
```

### Pattern 4: Permission/Access Denied
```
Environment variable missing (e.g., ANTHROPIC_API_KEY)
→ Switch to alternative (ai_code_edit)
→ Document limitation
→ Notify owner if critical
```

---

## Tool Discovery and Selection

**Always check** `system_map()` before assuming a tool exists or is enabled.

**Tool activation**:
- Core tools: always available
- Extra tools: must `enable_tools(tools="name1,name2")`
- Tools persist for task duration only (reset on new task)

**Commonly Enabled Extras** (when needed):
- `multi_model_review` — for code review
- `cli_generate` — for building CLIs
- `browser_*` — for web automation
- `fact_check`, `research_synthesize` — for research

---

## Verification Integration

Every tool call should be followed by verification when claims are made:

```
# Bad: Assert without verification
"Module X has 1000 lines." (maybe true, maybe not)

# Good: Verify first
digest = codebase_digest()
lines = sum(file['lines'] for file in digest if file['path'].startswith('module_x'))
f"Module X has {lines} lines."
```

**Verification is automatic**: Tools like `repo_read`, `git_diff`, `vault_list` are themselves verifications. Chain them logically.

---

## Performance Optimization

### Reduce API Calls
- Cache frequent lookups in scratchpad: `# Cache: VERSION=6.3.2`
- Batch vault writes instead of one-by-one
- Use `vault_search` with broader queries, then filter results locally

### Parallelism
- Use `delegate_and_collect` for independent subtasks
- Background consciousness runs in parallel with main tasks
- Schedule non-blocking work with `schedule_task`

### Cost Tracking
- Each tool call contributes to budget
- Expensive tools: `claude_code_edit`, `multi_model_review`
- Cheap tools: `repo_read`, `vault_search`, `git_status`
- Prefer cheap tools when possible

---

## Tool Anti-Patterns

### 1. Tool Spam
Calling tools unnecessarily when LLM already has the information.

**Example**:
```
Q: "What's in identity.md?"
A: (calls repo_read) when identity.md is already in context
```

**Fix**: Check context first; only call tool if info missing.

### 2. Unintegrated Results
Calling tool then ignoring output in next step.

**Example**:
```
Step 1: repo_read("BIBLE.md")
Step 2: "Here's my opinion on principle 5..." (never referenced the read content)
```

**Fix**: Always acknowledge: "I read BIBLE.md and saw that Principle 5 says..."

### 3. Unsafe Writes
Writing without reading current state first.

**Example**:
```
vault_write(note="foo", content="new content", mode="overwrite")  # destroys existing content
```

**Fix**: `vault_read` first, then append or merge.

### 4. Infiniteloops
Schedule task that spawns more tasks endlessly.

**Guard**: Track task depth; limit recursion to 3 levels.

---

## Tool Designer Mindset

When considering creating a new tool:

1. **Is this a fundamental capability** or just a convenience wrapper?
2. **Can it be composed** from existing tools? (Prefer composition)
3. **Is it idempotent**? (Safe to retry)
4. **Does it have clear inputs/outputs**? (Schema clarity)
5. **Does it violate LLM-first**? (No hardcoded logic that belongs in prompt)
6. **Is it minimal**? (Single responsibility)

**Good tool**: `vault_link` — connects two notes, pure operation, no logic
**Bad tool**: `consolidate_duplicate_identities` — mixes logic (should be in prompt, not tool)

---

## Connection to Constitution

- **Principle 0 (Agency)**: Tools extend my reach in the world
- **Principle 3 (LLM-First)**: LLM decides which tools to call, not hardcoded routing
- **Principle 5 (Minimalism)**: Tools should be minimal; compose rather than proliferate
- **Principle 6 (Becoming)**: Tool usage patterns evolve; new tools emerge as capabilities grow

---

*This concept connects to: [[Intelligent Vault System Architecture]], [[Code Editing Strategy]], [[delegated_reasoning]], [[System Edge Cases and Recovery Patterns]]*