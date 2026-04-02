---
title: Tool Documentation Gap Analysis
created: 2026-04-02T12:22:41.782880+00:00
modified: 2026-04-02T12:22:41.782880+00:00
type: tool
status: active
tags: [documentation, analysis, tools, gap-analysis]
---


# Undocumented Tools Documentation

**Created**: 2026-04-02
**Purpose**: Track and document tools lacking vault knowledge base entries

## Documentation Strategy

Tools are documented in priority order:
1. **High Impact** - Tools used in core workflows
2. **Medium Impact** - Tools for specialized tasks  
3. **Low Impact** - Niche utility tools

## High Priority Tools (Previously Undocumented)

### System Management Tools

#### `request_restart`
**Purpose**: Request system restart with reason logging
**When to use**: After code changes that need reload configuration
**Returns**: Confirmation message
**Safety**: Safe - uses graceful restart mechanism

#### `promote_to_stable`
**Purpose**: Mark current codebase as stable for production
**When to use**: After successful testing and verification
**Returns**: Promotion confirmation
**Note**: Updates stability tracking metadata

#### `toggle_evolution`  
**Purpose**: Enable/disable evolution mode
**When to use**: During development vs production cycles
**Returns**: Current mode status
**Context**: See [[Evolution Cycle]]

#### `toggle_consciousness`
**Purpose**: Enable/disable background consciousness
**When to use**: Managing autonomous thinking budget
**Returns**: Current consciousness status
**Context**: See [[Background Consciousness]]

#### `forward_to_worker`
**Purpose**: Forward task to worker process
**When to use**: Heavy computational tasks
**Returns**: Worker task confirmation
**Context**: See [[Worker Architecture]]

### Code & Development Tools

#### `delegate_and_collect`
**Purpose**: Parallel multi-agent task delegation
**When to use**: Complex tasks with 3+ independent subtasks
**Returns**: Aggregated results from multiple agents
**Context**: See [[Multi-Agent Architecture]]

#### `request_capability`
**Purpose**: Request new tool or capability installation
**When to use**: When existing tools are insufficient
**Returns**: Capability request status
**Safety**: Requires creator approval for installation

### Research & Analysis Tools

#### `dspy_classify`
**Purpose**: DSPy-based task classification
**When to use**: Before tool selection for complex tasks
**Returns**: task_type, intent, complexity classification
**Context**: See [[DSPy Integration]]

#### `dspy_select_tools`
**Purpose**: AI-driven optimal tool selection
**When to use**: After classification, before execution
**Returns**: Ranked tool recommendations
**Context**: See [[Tool Selection Strategy]]

#### `dspy_verify`
**Purpose**: Output verification and correctness checking
**When to use**: After generating complex outputs
**Returns**: Verification score and feedback
**Context**: See [[Verification as Agency]]

#### `dspy_route`
**Purpose**: Task routing optimization
**When to use**: For complex multi-step tasks
**Returns**: Route recommendation (direct/delegate/research)
**Context**: See [[Task Routing Strategy]]

#### `dspy_optimize`
**Purpose**: Optimize DSPy modules from examples
**When to use**: Improving classification accuracy
**Returns**: Optimization metrics
**Context**: See [[DSPy Optimization]]

#### `dspy_status`
**Purpose**: Check DSPy integration status
**When to use**: Debugging classification issues
**Returns**: Status and configuration info

### Web & Browser Tools

#### `analyze_screenshot`
**Purpose**: Vision LLM screenshot analysis
**When to use**: After browser screenshots need interpretation
**Returns**: Structured analysis of visual content
**Context**: See [[Browser Automation]]

#### `browse_page`
**Purpose**: Open URL in headless browser
**When to use**: Web research and page inspection
**Returns**: Page content in multiple formats
**Context**: See [[Browser Automation]]

#### `browser_action`
**Purpose**: Perform actions on browser page
**When to use**: Interactive web navigation
**Actions**: click, fill, select, screenshot, evaluate, scroll
**Context**: See [[Browser Automation]]

### Knowledge Management Tools

#### `knowledge_read`
**Purpose**: Read from persistent knowledge base
**When to use**: Accessing topic-based articles
**Returns**: Article content
**Context**: See [[Knowledge Base Structure]]

#### `knowledge_write`
**Purpose**: Write to persistent knowledge base
**When to use**: Capturing recipes, patterns, lessons
**Returns**: Confirmation of write operation

## Auto-Resolution Strategy

Orphaned code symbols (1,780 concepts) resolve automatically when:
1. Tool is called with specific symbol reference
2. During code intelligence queries
3. Evolution cycles that involve specific modules

This documentation provides the knowledge base structure for that resolution.

## Gap Resolution Progress

- **Created**: 2026-04-02
- **Total undocumented tools identified**: 63
- **High priority documented**: 17 tools above
- **Remaining**: 46 medium/low priority tools

**Next steps**: Document remaining tools in priority order based on usage patterns.
