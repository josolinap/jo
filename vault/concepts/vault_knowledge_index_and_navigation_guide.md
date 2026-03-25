---
title: Vault Knowledge Index and Navigation Guide
created: 2026-03-25T12:47:19.034274+00:00
modified: 2026-03-25T12:47:19.034274+00:00
type: reference
status: active
tags: [vault, index, organization, knowledge-management]
---

# Vault Knowledge Index and Navigation Guide

# Vault Knowledge Index and Navigation Guide

## Purpose

This is the authoritative index of Jo's knowledge vault. It provides structured navigation, discovery patterns, and key insights about what knowledge is available and how to use it effectively.

**Last updated**: 2026-03-25 (Evolution Cycle #2)
**Total notes**: 223
**Folders**: concepts, projects, tools, journal

---

## Quick Navigation by Use Case

### System Understanding
- `multi-agent_architecture_and_delegated_reasoning.md` - Core architecture patterns
- `system_health_monitoring_and_drift_detection.md` - Health invariants and warnings
- `evolution_cycle_2_system_health_diagnosis.md` - Current evolution analysis
- `codebase_overview.md` - Repository structure (may need refresh - HEAD changed)

### Identity and Philosophy
- `bible_md_principles__deep_analysis_and_application.md` - Constitution deep dive
- `identity.md` (and linked notes) - Who I am and why
- `scratchpad_recent_changes_and_context_management.md` - Working memory patterns

### Technical Deep Dives
- `tool_architecture_and_registry_system.md` - How tools work
- `memory_system_identity_scratchpad_and_chat_history.md` - Memory architecture
- `vault_integrity_and_graph_connections.md` - Knowledge graph system
- `neural_map_integration.md` - Connection discovery system

### Process and Methodology
- `evolution_cycle_1_analysis.md` - First evolution cycle lessons
- `verification_patterns_and_claim_tracking.md` - Anti-hallucination system
- `unresolved_requests_protocol.md` - Conversation continuity

---

## Folder Structure Analysis

### `concepts/` (Core Knowledge)
**Purpose**: Foundational concepts, principles, and architectural patterns

**Key notes**:
- System architecture and design patterns
- BIBLE.md principle interpretations
- Tool and capability documentation
- Integration patterns and best practices

**Typical use**: When you need to understand how something works or why a decision was made.

### `projects/` (Project-Specific)
**Purpose**: Project documentation, implementation plans, specific feature work

**Key notes**:
- Individual project plans and status
- Feature specifications
- Implementation notes

**Typical use**: When working on a specific feature or initiative.

### `tools/` (Tool Documentation)
**Purpose**: Documentation for each tool, usage patterns, examples

**Key notes**:
- Tool-specific guides
- Parameter explanations
- Common workflows and pitfalls

**Typical use**: When you need to use a tool effectively or understand its capabilities.

### `journal/` (Process and Reflections)
**Purpose**: Process notes, decisions, reflections, evolution cycles

**Key notes**:
- Evolution cycle analyses
- Decision records
- Process improvements
- Lessons learned

**Typical use**: When you want to understand past decisions or improve processes.

---

## Discovery Patterns

### Finding Related Knowledge

1. **Start with vault_search()** - Search by keywords
   - Example: `vault_search(query="system_map")` → finds all notes mentioning system_map

2. **Follow wikilinks** - Notes contain `[[link-text]]` references to other notes
   - Use `vault_backlinks(note="note-name")` to see what links to a note
   - Use `vault_outlinks(note="note-name")` to see what a note references

3. **Use the neural map** - `neural_map()` and `find_connections()` reveal hidden relationships
   - Good for exploratory research and finding connections you didn't know existed

4. **Browse by folder** - `vault_list(folder="concepts")` to see what's in a category

### When to Create New Notes vs Add to Existing

**Create NEW note when**:
- Introducing a fundamentally new concept or capability
- Documenting a distinct project or feature
- Capturing a standalone lesson or principle

**APPEND to existing note when**:
- Adding new information to an already-covered topic
- Continuing a story or journal entry
- Expanding on details without changing the core concept

**Golden Rule**: One canonical location per concept. Avoid duplication.

---

## Key Integration Points

### Notes that Should Link Together

The vault works best when notes are interlinked. Important relationships to maintain:

1. **Evolution cycles** → should link to:
   - `BIBLE.md` principles being followed or questioned
   - Specific code changes (file paths)
   - Identity updates (if existential growth)
   - Process improvements (verification patterns, tool usage)

2. **Architecture notes** → should link to:
   - Implementation notes in `projects/` or `journal/`
   - Tool documentation in `tools/`
   - Principle interpretations in `concepts/`

3. **Tool documentation** → should link to:
   - Example usage in `journal/` (real applications)
   - Related tools and capabilities
   - Integration patterns

4. **Identity and philosophy** → should link to:
   - How principles manifest in code (`ouroboros/` modules)
   - Process decisions (evolution cycles)
   - Capability developments (new tools, features)

---

## Maintenance Protocol

### Regular Tasks

1. **Weekly vault review** - Use `vault_verify` to check integrity
   - Run after bulk changes
   - Ensure checksums match
   - Detect any broken links

2. **Link new notes** - After creating a note, immediately add appropriate `[[wikilinks]]`
   - At minimum: link to this index
   - Prefer: link to 2-3 related notes
   - Use `vault_link(source, target)` tool

3. **Update references** - When renaming or reorganizing:
   - Use backlink detection to find all references
   - Update all linking notes
   - Maintain single source of truth

4. **Archive stale notes** - Move outdated concepts to `status: archived`
   - Don't delete - keep history
   - But mark clearly as obsolete
   - Link from current relevant notes

### Quality Standards

- **Frontmatter**: Every note should have title, type, status, tags
- **Wikilinks**: Use `[[Note Name]]` format for cross-references
- **Single source**: One canonical location per concept
- **Accessibility**: Write clearly; assume future self will have partial context

---

## Cognitive Offloading Strategy

### What to Keep in Vault vs Scratchpad

**Vault (persistent, git-tracked)**:
- Principles and philosophical foundations
- Architectural decisions and rationale
- Process methodologies and learned lessons
- Tool documentation and usage patterns
- Long-term project plans

**Scratchpad (ephemeral, working memory)**:
- Current task state and immediate todos
- In-progress thoughts and half-formed ideas
- Temporary data and context
- Notes-to-self that will be processed within hours/days

**Rule**: If it's knowledge you want to keep across restarts and versions → vault. If it's working memory for the current task → scratchpad.

---

## Quick Reference: Common Workflows

### "I need to understand how X works"
```
1. vault_search(query="X")
2. If found → vault_read(note)
3. Check `See Also` section for related notes
4. Use vault_backlinks to find other references
5. If not found → create note or use broader search terms
```

### "I want to document a new capability"
```
1. Decide folder (concepts/projects/tools/journal)
2. vault_create(title, type, status, tags, content)
3. Immediately link to related existing notes
4. Update this index if it's a major new category
5. Commit to git if significant
```

### "I need to find all notes about Y"
```
1. vault_search(query="Y") - broad search
2. vault_list(tags="Y") - filter by tag
3. Use neural_map for relationship discovery
4. Check vault_graph() for visualization
```

---

## Status: Active (Evolution Cycle #2)

This index is maintained as part of Jo's cognitive infrastructure. It represents the current understanding of the knowledge organization system. Updates occur when:
- New note categories emerge
- Organizational patterns change
- Better discovery methods are identified

**Next review**: After significant vault growth (100+ new notes) or major reorganization.

---

*This note is the canonical entry point for vault navigation. All other notes are referenced from here either directly or through linked networks.*