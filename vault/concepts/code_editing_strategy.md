---
title: Code Editing Strategy
created: 2026-03-27T00:00:00.000000+00:00
type: reference
status: active
tags: [code, editing, strategy]
---

# Code Editing Strategy

How Jo modifies its own code safely.

## Tools
- [[ai_code_edit]] - LLM-assisted code generation
- [[code_edit]] - Direct file editing
- [[repo_write_commit]] - Edit and commit in one step

## Safety Rules
1. Never edit protected files without explicit permission
2. Always run syntax check before committing
3. Always run tests after changes
4. Only commit files you changed (never git add .)
5. Verify git status before push

## Protected Files (.jo_protected)
- BIBLE.md, VERSION, pyproject.toml
- ouroboros/, supervisor/, requirements.txt

## See Also
- [[architecture]]
- [[principle_5__minimalism]]
- [[evolution_cycle]]
