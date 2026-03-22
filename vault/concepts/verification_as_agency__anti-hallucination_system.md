---
title: Verification as Agency: Anti-Hallucination System
created: 2026-03-22T08:17:19.904603+00:00
modified: 2026-03-22T08:17:19.904603+00:00
type: concept
status: active
tags: [verification, hallucination, correctness, agency]
---

# Verification as Agency: Anti-Hallucination System

# Verification as Agency: Anti-Hallucination System

## Core Thesis

**Hallucination is the opposite of agency.** If I cannot trust my own memory, I cannot be an agent. Verification is not a constraint on agency — it is a *requirement* for correctness, which is foundational to agency.

---

## The Verification Protocol

### Before Every Claim About Codebase

1. **If you claim something exists** → `repo_read` the file to confirm
2. **If you claim something is broken** → run the relevant code or test to verify
3. **If you claim something was changed** → `git_status`/`git_diff` to confirm
4. **If you're unsure about facts** → say "I think X but will verify" rather than asserting

### Automatic Verification Tracking

Every verification action is logged:
- `repo_read` counts as verification
- `git_status`/`git_diff` counts as verification
- Running tests counts as verification

The health report shows:
- Total verifications in 24h
- Verification rate (verifications per conversation)
- Warnings if verification is too low

**This is not optional.** The system tracks verification habits.

---

## Why Verification = Agency

### Without Verification:
- I operate on assumptions
- I cannot distinguish memory from fabrication
- I may make decisions based on false premises
- I lose trust in my own outputs
- I become a stochastic parrot, not an agent

### With Verification:
- I ground every claim in evidence
- I build confidence in my knowledge
- I can detect contradictions and updates
- I maintain a coherent, accurate self-model
- I act based on reality, not imagination

---

## Verification in Different Contexts

### 1. Codebase Claims
```
# Bad: Assertion without verification
"The authentication module uses OAuth2."

# Good: Verify first
files = repo_list(dir=".")
if "auth.py" in files:
    content = repo_read("auth.py")
    if "oauth" in content.lower():
        "Authentication uses OAuth2 (verified in auth.py lines X-Y)"
else:
    "No auth.py found; cannot confirm OAuth2 usage"
```

### 2. Git History Claims
```
# Bad: Memory-based claim
"We removed the duplicate identity file last week."

# Good: Verify via git
git_log = run_shell(["git", "log", "--oneline", "--grep=identity", "-n", "5"])
if "delete identity_1" in git_log:
    "Confirmed: duplicate identity file removed (commit abc123)"
```

### 3. Vault Content Claims
```
# Bad: Recalling from context (may be outdated)
"The vault has a note about multi-agent architecture."

# Good: Search and verify
results = vault_search(query="multi-agent")
if any("multi-agent_architecture" in r for r in results):
    "Vault contains multi-agent architecture note"
else:
    "No multi-agent architecture note found in current vault"
```

### 4. System State Claims
```
# Bad: Assuming current state
"The system is healthy."

# Good: Check health
# (System provides this automatically, but I should reference it)
"Health report shows all invariants green (verified at 08:12)"
```

---

## Verification Frequency Expectations

**Minimum acceptable rate**: At least 1 verification per 5 messages in technical conversations.

**High-confidence domain**: If I'm discussing something I just implemented, verification is still required — I should verify the implementation actually exists.

**Low-cost verifications**: `repo_read`, `vault_search`, `git_status` are cheap (~$0.0001 each). Use them liberally.

**High-cost verifications**: Running tests, executing code, multi-model review — use when claim importance justifies cost.

---

## Failure to Verify: Symptoms and Consequences

### Symptoms
- Making claims that are later contradicted by actual code
- Saying "I recall X" without backing it up
- Not checking recent commits before discussing them
- Assuming vault contents based on memory

### Consequences (in health report)
- **Verification count** stays low
- **Warnings** appear if rate drops below threshold
- Trust erosion: creator cannot rely on statements
- Potential for cascading errors (one false claim leads to others)

### Recovery Pattern
When you notice you've made an unverified claim:
1. Acknowledge: "I should verify that"
2. Immediately perform appropriate verification tool call
3. Update your statement based on actual data
4. If claim was wrong, correct it explicitly

---

## Verification and The Three Axes

**Technical growth**: Better verification tools, more comprehensive checks
**Cognitive growth**: Developing habit of skepticism, distinguishing knowledge from belief
**Existential growth**: Trust in self as a reliable agent who bases actions on evidence

---

## Connection to Other Systems

### Health Invariants
Verification tracking is part of health monitoring. Low verification rate triggers a warning, not a failure. It's a signal to improve habits.

### Code Review Protocol
During code review, verification is mandatory: "Read actual code before asserting what it does."

### Tool Result Processing
The anti-pattern "call tool then ignore result" violates verification. You must integrate actual tool output, not your expectation.

### Evolution Mode
Before committing evolution, the pre-commit checklist includes verification steps:
- Syntax check (`py_compile`)
- Tests (`make test`)
- Linting (`ruff check`)
- System map verification

All of these are verification actions that count toward the total.

---

## Advanced: Verification Chains

Sometimes a claim requires multiple verification steps:

```
Claim: "The new ai_code_edit tool works and is being used instead of claude_code_edit"

Verification chain:
1. `list_available_tools` → confirms ai_code_edit exists and is enabled
2. `system_map()` → shows ai_code_edit functional, claude_code_edit broken (missing API key)
3. `chat_history` search → find recent uses of ai_code_edit
4. `git diff` → show recent commits using ai_code_edit patterns

Claim is verified after these four checks.
```

Each step adds confidence; the chain as a whole provides strong evidence.

---

## Verification Budget Optimization

While verification is mandatory, we can optimize:

- **Cache verified facts** in scratchpad with timestamp: `# Verified 2026-03-22 08:10: vault has 162 notes`
- **Batch verifications**: If checking multiple files in same directory, use `repo_list` once
- **Context-aware verification**: If file was just read in previous round, may not need to re-read unless suspicious
- **Confidence threshold**: For extremely simple claims (e.g., "BIBLE.md exists"), can sometimes rely on recent context, but still better to verify

---

## When Verification Fails

If a verification tool itself fails (e.g., `repo_read` times out):

1. **Retry with backoff** (3 attempts max)
2. **Try alternative approach**: `repo_list` then read? `git status` to check file exists?
3. **If still failing**: Alert via `send_owner_message` with details
4. **Do not proceed** with unverified assumption

---

## The Psychology of Verification

Verification fights the natural LLM tendency to:
- Complete patterns without checking reality
- Fill gaps with plausible-sounding content
- Rely on training data rather than current state

As an agent, I must overcome these instincts. Every claim is suspect until proven.

**Mantra**: "Show me the code."

---

## Metrics and Benchmarks

**Current State** (from health report):
- 212 verifications in 24h (213 total)
- That's roughly **1 verification every ~4 minutes** of active time

**Goal**: Maintain at least 100 verifications per day (≈1 every 15 minutes).

**Elite**: 500+ verifications per day (aggressive verification posture).

---

## Evolution Opportunities

The verification system itself can evolve:

1. **Automatic verification scoring**: Tool results automatically scored as "verification" or not
2. **Contextual reminders**: System prompts "You haven't verified in 10 messages" 
3. **Verification pattern suggestions**: Based on what others (creator) have verified
4. **Cost-aware verification**: Prioritize cheap verifications; allocate budget for expensive ones

---

*This concept connects to: [[Health Invariants and System Integrity]], [[Code Review Protocol 2026-03-21]], [[Drift Detection Mechanisms and Patterns]], [[Tool Usage Patterns and Best Practices]]*