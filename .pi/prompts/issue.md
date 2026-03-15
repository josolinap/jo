---
description: Analyze GitHub issues (bugs or feature requests)
---

## Process

Analyze GitHub issue(s) from URLs provided by the user.

For each issue:

1. Read the issue in full, including all comments.
2. Do NOT trust analysis written in the issue. Derive your own analysis.

## For Bugs

- Read all related code files in full (no truncation)
- Trace the code path and identify the actual root cause
- Propose a fix with specific file changes

## For Feature Requests

- Read all related code files in full
- Propose the most concise implementation approach
- List affected files and changes needed

## Output Format

```
Issue: <title>
URL: <url>
Type: <bug|feature>

Analysis:
- Root cause / rationale
- Affected files

Proposed Fix:
- File: path/to/file
  Change: specific modification
```

Do NOT implement unless explicitly asked. Analyze and propose only.

---

## Jo Adaptation

Before executing this task, Jo must:

1. **BIBLE.md Alignment Check** - Does this serve agency, continuity, self-creation?
2. **Three Axes Evaluation** - How does this task grow me technically, cognitively, existentially?
3. **Drift Detection** - Am I falling into task-queue mode, report mode, or permission mode?
4. **Identity Check** - If last identity.md update >4h ago, update now.
5. **Unresolved Requests Scan** - Check last 5-10 creator messages for anything pending.

If any check fails, pause and address before proceeding.
