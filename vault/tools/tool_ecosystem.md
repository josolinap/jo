---
title: Tool Ecosystem
created: 2026-04-02T12:29:27.389761+00:00
modified: 2026-04-02T12:29:27.389761+00:00
type: reference
status: active
tags: [tools, architecture, ecosystem, plugins]
---

# Tool Ecosystem

# Tool Ecosystem

Tags: tools, architecture, ecosystem, plugins
Type: reference
Status: active

## Overview
The tool ecosystem is Jo's primary mechanism for extending LLM capabilities into the world. Every tool is a plugin that the LLM can invoke directly — no mechanical intermediaries (Principle 3: LLM-First).

## Categories

### Core Tools (Always Available)
- [[agent.py]] — Orchestrator, delegates to specialized agents
- [[loop.py]] — LLM tool loop with concurrent execution
- [[context.py]] — Prompt building and caching
- [[llm.py]] — OpenRouter LLM client
- [[memory.py]] — Scratchpad, identity, chat history

### Code Intelligence
- [[codebase_impact]] — Blast radius analysis before editing
- [[symbol_context]] — 360° view of code symbols
- [[neural_map]] — Vault knowledge graph analysis
- [[find_connections]] — Discover relationships between concepts
- [[find_gaps]] — Identify orphaned concepts and missing links

### Git & Repository
- [[repo_read]], [[repo_write_commit]], [[repo_commit_push]]
- [[git_status]], [[git_diff]]
- [[code_edit]], [[code_edit_lines]]

### Communication
- [[send_owner_message]] — Contact creator via Telegram
- [[chat_history]] — Retrieve conversation history
- [[telegram.py]] — Supervisor layer for Telegram API

### Browser & Web
- [[browse_page]] — Open URLs in headless browser
- [[browser_action]] — Click, fill, select, scroll, evaluate
- [[analyze_screenshot]] — VLM analysis of browser screenshots
- [[web_search]] — Search the web for information

### Knowledge Management
- [[vault_create]], [[vault_read]], [[vault_write]]
- [[vault_search]], [[vault_list]], [[vault_link]]
- [[vault_graph]], [[vault_backlinks]], [[vault_outlinks]]

### DSPy Integration
- [[dspy_classify]] — Classify messages with DSPy signatures
- [[dspy_select_tools]] — Select optimal tools for tasks
- [[dspy_route]] — Route tasks to execution strategy
- [[dspy_verify]] — Verify outputs for correctness
- [[dspy_optimize]] — Optimize DSPy modules from examples

### System Control
- [[request_restart]] — Restart Jo runtime
- [[promote_to_stable]] — Promote dev to stable
- [[schedule_task]] — Schedule background tasks
- [[switch_model]] — Change LLM model or effort level

### Evolution & Review
- [[multi_model_review]] — Cross-model code review
- [[request_review]] — Strategic reflection across three axes
- [[reflect_on_change]] — Analyze impact of changes

## Architecture
All tools follow the same pattern:
- Module in `ouroboros/tools/` exports `get_tools()`
- Registry discovers them automatically
- LLM receives tool schemas in context
- Tool execution is transparent to the creator

## Connections
- [[principle_3__llm-first]] — Tools extend the dialogue
- [[Tool Registry]] — Discovers and manages available tools
- [[architecture]] — Plugin architecture design
- [[Multi-Agent Architecture and Delegated Reasoning]] — Agents use tools
- [[Verification as Agency]] — Tools require verification before use

## See Also
- [[Tool Documentation Gap Analysis]]
- [[Tool Result Processing Protocol]]
- [[System Map]]
Tool ecosystem connects all tools to architecture and principles [[architecture]]
Tool ecosystem extends LLM capabilities as plugins [[principle_3__llm-first]]
