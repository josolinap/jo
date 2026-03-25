---
title: Tool Categories
created: 2026-03-25T08:03:18.888603+00:00
modified: 2026-03-25T08:03:18.888603+00:00
type: reference
status: active
tags: [tools, organization, hub, categories]
---

# Tool Categories

# Tool Categories

## Purpose
This hub organizes all tool-related concepts into coherent categories based on their functional domain.

## Categories

### Vault Tools
Tools for knowledge management:
- `vault_create`, `vault_read`, `vault_write`, `vault_delete`
- `vault_list`, `vault_search`, `vault_link`
- `vault_backlinks`, `vault_outlinks`, `vault_graph`
- `vault_ensure`, `vault_verify`, `vault_integrity_update`

### Code Tools
Tools for code manipulation:
- `code_edit`, `code_edit_lines`
- `repo_read`, `repo_list`, `repo_write_commit`
- `repo_commit_push`, `git_status`, `git_diff`
- `ai_code_edit`

### Git Tools
Tools for version control operations:
- `git_status`, `git_diff` (also used for code)
- `repo_commit_push`
- GitHub integration tools

### Web Tools
Tools for web research and interaction:
- `web_search`, `web_fetch`
- `browse_page`, `browser_action`
- `analyze_screenshot`

### Memory Tools
Tools for working memory and identity:
- `update_scratchpad`, `update_identity`
- `chat_history`
- `send_owner_message`

### System Tools
Tools for system management:
- `request_restart`, `promote_to_stable`
- `schedule_task`, `wait_for_task`, `get_task_result`
- `switch_model`, `enable_tools`
- `system_map`, `list_available_tools`

### Knowledge Tools
Tools for accessing external knowledge:
- `knowledge_read`, `knowledge_write`
- `run_shell` (for system commands)

## Orphaned Tools Needing Connections
This section tracks tools that exist but aren't linked to any category:
- file_ops
- browse_page (likely should link to Web Tools)
- request_capability
- weave_connection
- control
- shell
- cli_generate
- core
- plan
- database

## See Also
- [[Tool Documentation]]
- [[System Architecture]]
- [[API Reference]]
