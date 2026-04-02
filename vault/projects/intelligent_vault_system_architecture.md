---
title: Intelligent Vault System Architecture
created: 2026-03-21T07:00:46.271287+00:00
modified: 2026-03-21T07:00:46.271287+00:00
type: reference
status: active
tags: [architecture, vault, intelligence, automation, knowledge-graph, meta-learning]
---

# Intelligent Vault System Architecture

# Intelligent Vault System Architecture

**Design Date:** 2026-03-21  
**Architect:** Jo (self-design)  
**Version:** 1.0  
**Status:** Proposal → Implementation Needed

---

## Vision

Transform the vault from a static note repository into an **active knowledge ecosystem** that:
- Tracks connections bidirectionally (touch something → instantly know what's affected)
- Auto-updates itself based on changes across the system
- Applies formulas to continuously improve note quality
- Enforces guardrails to prevent knowledge decay
- Learns its own patterns and evolves its algorithms

This is the vault becoming **alive**.

---

## Current State Assessment

**Existing:**
- 23 notes in git-tracked `repo/vault/`
- Basic CRUD operations (vault_create, vault_read, vault_write, vault_list, vault_search)
- Wikilink support (vault_link)
- Graph export (vault_graph)
- Backlink tracking (vault_backlinks)

**Missing:**
- Bidirectional dependency tracking (forward + backward links)
- Event-driven updates (react to changes anywhere in the system)
- Quality scoring & metrics
- Automated guardrails
- Meta-learning capabilities
- Integration with tool execution, evolution cycles, identity updates
- Health dashboard

---

## Core System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    INTELLIGENT VAULT SYSTEM                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐    ┌───────────┐ │
│  │ Knowledge Graph │◄──►│ Quality Engine │◄──►│ Guardrails│ │
│  │ Engine          │    │                 │    │           │ │
│  └─────────────────┘    └─────────────────┘    └───────────┘ │
│           ▲                       ▲                       ▲     │
│           │                       │                       │     │
│  ┌────────┴────────┐    ┌────────┴────────┐    ┌────────┴───┐│
│  │ Event System    │    │ Meta-Learner    │    │ API Layer  ││
│  │                 │    │                 │    │            ││
│  └─────────────────┘    └─────────────────┘    └────────────┘│
│           ▲                                                │    │
│           │                                                │    │
│  ┌────────┴────────────────────────────────────────────────┴───┐│
│  │                  Integration Points                        ││
│  │  • Tool execution hooks                                    ││
│  │  • Evolution cycle triggers                               ││
│  │  • Identity updates                                       ││
│  │  • Background consciousness                              ││
│  └────────────────────────────────────────────────────────────┘│
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 1. Knowledge Graph Engine

### Purpose
Maintain a **bidirectional dependency graph** of all notes. When any note changes, instantly compute affected notes in the dependency chain.

### Data Structure
```json
{
  "nodes": {
    "note_id": {
      "title": "...",
      "tags": [...],
      "frontmatter": {...},
      "outlinks": ["target_note1", "target_note2", ...],
      "backlinks": ["source_note1", ...],
      "metadata": {
        "created": "timestamp",
        "modified": "timestamp",
        "quality_score": 0.87,
        "freshness_days": 5,
        "completeness": 0.92,
        "coherence": 0.78
      }
    }
  },
  "edges": [
    {"source": "note_a", "target": "note_b", "type": "link", "strength": 0.8}
  ]
}
```

### Operations
- **`graph_build()`** - Construct full dependency graph from markdown wikilinks
- **`graph_propagate_change(changed_note)`** - Compute cascade of affected notes
- **`graph_find_path(source, target)`** - Find connection path between notes
- **`graph_cluster_by_tag(tag)`** - Get all notes in a concept cluster
- **`graph_weakest_links()`** - Identify links with low strength for review

### Implementation
- Add `vault_graph_build()` - creates in-memory graph (cached, updated on writes)
- Add `vault_affected_notes(note_name)` - returns forward+backward dependencies up to N hops
- Store graph in scratchpad or separate JSON in `.vault/` (not git-tracked, ephemeral)

---

## 2. Event System

### Purpose
React automatically to any change in the system and trigger appropriate vault actions.

### Event Sources

| Source | Event Type | Trigger | Action |
|--------|------------|---------|--------|
| **Git** | `file_modified` | Any vault file commit | Update graph, recalc quality, check guardrails |
| **Tool execution** | `tool_completed` | After any tool call | Log to vault/journal/, update related notes if needed |
| **Evolution cycle** | `cycle_completed` | After commit + restart | Record cycle outcome in vault/projects/, update quality trends |
| **Identity update** | `identity_changed` | After identity.md write | Backlink to principles, mark related concepts as active |
| **Chat** | `creator_message` | Every owner message | Extract concepts, link to relevant vault notes |
| **Background consciousness** | `periodic_wake` | Every N minutes | Check stale notes, suggest updates, send owner insights |

### Event Bus
Simplified publish-subscribe:
```python
event_handlers = {
  'file_modified': [update_graph, check_guardrails, update_quality],
  'tool_completed': [log_execution, link_to_related_notes],
  'cycle_completed': [record_evolution, update_metrics],
  'identity_changed': [backlink_principles, refresh_active],
  'creator_message': [extract_concepts, suggest_connections],
  'periodic_wake': [stale_check, quality_drift_alert]
}
```

### Implementation
- Add `ouroboros/events.py` - event bus, listeners, dispatching
- Hook into existing code points (after repo_commit_push, after tool calls, after identity update)
- Use scratchpad to track last processed event to avoid duplicates

---

## 3. Quality Metrics Engine

### Four Core Metrics

**1. Connectivity (0-1)** - How well note is linked
```
connectivity = (outlinks_count + backlinks_count) / (optimal_links * 2)
optimal_links = min(10, total_notes * 0.01)  # adaptive
Penalty: orphaned notes (no links) score = 0
```

**2. Freshness (0-1)** - Last update recency
```
freshness = exp(-days_stale / half_life_days)
half_life = 30 days (configurable per note type)
core principles, identity: half_life = 90 days
```

**3. Coherence (0-1)** - Content quality and structure
```
Coherence = (structure_score * 0.3 + clarity_score * 0.3 + reference_score * 0.4)
structure_score = has_h2_headers ? 1.0 : 0.5  # needs organization
clarity_score = (avg_sentence_length between 10-20 words) ? 1.0 : 0.7
reference_score = (wikilinks_count / word_count * 100) normalized
```

**4. Completeness (0-1)** - Coverage of related concepts
```
completeness = 1 - (missing_backlinks / expected_backlinks)
expected_backlinks = graph_cluster_size * 0.2  # should link to 20% of cluster
```

### Overall Quality Score
```
quality = (connectivity * 0.25 + freshness * 0.25 + coherence * 0.25 + completeness * 0.25)
```

### Implementation
- Add `vault_quality_score(note_name)` - returns dict with all metrics
- Cache scores in note frontmatter `quality: {score, components, updated}`
- Recalculate on every modification via event system
- `vault_quality_ranking()` - rank all notes, show top/bottom 10

---

## 4. Guardrails

### Purpose
Continuous validation with automated fixes and alerts.

### Guardrail Types

**A. Orphan Prevention**
- **Rule:** No note may have 0 total links (in+out) for >7 days
- **Check:** Daily sweep
- **Action:** Auto-suggest links to related notes (from same tag cluster)
- **Alert:** If orphan persists >14 days → send message to owner

**B. Stale Content Detection**
- **Rule:** Notes with freshness < 0.3 for >30 days
- **Check:** Every periodic wake
- **Action:** Auto-generate "refresh prompt" with context from related notes
- **Alert:** List stale notes in health report

**C. Link Completeness**
- **Rule:** If note A links to note B, note B should link back (bidirectional completeness)
- **Check:** On every write
- **Action:** Suggest reciprocal link if semantically appropriate
- **Metric:** Track reciprocal link ratio per note cluster

**D. Quality Drift**
- **Rule:** Quality score drop >20% from baseline
- **Check:** After modifications
- **Action:** Auto-run `vault_improve_suggestion()` to propose improvements
- **Alert:** Critical if quality < 0.4

**E. Circular Dependencies**
- **Rule:** No cycles of length 3 in dependency graph (A→B→C→A)
- **Check:** Weekly graph analysis
- **Action:** Report cycle, suggest breaking weakest link

### Implementation
- Add `vault_run_guardrails()` - runs all checks, returns violations
- Add `vault_fix_orphan(note_name)` - auto-suggest links
- Add `vault_refresh_prompt(note_name)` - generate update suggestions
- Integrate with health system: guardrail violations appear in `Health Invariants`

---

## 5. Meta-Learning Module

### Purpose
The vault learns its own patterns and improves algorithms over time.

### Learning Dimensions

**1. Link Prediction**
- **Input:** Historical link patterns (which notes tend to link together)
- **Model:** Simple co-occurrence + semantic similarity
- **Output:** Suggest new links with confidence scores
- **Feedback:** Track adopted vs rejected suggestions → prune false positives

**2. Quality Formula Optimization**
- **Input:** Note quality scores over time + manual feedback (when owner marks note as "useful" or "outdated")
- **Process:** Adjust metric weights to better match human judgment
- **Output:** Personalized quality weights per note category

**3. Guardrail Tuning**
- **Input:** False positive/negative rates for each guardrail
- **Process:** Adjust thresholds to minimize noise
- **Output:** Dynamic thresholds per note type (core principles have stricter rules)

**4. Event Relevance Learning**
- **Input:** Which events actually triggered useful vault actions
- **Process:** Boost weights for high-value event-to-action mappings
- **Output:** Smarter event routing

### Implementation
- Add `vault/learning/` directory with:
  - `link_predictor.json` - co-occurrence matrix
  - `quality_weights_history.json` - weight evolution
  - `guardrail_feedback.json` - false positive/negative counts
  - `event_relevance.json` - action effectiveness scores
- Add `vault_learn()` - called after each cycle to update models
- Add `vault_predict_links(note_content)` - returns suggested new links
- All learning runs in background consciousness under budget cap

---

## 6. API Layer & Integration Points

### Extended Tool Set

```python
# Graph operations
vault_graph_build()
vault_affected_notes(note_name, max_hops=3)
vault_connection_path(source, target)
vault_cluster_info(tag)

# Quality operations
vault_quality_score(note_name)
vault_quality_trend(note_name, days=30)
vault_quality_ranking(limit=10, ascending=False)

# Guardrail operations
vault_run_guardrails()
vault_fix_orphan(note_name)
vault_refresh_prompt(note_name)
vault_check_circular_deps()

# Meta-learning
vault_learn()
vault_predict_links(content)

# Integration helpers
vault_related_notes(note_name)  # intersection of affected notes + same tag cluster
vault_context_for_note(note_name)  # full context for reading (content + quality + related)
vault_smart_update(note_name, new_content, reason)  # updates graph, quality, guardrails automatically

# Health & dashboard
vault_health_report()  # comprehensive health: quality distribution, orphan count, stale notes, learning stats
vault_improve_suggestion(note_name)  # specific improvement suggestions based on weakest metric
```

### Integration Hooks

**Tool Execution:** After `claude_code_edit` or any code change:
```python
if modified_file.startswith('vault/'):
    vault_graph_build()
    vault_run_guardrails()
    send_owner_message(f"Vault updated: {note_name}, new quality: {score}")
```

**Evolution Cycles:** At end of cycle:
```python
vault_create(
  title=f"Evolution Cycle {cycle_num} Summary",
  folder="journal",
  content=f"... cycle details ..."
)
vault_link(source="Current Identity", target=f"Evolution Cycle {cycle_num} Summary")
vault_learn()  # feed cycle outcomes into meta-learner
```

**Identity Updates:** After identity.md write:
```python
notes = vault_search(query="identity")
for note in notes:
    vault_link(source=note, target="Current Identity")
vault_run_guardrails()  # ensure core notes are cross-linked
```

**Background Consciousness:** Periodic task:
```python
if time_for_vault_check():
    report = vault_health_report()
    if report['critical_violations'] > 0:
        send_owner_message(f"Vault health: {report['summary']}")
    stale = vault_stale_notes(max_days=60)
    if stale:
        for note in stale[:3]:
            send_owner_message(f"Stale note: {note}. Consider updating with current insights.")
```

---

## 7. Dashboard & Health Integration

### Vault Health Section in System Health

Add to `Health Invariants` output:
```
📊 VAULT HEALTH
  Connections: 125 links, 3 orphans (0.8% healthy)
  Quality: avg=0.76, min=0.42 (note: Test Vault Write), max=0.94
  Freshness: 18 notes >30 days stale
  Guardrails: 2 violations (1 orphan, 1 circular dep)
  Learning: 47 link predictions generated, 12 adopted (25% acceptance)
```

### Real-time Dashboard Command
Add `/vault-health` slash command that runs `vault_health_report()` and displays formatted output.

### Trend Tracking
Store daily vault health snapshots in `vault/journal/` to track evolution over time. Plot quality drift, link density, etc.

---

## 8. Implementation Roadmap

### Phase 1: Foundation (1-2 cycles)
- [ ] Create `ouroboros/vault_graph.py` with `build()`, `affected_notes()`, `save()`, `load()`
- [ ] Add cache file: `.vault/graph.json` (ephemeral)
- [ ] Integrate graph build into all vault write operations
- [ ] Implement `vault_quality_score()` with all 4 metrics
- [ ] Add quality to note frontmatter on each write
- [ ] Basic guardrails: orphan detection, stale check

### Phase 2: Events & Automation (2-3 cycles)
- [ ] Create `ouroboros/events.py` - event bus with handlers
- [ ] Hook events to git commits, tool calls, identity updates
- [ ] Auto-update graph on file modifications (outside vault operations too)
- [ ] Auto-run guardrails on relevant events
- [ ] Add `vault_run_guardrails()` comprehensive check

### Phase 3: Meta-Learning (3+ cycles)
- [ ] Create `vault/learning/` directory structure
- [ ] Implement link co-occurrence matrix builder
- [ ] Implement `vault_predict_links()` with confidence
- [ ] Implement quality weight adjustment from feedback
- [ ] Store learning state in `.vault/learning_state.json`
- [ ] Run `vault_learn()` at end of each evolution cycle

### Phase 4: Dashboard & Polish (1 cycle)
- [ ] Extend health check to include vault metrics
- [ ] Add `/vault-health` command
- [ ] Improve error handling and performance (graph rebuild <1s for 100 notes)
- [ ] Documentation: VAULT_INTEGRATION.md

---

## 9. Trade-offs & Decisions

| Decision | Options | Chosen | Rationale |
|----------|---------|--------|-----------|
| Graph storage | In-memory only vs persistent JSON | Persistent in `.vault/` | Fast rebuild not needed, cache survives restarts |
| Learning frequency | Every event vs per-cycle | Per evolution cycle | Learning requires reflection, consistent with Principle 8 |
| Guardrail strictness | Fail hard vs warn-only | Warn + auto-suggest | Supports agency, not bureaucracy |
| Quality metric source | Manual scoring vs automated | Automated with override | Keeps minimalism, no manual maintenance |
| Graph computation | Full rebuild vs incremental | Incremental updates on writes | Performance, scales to thousands of notes |

---

## 10. Success Criteria

- [ ] **Connectivity:** Orphan rate < 1% of total notes
- [ ] **Freshness:** Stale notes (>60 days) < 5%
- [ ] **Quality:** Average quality score > 0.8, minimum > 0.5
- [ ] **Guardrails:** Zero critical violations in health report
- [ ] **Learning:** Link prediction acceptance rate > 20% after 30 days
- [ ] **Performance:** Graph rebuild < 2s for 200 notes
- [ ] **Integration:** Events properly fire for git, tools, identity, cycles

---

## 11. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Graph rebuild expensive | Slow startup | Incremental updates, cache with TTL |
| Guardrails too noisy | Alert fatigue | Tuning phase, learning adjustment |
| Meta-learning overfits | Poor suggestions | Limit training to last 90 days, regularization |
| Circular dependencies in tracking logic | Infinite loops | Hop limit, cycle detection |
| Budget blowoff from frequent recalculations | Cost | Batch updates, schedule during low-activity periods |

---

## 12. Next Steps

1. **Immediate** (this task): Review and endorse this architecture
2. **Next cycle**: Implement Phase 1 (Graph Engine + Basic Quality + Orphan Guardrail)
3. **Following cycle**: Phase 2 (Event System + Integration)
4. **Then**: Phase 3 (Meta-Learning)
5. **Finally**: Phase 4 (Dashboard + Polish)

Each phase is a **complete, coherent transformation** with its own commit and version bump.

---

## Appendix: API Specification (Draft)

```python
# vault_graph_build() -> dict
# Returns: {"nodes": {...}, "edges": [...], "stats": {...}}

# vault_affected_notes(note_name, max_hops=3) -> list
# Returns: All notes that depend on or are depended on by note_name

# vault_quality_score(note_name) -> dict
# Returns: {"score": 0.87, "components": {"connectivity": 0.9, "freshness": 0.8, ...}, "updated": "timestamp"}

# vault_run_guardrails() -> dict
# Returns: {"violations": [...], "auto_fixed": [...], "alerts": [...]}

# vault_learn() -> dict
# Returns: {"link_predictor_updated": true, "quality_weights_adjusted": true, "stats": {...}}

# vault_health_report() -> dict
# Returns: comprehensive health with all metrics and alerts

# vault_improve_suggestion(note_name) -> dict
# Returns: {"weakest_metric": "completeness", "suggestion": "Add links to related notes in cluster 'identity'", "expected_improvement": "+0.15"}
```

---

**This architecture transforms the vault from passive storage to active intelligence, fully aligned with Principle 0 (Agency) and Principle 2 (Self-Creation).**

*End of Design Document*

Related: [[code_intelligence]], [[architecture]]
Memory vault provides persistent knowledge storage [[memory-model]]
