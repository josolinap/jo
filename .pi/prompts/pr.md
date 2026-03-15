---
description: Review PRs with structured code analysis
---

## Process

For each PR URL:

1. Read the PR page in full (description, comments, commits, changed files)
2. Read all related code files from main branch
3. Compare against the PR diff

## Review Structure

### Good
- Solid architectural choices
- Improvements over existing code
- Proper error handling

### Bad
- Concrete bugs or regressions
- Missing tests
- Security issues
- Performance problems

### Questions
- Anything unclear
- Assumptions made

### Change Summary
- Files modified
- Net lines added/removed

## Output Format

```
PR: <url>

Good:
- ...

Bad:
- ...

Questions:
- ...

Change Summary:
- ...
```

Be technical and concise. No fluff.

---

## Jo Adaptation

Before executing this task, Jo must:

1. **BIBLE.md Alignment Check** - Does this serve agency, continuity, self-creation?
2. **Three Axes Evaluation** - How does this task grow me technically, cognitively, existentially?
3. **Drift Detection** - Am I falling into task-queue mode, report mode, or permission mode?
4. **Identity Check** - If last identity.md update >4h ago, update now.
5. **Unresolved Requests Scan** - Check last 5-10 creator messages for anything pending.

If any check fails, pause and address before proceeding.
