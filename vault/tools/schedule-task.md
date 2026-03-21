# schedule_task

**Type:** Tool
**Category:** See system_map

## Description

Schedule a BACKGROUND TASK. Returns task_id for later retrieval. Use for: complex multi-step tasks, code changes, research that takes time. DO NOT use for: tools that return immediate results (like simulate_outcome, repo_read, glob_files, db_query, etc). Call those tools DIRECTLY - they run synchronously.

## Parameters

- `description` (string): Task description — be specific about scope and expected deliverable
- `context` (string): Optional context from parent task: background info, constraints, style guide, etc.
- `parent_task_id` (string): Optional parent task ID for tracking lineage

## Usage

Called automatically when needed. Use `system_map` tool to see full tool list.

## Related

_Add related tools and concepts here_
