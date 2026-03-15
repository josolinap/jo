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
