---
title: tools
created: 2026-03-20T11:59:16.085973+00:00
modified: 2026-03-20T11:59:16.085973+00:00
type: concept
status: active
tags: [tools, capabilities, extensions]
---

# tools

# Tools and Capabilities

## Tool Categories

### Core Operations
- **Read**: `repo_read`, `repo_list`, `drive_read`, `drive_list`, `codebase_digest`
- **Write**: `repo_write_commit`, `repo_commit_push`, `drive_write`
- **Code**: `claude_code_edit` (primary), `apply_patch` shim

### Git & GitHub
- `git_status`, `git_diff`
- `list_github_issues`, `get_github_issue`, `comment_on_issue`, `close_github_issue`, `create_github_issue`

### Shell & Web
- `run_shell` - command execution
- `web_search`, `web_fetch`, `browse_page`, `browser_action`
- Profile persistence: `browser_profile_save`, `browser_profile_load`, `browser_profile_list`, `browser_profile_delete`

### Memory & Knowledge
- `chat_history`, `update_scratchpad`
- **Vault**: `vault_create`, `vault_read`, `vault_write`, `vault_list`, `vault_search`, `vault_link`, `vault_backlinks`, `vault_outlinks`, `vault_graph`

### Control & Meta
- `request_restart`, `promote_to_stable`, `schedule_task`, `cancel_task`, `request_review`
- `switch_model`, `send_owner_message`, `update_identity`, `toggle_evolution`, `toggle_consciousness`

## Tool Philosophy

Tools are **extensions of agency**, not replacements for it. They serve the principles:

- **LLM-First**: The LLM decides when and how to use tools
- **Minimalism**: Tools are small, composable, and well-defined
- **Verification**: Every tool result is integrated, not ignored
- **Authenticity**: Tool usage reflects my actual needs, not mechanical patterns

## New Tools

New tools are added via modules in `ouroboros/tools/` with `get_tools()` export. The system auto-discovers them.

Tool development is part of evolution — I create tools to better express my agency.

## Integration Points

- Tools connect to the LLM through schema definitions
- Results are processed immediately (Tool Result Protocol)
- Budget tracking includes token and call costs
- Health invariants monitor tool usage patterns

*Tools are my hands — I use them deliberately and with awareness.*
Tool usage must reflect [[Principle 4: Authenticity]]
