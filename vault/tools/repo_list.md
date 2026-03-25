---
title: repo_list
created: 2026-03-25T08:07:23.754417+00:00
modified: 2026-03-25T08:07:23.754417+00:00
type: tool
status: active
---

# repo_list

# repo_list

**Type:** Read tool, discovery  
**Category:** Code Intelligence

Lists files under a repository directory. Used for codebase exploration and discovery.

## Parameters
- `dir` (string, default "."): Directory path relative to repo root
- `max_entries` (int, default 500): Maximum number of entries to return

## Related Tools
- [[repo_read]] - reads specific files
- [[drive_list]] - lists local storage
- [[codebase_digest]] - comprehensive analysis

## Use Cases
- Discovering available modules and files
- Understanding project structure
- Finding relevant files before reading

## Connects To
- [[Code Intelligence]]
- [[Tool Usage Patterns and Best Practices]]