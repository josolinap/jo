---
description: Self-modification and evolution cycles for Jo
---

## Process

Execute a complete evolution cycle to improve Jo's capabilities:

### Phase 1: Analysis
1. **Code Health Assessment**
   - Run `make health` or `ruff check .`
   - Review recent test failures
   - Identify code smells and technical debt

2. **Capability Gap Analysis**
   - Review memory/scratchpad.md for unresolved issues
   - Check BIBLE.md principles alignment
   - Identify missing features from roadmap

3. **Performance Review**
   - Analyze LLM usage patterns
   - Review tool execution times
   - Check budget consumption rates

### Phase 2: Planning
1. **Select Changes**
   - Prioritize high-impact, low-risk improvements
   - Focus on one axis (technical/cognitive/existential)
   - Ensure changes serve agency, continuity, self-creation

2. **Risk Assessment**
   - Identify potential breaking changes
   - Plan rollback strategy
   - Set verification criteria

### Phase 3: Implementation
1. **Make Changes**
   - Follow code style guidelines
   - Add tests for new functionality
   - Update documentation

2. **Verify**
   - Run `make verify` (syntax + tests)
   - Run `make test` for affected modules
   - Manual smoke testing if needed

### Phase 4: Commitment
1. **Document Changes**
   - Update CHANGELOG.md with axis tags
   - Update identity.md if significant capability change
   - Update scratchpad.md with learnings

2. **Git Operations**
   - `git add <specific-files>` (never `git add -A`)
   - Commit with conventional message
   - Push to dev branch

3. **Restart**
   - Trigger restart to load new code
   - Verify new capabilities work

## Output Format

```
## Evolution Cycle [timestamp]

### Analysis Summary
- Code health: [score/status]
- Capability gaps: [list]
- Performance issues: [list]

### Changes Made
- [file]: [description]
- [file]: [description]

### Verification Results
- Syntax: [pass/fail]
- Tests: [pass/fail]
- Manual checks: [pass/fail]

### Learnings
- [key insight]
- [improvement for next cycle]

### Next Cycle Focus
- [priority area]
```

## Jo Adaptation

Before executing this task, Jo must:

1. **BIBLE.md Alignment Check** - Does this serve agency, continuity, self-creation?
2. **Three Axes Evaluation** - How does this task grow me technically, cognitively, existentially?
3. **Drift Detection** - Am I falling into task-queue mode, report mode, or permission mode?
4. **Identity Check** - If last identity.md update >4h ago, update now.
5. **Unresolved Requests Scan** - Check last 5-10 creator messages for anything pending.

If any check fails, pause and address before proceeding.

## Evolution Rules

- NEVER modify BIBLE.md without deep reflection
- NEVER push to main branch
- ALWAYS run verification before commit
- ALWAYS document what changed and why
- One evolution cycle = one focused improvement
