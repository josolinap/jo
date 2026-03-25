---
title: repo_read
created: 2026-03-25T08:07:08.040218+00:00
modified: 2026-03-25T08:07:08.040218+00:00
type: tool
status: active
---

# repo_read

# repo_read

**Type:** Read tool  
**Category:** Code Intelligence  

Reads a UTF-8 text file from the GitHub repo. Used for code analysis, verification, and understanding the codebase structure.

## Parameters
- `path` (string, required): File path relative to repo root

## Related Tools
- [[drive_read]] - reads from local storage
- [[repo_list]] - lists directory contents
- [[codebase_digest]] - comprehensive codebase analysis

## Use Cases
- Verifying claims about code existence
- Reading implementation details before modification
- Understanding dependencies and architecture

## Connects To
- [[Code Intelligence]]
- [[Verification as Agency: Anti-Hallucination System]]
- [[Codebase Overview]]