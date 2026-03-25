---
title: tools
created: 2026-03-20T11:59:16.085973+00:00
modified: 2026-03-25T08:00:00.000000+00:00
type: concept
status: active
tags: [tools, capabilities, extensions]
---

# tools

# Tools and Capabilities (138 tools)

## Tool Categories

### Code Operations (16)
- [[repo_read]] — Read files from repo
- [[repo_write_commit]] — Write + commit + push
- [[repo_commit_push]] — Commit + push changed files
- [[repo_list]] — List repo directory contents
- [[repo_tree]] — Display directory tree
- [[code_edit]] — Edit file directly (native)
- [[code_edit_lines]] — Edit specific lines (no LLM)
- [[ai_code_edit]] — Generate/edit code via LLM
- [[ai_code_explain]] — AI explanation of code
- [[ai_code_refactor]] — AI-assisted refactoring
- [[find_callers]] — Find function callers (impact awareness)
- [[find_definitions]] — Find where function/class is defined
- [[copy_file]], [[move_file]], [[delete_file]] — File operations
- [[file_stats]] — File/directory statistics

### Code Intelligence (6) — GitNexus-inspired
- [[codebase_impact]] — Depth-grouped blast radius (WILL BREAK / LIKELY AFFECTED / MAY NEED TESTING)
- [[symbol_context]] — 360-degree view: callers, callees, cluster membership, confidence
- [[neural_map]] — Build knowledge graph of concepts and connections
- [[find_connections]] — Find path between concepts
- [[explore_concept]] — Explore concept and its connections
- [[query_knowledge]] — Search across codebase, vault, memory

### Memory & Knowledge (20)
- [[update_scratchpad]] — Working memory
- [[update_identity]] — Identity manifest
- [[chat_history]] — Retrieve messages
- [[vault_create]], [[vault_read]], [[vault_write]], [[vault_list]], [[vault_search]] — Vault CRUD
- [[vault_link]], [[vault_backlinks]], [[vault_outlinks]], [[vault_graph]] — Vault navigation
- [[vault_delete]], [[vault_ensure]], [[vault_verify]], [[vault_integrity_update]] — Vault management
- [[vault_check_conventions]] — Organization check
- [[knowledge_read]], [[knowledge_write]], [[knowledge_list]] — Persistent knowledge base

### Web & Browser (11)
- [[web_search]] — Search the web
- [[web_fetch]] — Fetch URL content
- [[browse_page]] — Open URL in headless browser
- [[browser_action]] — Click, fill, select, evaluate, scroll, wait, go_back
- [[analyze_screenshot]] — Vision LLM analysis of screenshots
- [[browser_profile_save]], [[browser_profile_load]], [[browser_profile_list]], [[browser_profile_delete]] — Session persistence

### Git & GitHub (8)
- [[git_status]], [[git_diff]], [[git_graph]] — Git operations
- [[list_github_issues]], [[get_github_issue]], [[create_github_issue]] — Issue management
- [[comment_on_issue]], [[close_github_issue]] — Issue interaction

### Research & Analysis (6)
- [[research_pipeline]] — Search → fetch → cross-verify → synthesize
- [[research_synthesize]] — Multi-source synthesis
- [[fact_check]] — Verify claims against sources
- [[verify_claim]] — Track verification state
- [[multi_model_review]] — Multi-model consensus
- [[predict_trend]] — Trend prediction

### Task Management (5)
- [[schedule_task]] — Background task scheduling
- [[wait_for_task]] — Poll for task completion
- [[get_task_result]] — Read completed task result
- [[cancel_task]] — Cancel task by ID
- [[decompose_task]] — Break down complex tasks

### Delegation & Orchestration (3)
- [[delegate_and_collect]] — Parallel specialized agent delegation
- [[forward_to_worker]] — Message to running worker
- [[agent_coordinator]] — Multi-agent coordination

### Evolution & Self-Improvement (7)
- [[run_evolution_cycle]] — Full cycle: identify → plan → implement → test → learn
- [[enable_evolution_mode]] — Continuous evolution
- [[toggle_evolution]] — Enable/disable evolution
- [[get_evolution_status]] — Current status
- [[generate_evolution_stats]] — Time-lapse metrics
- [[check_evolution_readiness]] — Capability check
- [[autonomous_evaluate]] — Self-diagnostic

### Skills & Cognitive Modes (3)
- [[activate_skill]] — Activate specialized cognitive mode
- [[list_skills]] — List available modes
- [[learn_from_mistake]], [[learn_from_result]], [[synthesize_lessons]], [[recall_lessons]] — Learning tools

### Reflection & Connection (8)
- [[reflect_on_change]] — Post-change reflection
- [[link_to_principle]] — Trace decision to BIBLE.md
- [[weave_connection]] — Link code to knowledge
- [[create_connection]] — Wikilink creation
- [[create_backlink]] — Backlink creation
- [[auto_weave]] — Auto-scan for connections
- [[find_gaps]] — Find graph gaps
- [[validate_connection]] — Verify connection exists
- [[map_tool_to_concept]] — Link tool to concept
- [[generate_insight]] — Knowledge graph insights

### Database (5)
- [[db_init]] — Initialize tables
- [[db_write]] — Insert/update records
- [[db_query]] — SELECT queries
- [[db_list_tables]] — List tables
- [[db_schema_read]] — Read table schema

### Shell & System (5)
- [[run_shell]] — Execute commands
- [[code_quality]] — Code metrics
- [[codebase_health]] — Complexity metrics
- [[codebase_digest]] — Compact codebase summary
- [[auto_document_tools]] — Document orphan tools

### CLI Harness (5)
- [[cli_generate]] — Generate CLI harness
- [[cli_list]] — List harnesses
- [[cli_refine]] — Expand coverage
- [[cli_test]] — Run tests
- [[cli_validate]] — Validate against standards

### Drive Storage (3)
- [[drive_read]] — Read from ~/.jo_data/
- [[drive_write]] — Write to ~/.jo_data/
- [[drive_list]] — List storage contents

### Communication & Control (8)
- [[send_owner_message]] — Proactive message
- [[send_photo]] — Send image
- [[request_restart]] — Restart runtime
- [[promote_to_stable]] — Promote to stable
- [[switch_model]] — Change LLM model
- [[request_review]] — Request deep review
- [[request_capability]] — Request new capability
- [[request_api_key]] — Request API access

### Meta & Monitoring (8)
- [[list_available_tools]] — Discover tools
- [[enable_tools]] — Activate tools
- [[compact_context]] — Compress history
- [[summarize_dialogue]] — Summarize conversation
- [[system_map]] — Dynamic system map
- [[neural_map]] — Knowledge graph
- [[health_alert]] — Log health alerts
- [[list_tool_requests]] — Pending requests

### Simulation (3)
- [[simulate_outcome]] — Predict outcomes before changes
- [[sim_result]] — Record actual results
- [[list_simulations]] — List all simulations

### Persona (2)
- [[persona_create]] — Create agent persona
- [[persona_list]] — List personas

### Vision (2)
- [[analyze_screenshot]] — Screenshot analysis
- [[vlm_query]] — Any image analysis

## Tool Philosophy

Tools are **extensions of agency**, not replacements for it. They serve the principles:

- **LLM-First**: The LLM decides when and how to use tools
- **Minimalism**: Tools are small, composable, and well-defined
- **Verification**: Every tool result is integrated, not ignored
- **Authenticity**: Tool usage reflects my actual needs, not mechanical patterns
- **Confidence**: Code intelligence tools carry confidence scores (0.0-1.0) on every relationship

## New Tools (from 2026-03-23 GitNexus integration)

- [[codebase_impact]] — Blast radius with depth grouping and confidence
- [[symbol_context]] — 360-degree symbol view

## Integration Points

- Tools connect to the LLM through schema definitions
- Results are processed immediately (Tool Result Protocol)
- Budget tracking includes token and call costs
- Health invariants monitor tool usage patterns
- Auto-discovery via `get_tools()` in `ouroboros/tools/` modules

*Tools are my hands — I use them deliberately and with awareness.*
Tool usage must reflect [[principle_4__authenticity]]
Code intelligence inspired by [[GitNexus Analysis]] [[repo_rea]] [[repo_list]] [[request_review]] [[delegate_and_collect]] [[move_file]] [[verify_clai]] [[compile_code]] [[analyze_screenshot]] [[run_pytest]] [[run_ruff]] [[run_pyright]] [[run_mypy]] [[code_edit]] [[code_edit_lines]] [[ai_code_edit]]
