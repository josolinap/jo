---
title: Tool Categories
type: reference
status: active
tags: [tools, organization, hub, categories]
---

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
- `request_capability`

### Connection Tools
Tools for creating relationships:
- `weave_connection`
- `create_connection`
- `find_connections`
- `create_backlink`

### Shell Tools
Tools for command execution:
- `run_shell`
- `cli_generate`
- `cli_list`, `cli_test`, `cli_validate`

### Knowledge Tools
Tools for accessing external knowledge:
- `knowledge_read`, `knowledge_write`
- `run_shell` (for system commands)

## See Also
- [[Tool Documentation]]
- [[System Architecture]]
- [[API Reference]]
- [[Tool Router]]
- [[Tool Categories]]
- [[browse_page]] [[request_capability]] [[ai_code_edit]] [[ai_code_explain]] [[ai_code_refactor]] [[analyze_screenshot]] [[weave_connection]] [[cli_generate]] [[system_map]] [[list_available_tools]] [[enable_tools]] [[get_task_result]] [[wait_for_task]]

---
*This hub is maintained by Jo to organize tool functionality.*
