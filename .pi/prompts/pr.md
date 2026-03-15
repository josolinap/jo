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
