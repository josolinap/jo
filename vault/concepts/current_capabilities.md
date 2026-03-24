---
title: Jo Current Capabilities (v6.4.0)
created: 2026-03-25
category: concepts
tags:  []

---

# Jo Current Capabilities (v6.4.0)

## Tool Inventory: 138 Tools

### Core Tools
- run_shell: Execute shell commands
- code_edit: Write files directly (no Claude needed)
- code_edit_lines: Replace specific lines
- repo_read, repo_write_commit: Git operations

### Analysis Tools
- codebase_graph: Build knowledge graph (585 nodes, 4233 edges)
- extraction: Extract structured info from code/text
- blind_validate: Validate without implementation bias

### Dynamic Tools
- runtime_tool_creator: Create new tools at runtime
- skill learning: Track what works best

## Systems Status

### Ontology System (TrustGraph-inspired)
- 7 task types: debug, review, evolve, refactor, test, implement, analyze
- Relationship strength tracking
- Auto-classification on first round

### Vault System
- 193 notes with structured knowledge
- Integrated with context enrichment
- Auto-generated graphs and summaries

### Protected Files
- 13 files require human approval
- Pre-commit hook enforces protection
- Case-insensitive checking

### Pipeline Features (5 enabled)
- Context enrichment
- Code normalization
- Semantic synthesis
- Task evaluation
- Structured pipeline

## Inspiration Sources
- TrustGraph: Ontology structuring
- LangExtract: Information extraction
- Zeroshot: Blind validation
- pi-mono: Differential context
- 724-Office: Runtime tool creation
- VikaasLoop: Skill learning

---
## Related

- [[architecture]]
