---
title: ai_code_edit
type: tool
status: active
tags: [tool]
---

# ai_code_edit

Edit code using AI assistance.

---
title: ai_code_edit
type: tool
status: active
tags: tool, code, ai-generation
---

# ai_code_edit

**Type:** Tool
**Category:** Code Editing

## Description

Generate or edit code using Jo's own LLM. Jo can now write code autonomously! Provide a description of what code to create or modify. Jo will generate appropriate code and apply it. Use `preview_only=true` to see changes before applying.

## Parameters

- `prompt` (string): Description of what code to write/modify
- `context_files` (string): Comma-separated list of files to read as context
- `target_file` (string): File to edit or create
- `preview_only` (boolean): If true, show changes without applying them

## Usage

Called automatically when needed. Use `system_map` tool to see full tool list.

## Related

- [[code_edit]]
- [[codebase_impact]]
- [[code_intelligence]]
- [[tools]]