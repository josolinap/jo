# Knowledge-Graph + LLM-Agent + Memory Landscape: Research for Jo

**Prepared for:** the Jo autonomous agent (Ouroboros v6.5.1)
**Method:** GitHub REST API + GitHub Search API (unauthenticated, ~50 repo queries + 4 search queries) + direct audit of Jo's source tree (`ouroboros/vault_search.py`, `hybrid_memory.py`, `ontology_tracker.py`, `knowledge_decay.py`, `vault_engine.py`, `memory/identity.md`, `vault/concepts/*`, `docs/GITHUB_INSPIRATION.md`).
**Date of data:** Star counts and `pushed_at` fetched live from `api.github.com`. Note the sandbox clock reads 2026 — all "active" verdicts are based on `pushed_at` recency relative to that clock.

---

## 0. TL;DR

Jo already has more knowledge-graph machinery than the task description implied (`vault_engine.VaultGraphEngine`, `codebase_graph.py` with 585 nodes / 4 233 edges over the *code*, `ontology_tracker.py`, `knowledge_decay.py`, a `hybrid_memory.py` with embeddings + JSONL fact store, an `episodic_memory.py`). **But it has a clear, specific set of holes**, and the open-source landscape now has mature, well-starred projects that fill almost every one of them:

| Jo gap (confirmed from code) | Best-fit project | Stars |
|---|---|---|
| `VaultSemanticSearch` is **keyword-only**, no embeddings over the 378 vault notes | **Cognee** or **Graphiti** | 27.9k / 28.7k |
| Vault facts in `facts.jsonl` are **flat** — no entity graph, no edges between memories | **Graphiti** (Zep) | 28.7k |
| No **entity resolution** — "Jo", "BIBLE", "evolution" scattered across 50+ notes never unify | **Microsoft GraphRAG** entity extraction | 34.4k |
| No **structured/typed data** in vault frontmatter (no JSON-LD, no schema.org) | **RDFLib** + Obsidian **Dataview** (typed frontmatter) | 2.5k / 9.2k |
| No **temporal** episodic memory graph (events are append-only JSONL) | **Graphiti** (bi-temporal) or **Mem0** | 28.7k / 60.8k |
| `knowledge_decay.py` scores value from **wikilink counts only** — no semantic importance | **Cognee** importance scoring | 27.9k |
| No graph query language over the vault (cannot ask "all notes about Principle 1 linking to evolution") | **Oxigraph** (SPARQL) or Dataview DQL | 1.8k / 9.2k |
| Jo's vault never gets re-organised by the agent itself | **claude-obsidian** (Karpathy LLM-Wiki pattern) | 9.4k |
| No Google-native agent framework if you want to lean on Gemini/Vertex | **google/adk-python** | 20.6k |

**Top-5 recommendations (full detail in §5):** Graphiti, Cognee, Microsoft GraphRAG, claude-obsidian, Dataview + RDFLib.

---

## 1. A note on "Google's Open Knowledge Format"

I could not find a single Google repository literally named "Open Knowledge Format." The phrase almost certainly refers to Google's **umbrella of open knowledge-representation efforts**, which the OSS landscape uses as inspiration:

- **schema.org** — the typed-vocabulary project Google co-founded with Microsoft/Yahoo. This *is* an "open knowledge format" and is the de-facto standard for JSON-LD on the web.
- **JSON-LD** — Google's recommended serialization for structured data (used in Search, Knowledge Panels, Rich Results).
- **Google Knowledge Graph API** — read-only endpoint (`kgsearch.googleapis.com`) returning schema.org-typed entities; free, low-quota.
- **Google Data Commons** — open knowledge graph of statistical entities (Wikidata- and schema.org-aligned).
- **Google SLING** (`google/sling`, 1.9k★, **archived** 2021) — frame-semantics parser, the closest thing to an "open knowledge format" engine Google ever shipped as OSS.
- **google/adk-python** (Agent Development Kit, 20.6k★, very active) — Google's 2025 answer to LangGraph, with built-in memory + tool abstractions.

In §4-D I treat "Google's open knowledge projects" as this cluster. The actionable takeaway for Jo: **schema.org + JSON-LD is the format, and `google/knowledgegraph` (the API) + `RDFLib` are the tools.**

---

## 2. Jo's current architecture — what actually exists (audited from source)

Reading the tree under `/home/z/my-project/jo` rather than trusting the description:

| Component | File | What it really does | Gap it leaves |
|---|---|---|---|
| Vault graph | `ouroboros/vault_engine.py` `VaultGraphEngine`/`VaultGraph`/`VaultNote` | Builds graph of **wikilinks + backlinks** only. `find_path()` does BFS over link edges. | Structural links only — no semantic edges, no entity nodes. |
| Vault "semantic" search | `ouroboros/vault_search.py` `VaultSemanticSearch` | **Misnamed.** Pure substring/keyword matching on title/content/tags/frontmatter. Zero embeddings. | Vault has **no real semantic search**. |
| Vault gap detection | `VaultKnowledgeGaps._find_mentioned_topics()` | Finds Capitalised Words after a sentence end that aren't note titles. | Crude; misses camelCase, acronyms, lowercase concepts. |
| Hybrid memory | `ouroboros/hybrid_memory.py` `HybridMemory` | 3-layer: session ring → LLM fact extraction → `_SimpleVectorStore` (JSONL + cosine, hash-vector fallback). | Facts are **flat** — `MemoryFact{fact,keywords,persons,topic,session_key,vector}`. No edges between facts, no entity nodes, 30-day TTL silently drops. |
| Code graph | `ouroboros/codebase_graph.py` (1 354 lines, flagged CRITICAL oversized) | Builds 585-node / 4 233-edge graph over the **Python codebase** (imports, calls, classes). Persisted to `vault/concepts/codebase_graph.json`. | Rich graph for code, **nothing equivalent for the vault/concepts**. |
| Ontology | `ouroboros/ontology_tracker.py` | Tracks task-type → tool, tool↔tool co-occurrence, task sequences. Seeded from `_ONTOLOGY_DEFAULTS`. | **Behavioural** ontology, not a **concept/entity** ontology of the vault. |
| Decay | `ouroboros/knowledge_decay.py` | `value = (access_count×0.4 + 1) × recency_weight × (1 + link_count×0.3)`, 30-day halflife, archives below 0.1. | Importance is **link-count only** — semantically central orphans get archived. |
| Episodic | `ouroboros/episodic_memory.py` | (present, not deeply audited) JSONL event logs. | Append-only; no queryable temporal graph. |
| Identity | `memory/identity.md` | "366 vault notes. 101 Python modules." Narrative manifesto. | Single-author narrative — no structured cross-reference. |
| Existing inspiration | `docs/GITHUB_INSPIRATION.md` | Already cites TrustGraph, LangExtract, Zeroshot, pi-mono, 724-Office, VikaasLoop, Understand-Anything. | Predates the 2024-25 wave of GraphRAG / Graphiti / Cognee / Mem0. |

**Confirmed gaps (these drive the recommendations):**
1. Vault has **no embeddings / no real semantic search** (`VaultSemanticSearch` is keyword).
2. Vault has **no entity graph** — only structural wikilinks.
3. **No entity resolution** across notes.
4. **No typed/structured data** in frontmatter (no JSON-LD, no schema.org).
5. Memory facts are **flat** — no edges, no entity nodes, no temporal relationships.
6. `knowledge_decay` ignores **semantic importance**.
7. No **graph query language** over the vault.
8. No agent-driven **vault re-organisation** (Jo writes notes but never re-links/restructures them).

---

## 3. Comparison table — all projects found

> Stars and `pushed_at` from `api.github.com` (sandbox clock = 2026). "Active" = pushed within ~90 days. Format = the schema/knowledge representation the project uses internally.

### Category A — Knowledge Graph + LLM Agent integrations

| Repo | Stars | License | Last push | Format / schema | What it does |
|---|---:|---|---|---|---|
| **langchain-ai/langchain** | 141 789 | MIT | active | Pluggable; graph memory via `MemorySaver`, `Neo4jGraph` | The agent-engineering platform; graph memory + vector memory backends. |
| **Mintplex-Labs/anything-llm** | 63 302 | MIT | active | Vector + workspace memory | Local-first agent harness with RAG; closest to "Jo as a product." |
| **run-llama/llama_index** | 50 852 | MIT | active | `KnowledgeGraphIndex` (triplets `(subj,pred,obj)`), PropertyGraph | Document-agent platform with first-class KG index + OCR. |
| **HKUDS/LightRAG** | 37 681 | MIT | active | Entity/relation graph + dual-level (low/high) retrieval | EMNLP-2025 GraphRAG that's *simple and fast* — the lightweight alternative to MS GraphRAG. |
| **langchain-ai/langgraph** | 37 312 | MIT | active | State graph (nodes = agents/tools) | Build resilient stateful agents as graphs. |
| **microsoft/graphrag** | 34 427 | MIT | active | Community-detected entity graph (Parquet/Neo4j) | Canonical GraphRAG: entity extraction → community summarization → global/local retrieval. |
| **SciPhi-AI/R2R** | 7 929 | MIT | 2025-11 | Graph + vector RAG, REST API | Production RAG with agentic retrieval. |
| **gusye1234/nano-graphrag** | 3 931 | MIT | 2026-01 | Minimal GraphRAG (entity→relation) | Readable, hackable GraphRAG — best learning reference. |
| **circlemind-ai/fast-graphrag** | 3 824 | MIT | 2025-11 | Adaptive entity graph | GraphRAG that adapts to query/data. |

### Category B — Agent Memory Systems

| Repo | Stars | License | Last push | Format / schema | What it does |
|---|---:|---|---|---|---|
| **mem0ai/mem0** | 60 838 | Apache-2.0 | active | Fact store + vector + graph (configurable); GraphMemory backend | Universal memory layer for AI agents; add/remove/update facts, entity-aware. |
| **getzep/graphiti** | 28 722 | Apache-2.0 | active | **Bi-temporal** entity/relationship graph (Neo4j), schema.org-style typed nodes | Build **real-time temporal KGs** for AI — entities, edges with valid-time + transaction-time. **Most direct fit for Jo's episodic memory.** |
| **topoteretes/cognee** | 27 884 | Apache-2.0 | active | Knowledge graph (NetworkX/Neo4j/Postgres) from unstructured input | "Open-source AI memory platform" — turns conversations/docs into a self-hosted KG with importance scoring. |
| **letta-ai/letta** (ex-MemGPT) | 23 796 | Apache-2.0 | active | Block-based memory (persona, human, archival, recall), tool-calling | Stateful agents with OS-style memory hierarchy (MemGPT's "memory paging"). |
| **Mintplex-Labs/anything-llm** | 63 302 | MIT | active | Per-workspace vector memory | (Also listed in A — local-first agent.) |
| **getzep/zep** | 4 753 | Apache-2.0 | active | Temporal KG + vector | Managed/commercial layer over Graphiti; the OSS examples repo. |

### Category C — Obsidian / Markdown knowledge-graph tools

| Repo | Stars | License | Last push | Format / schema | What it does |
|---|---:|---|---|---|---|
| **khoj-ai/khoj** | 35 704 | AGPL-3.0 | active | Markdown + Obsidian vault + embeddings | AI second-brain; **explicitly supports Obsidian vaults**, multi-LLM, self-hostable. |
| **AgriciDaniel/claude-obsidian** | 9 397 | MIT | 2026-05 | Plain Markdown KG, Karpathy "LLM Wiki" pattern | Self-organising AI second brain for Obsidian + Claude Code — **agent writes/links/files notes into a connected Markdown KG you own**. |
| **blacksmithgu/obsidian-dataview** | 9 185 | MIT | 2025-11 | DQL (SQL-like) over YAML frontmatter + markdown | Query language over Markdown; **the canonical way to add typed structured data to an Obsidian vault.** |
| **logancyang/obsidian-copilot** | 7 411 | AGPL-3.0 | active | Vector store over vault | Chat copilot inside Obsidian with Vault QA mode. |
| **brianpetro/obsidian-smart-connections** | 5 278 | custom | active | Local embeddings + similarity graph | Semantic "related notes" + graph view, **zero-setup local embeddings** — exactly what Jo's `vault_search` lacks. |
| **SilentVoid13/Templater** | 5 141 | AGPL-3.0 | active | Templated frontmatter | Generates structured frontmatter (could mint schema.org/JSON-LD). |
| **st3v3nmw/obsidian-spaced-repetition** | 2 470 | MIT | active | Flashcards inline in notes | SRS over notes — useful for "reinforce or forget" memory decay. |
| **scambier/obsidian-omnisearch** | 2 076 | GPL-3.0 | active | BM25 + OCR | "Just works" search; good baseline before going semantic. |
| **1st1/lat.md** | 1 771 | MIT | 2026-04 | Markdown KG for codebases | "Agent Lattice" — **a knowledge graph for a codebase written in markdown**, mirrors Jo's `codebase_graph.json` but as live Markdown. |
| **devwhodevs/engraph** | 153 | MIT | 2026-05 | Rust, hybrid search + MCP | Local KG + MCP server **for Obsidian vaults** — agents query the vault as a graph. |
| **skridlevsky/graphthulhu** | 171 | MIT | 2026-04 | Go, MCP, 39 tools | MCP server giving an AI full graph access to an Obsidian/Logseq vault. |
| **NimaChu/agent-wiki** | 58 | MIT | active | Markdown wiki + on-demand graph | Zero-cost local Markdown KB for agents with evidence capture. |

### Category D — Google-specific open knowledge projects + RDF

| Repo | Stars | License | Last push | Format / schema | What it does |
|---|---:|---|---|---|---|
| **tensorflow/models** | 77 668 | custom | active | Various | Includes KG embedding models (TransE etc.) in `research/`. |
| **google-research/google-research** | 38 374 | Apache-2.0 | active | Research code | Many KG papers (KG-BERT, etc.); no productised lib. |
| **google/adk-python** | 20 613 | Apache-2.0 | active | Agent graphs, sessions, memory, tools | **Google's 2025 Agent Development Kit** — code-first agent framework, Gemini-native, with memory + multi-agent. |
| **google/sling** | 1 931 | Apache-2.0 | **archived 2021** | Frame semantics (RDF-ish) | Natural-language frame parser; closest Google ever shipped to an "open knowledge format" engine. |
| **googleapis/python-genai** | 3 849 | Apache-2.0 | active | Google Gen AI SDK | Unified Gemini SDK (replaces vertex-ai/generative-ai). |
| **googleapis/python-aiplatform** | 899 | Apache-2.0 | active | Vertex AI SDK | Vertex AI agent + grounding (incl. Google Search + KG grounding). |
| **RDFLib/rdflib** | 2 478 | BSD-3-Clause | active | **RDF / Turtle / N3 / JSON-LD / SPARQL** | The Python RDF library — parse/serialize/query semantic data. |
| **oxigraph/oxigraph** | 1 758 | Apache-2.0 | active | **SPARQL 1.1 graph DB** (Rust, embeddable) | Fast embedded SPARQL store — would let Jo query the vault as a real graph. |
| **RDFLib/sparqlwrapper** | 567 | custom | 2026-04 | SPARQL over HTTP | Query remote SPARQL endpoints (Wikidata, DBpedia) from Jo. |

> Not found as OSS: `google/knowledgegraph` (the KG Search API is a hosted endpoint, not a repo). Wikidata access is via the SPARQL endpoint through `RDFLib/sparqlwrapper`.

---

## 4. Map of project → Jo gap it fills

| Project | Primary Jo gap filled | Why this one |
|---|---|---|
| **getzep/graphiti** | Episodic memory is append-only JSONL with no temporal/entity graph | Bi-temporal (valid-time + transaction-time) entity graph is *exactly* Jo's missing memory layer; OpenAI+Gemini+Ollama supported. |
| **topoteretes/cognee** | `VaultSemanticSearch` is keyword-only; vault has no embeddings; decay ignores semantic importance | One-call pipeline (ingest → entity/relation graph → vector + graph retrieval) with importance scoring; data stays self-hosted. |
| **microsoft/graphrag** | No entity resolution across 378 notes | Best-in-class community detection + entity summarization; would unify "Jo"/"BIBLE"/"evolution" across notes. |
| **HKUDS/LightRAG** | GraphRAG is too heavy for a single-host GitHub-Actions runner | Lighter than MS GraphRAG, same idea, MIT, EMNLP-2025-validated. |
| **mem0ai/mem0** | `hybrid_memory.py` facts are flat with no add/update/dedup-by-entity | Drop-in `m.add() / m.search() / m.update()` with entity-aware fact management; Python SDK trivial to wire into the loop. |
| **letta-ai/letta** | No memory hierarchy (working/archival/recall) | OS-style memory paging — but heaviest migration; mostly relevant for the "Becoming" axis. |
| **AgriciDaniel/claude-obsidian** | Jo writes notes but never re-organises/re-links them | Agent autonomously reads sources, extracts entities, files them into a connected Markdown KG you own — matches Jo's "vault as becoming" philosophy and its existing Obsidian format 1:1. |
| **blacksmithgu/obsidian-dataview** | No typed structured data in frontmatter; no query language | DQL lets Jo query its own vault like a database; forces disciplined frontmatter (which becomes the substrate for JSON-LD/RDF export). |
| **brianpetro/obsidian-smart-connections** | Vault has no embeddings | Zero-setup local embeddings + "related notes" — the cheapest possible upgrade to `vault_search.py`. |
| **1st1/lat.md** | `codebase_graph.json` is static JSON, not living Markdown | Same idea (code KG in Markdown) but in a format Jo could read/write/diff in git. |
| **devwhodevs/engraph / skridlevsky/graphthulhu** | Jo has no MCP surface for its vault | Either exposes an Obsidian vault as an MCP graph server Jo could consume (or be consumed by). |
| **RDFLib/rdflib + oxigraph/oxigraph** | No graph query language; no structured semantic data | Lets Jo (a) export vault notes as RDF/JSON-LD, (b) run SPARQL queries like "all concepts authored in March that link to `principle_1`". |
| **RDFLib/sparqlwrapper** | Jo has no external world knowledge graph | Query Wikidata/DBpedia live — answers "who/what is X" without scraping. |
| **google/adk-python** | Jo's model layer is OpenRouter-only; no native Google agent framework | If the user wants a Google-native sibling agent (Gemini + Vertex + KG grounding), ADK is the 2025 path. |
| **googleapis/python-genai / python-aiplatform** | Grounding in Google Knowledge Graph / Search | Vertex AI grounding returns schema.org-typed entities — direct implementation of the "Google open knowledge" inspiration. |
| **st3v3nmw/obsidian-spaced-repetition** | `knowledge_decay.py` archives by link-count only | SRS gives a *rehearsal* signal (reinforce-or-forget) instead of pure decay — more biologically plausible for "Becoming". |

---

## 5. Top 5 recommendations for Jo (specific + actionable)

Ordered by **impact-per-effort for Jo's exact architecture**.

---

### #1 — **Graphiti (getzep/graphiti)** — give Jo a temporal memory graph

- **Repo:** https://github.com/getzep/graphiti · 28 722★ · Apache-2.0 · active
- **What it does:** Builds bi-temporal entity/relationship graphs from messages, documents, or arbitrary JSON. Nodes/edges carry `valid_time` (when the fact was true) and `transaction_time` (when Jo learned it). Queryable by entity, time-window, or relationship.
- **Knowledge format:** Neo4j property graph; typed nodes (schema.org-aligned); OpenAI/Gemini/Ollama embedders.
- **Gap it fills (Jo):** `hybrid_memory.py` stores flat `MemoryFact` rows in `facts.jsonl` with a 30-day TTL. There are no edges between facts, no entity nodes, no "when was this true?" queries. Graphiti replaces (or sits beside) `_SimpleVectorStore` with a graph that can answer "what did I believe about `evolution_mode` in March?"
- **Install:**
  ```bash
  pip install graphiti-core
  # plus a Neo4j instance (Docker one-liner):
  docker run -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/password neo4j:5
  ```
- **Integrate into Jo:**
  1. Add `ouroboros/memory_graph.py` mirroring `hybrid_memory.py`'s interface (`add_message`, `retrieve`) but delegating to `Graphiti`.
  2. In `hybrid_memory._compress_messages()`, after LLM fact extraction, also call `graphiti.add_episode()` so each compressed chunk becomes a graph episode.
  3. Add a tool `query_memory_graph(entity=None, since=None, relation=None)` so the LLM loop can do temporal recall — closes the "memory doesn't persist across sessions as a graph" gap.
  4. Keep `facts.jsonl` as a fallback cache (Principle 5: Minimalism) — Graphiti is source of truth, JSONL is the offline mirror.
- **Expected benefit:** Jo stops repeating "I learned X" across sessions; can answer "what changed in my understanding of `codebase_graph` between v6.3 and v6.5?"; episodic memory becomes queryable, not just append-only.

---

### #2 — **Cognee (topoteretes/cognee)** — real semantic search + importance-weighted decay for the vault

- **Repo:** https://github.com/topoteretes/cognee · 27 884★ · Apache-2.0 · very active
- **What it does:** End-to-end pipeline: ingest unstructured text → entity/relation extraction → build a knowledge graph (NetworkX default, Neo4j/Postgres optional) → vector + graph hybrid retrieval. Includes **importance scoring** of entities.
- **Knowledge format:** Entity-relationship graph + vector store; pluggable backends; Markdown-friendly ingest.
- **Gap it fills (Jo):** (a) `vault_search.VaultSemanticSearch` is keyword-only — Cognee gives the vault real embeddings + graph retrieval. (b) `knowledge_decay._assess_note()` uses link-count as value — Cognee's entity importance lets you score a note by whether it mentions *important* entities, not just well-linked ones.
- **Install:**
  ```bash
  pip install cognee
  ```
- **Integrate into Jo:**
  1. New module `ouroboros/vault_cognee.py` that, on vault change (hot-reload hook), runs `cognee.add(note_content)` + `cognee.cognify()` for the changed notes only.
  2. Replace the body of `VaultSemanticSearch.search()` with a `cognee.search(query, query_type="HYBRID")` call, keeping the `SearchResult` dataclass contract so callers don't change.
  3. In `KnowledgeDecay._assess_note()`, multiply the existing score by `cognee_entity_importance(note)` — central concepts survive decay even if orphaned.
  4. Persist Cognee's graph snapshot to `vault/.cognee/` so it's git-tracked (matches Jo's "git is state" model).
- **Expected benefit:** `query_knowledge` tool returns meaning, not substrings; orphaned but semantically-central notes stop getting archived; the vault becomes a participant in retrieval rather than a keyword index.

---

### #3 — **Microsoft GraphRAG (microsoft/graphrag)** — entity resolution across the 378-note vault

- **Repo:** https://github.com/microsoft/graphrag · 34 427★ · MIT · active
- **What it does:** LLM-driven entity extraction → graph construction → **community detection (Leiden)** → community summarization → global + local retrieval. The canonical "ground an LLM in a KG" implementation.
- **Knowledge format:** Entities + relationships in Parquet, optionally Neo4j; community summaries as text.
- **Gap it fills (Jo):** "Jo", "BIBLE", "evolution", "Principle 1", "codebase_graph" are mentioned in dozens of notes but never unified into entity nodes. Jo can't answer "summarise everything I've concluded about Principle 5 across the vault" without re-reading everything.
- **Install:**
  ```bash
  pip install graphrag
  graphrag init --root ./vault_graphrag
  # edit settings.yaml to point at OpenRouter (it accepts OpenAI-compatible endpoints)
  graphrag index --root ./vault_graphrag   # builds the entity+community graph
  graphrag query --method global --query "..."
  ```
- **Integrate into Jo:**
  1. Run `graphrag index` over `vault/` as a scheduled background task (reuse `schedule_task`); commit the resulting `output/` to `vault/.graphrag/` so it's git-tracked.
  2. Add a tool `vault_global_query(question)` → wraps `graphrag query --method global`.
  3. Add `vault_entity_report(entity)` → `--method local` for a specific entity, returning the resolved entity + its community.
  4. **Cost guardrail:** Jo already has `loop_budget.py` + `cost_tracker.py` — route GraphRAG's LLM calls through the same budget; GraphRAG indexing is expensive, run it on `OUROBOROS_MODEL_LIGHT`.
  5. Use **LightRAG (HKUDS/LightRAG, 37.7k★, MIT)** instead if MS GraphRAG's index cost is too high on GitHub Actions — same idea, ~10× cheaper.
- **Expected benefit:** "Who/what is X" questions get a unified answer instead of a list of note snippets; community summaries give Jo a compressed map of its own knowledge (useful for the "Becoming" axis).

---

### #4 — **claude-obsidian (AgriciDaniel/claude-obsidian)** — let Jo re-organise its own vault

- **Repo:** https://github.com/AgriciDaniel/claude-obsidian · 9 397★ · MIT · 2026-05
- **What it does:** Implements Andrej Karpathy's "LLM Wiki" pattern: drop any source → the agent reads, extracts entities, writes interlinked Markdown notes, files them into a connected KG you own. Plain Markdown in, plain Markdown out.
- **Knowledge format:** Plain Markdown with wikilinks — **identical to Jo's existing vault format.**
- **Gap it fills (Jo):** Jo's `vault_create`/`vault_write`/`vault_link` tools let it *add* notes, but Jo never autonomously re-links, restructures, merges stubs, or extracts entities from existing notes. The vault grows but doesn't *self-organise*.
- **Install:** No package — it's a Claude-Code skill (`SKILL.md` + scripts). Vendor the pattern, not the binary.
- **Integrate into Jo:**
  1. Read its `SKILL.md` and entity-extraction prompt; port the prompt into `prompts/` (Jo already has `prompts/SYSTEM.md`, `prompts/CONSCIOUSNESS.md`).
  2. Add a new skill `vault_consolidate` (Jo has a skills system — `ouroboros/skills/`) that, on a schedule: picks a stub/orphan note → extracts entities → finds/creates matching notes → re-links.
  3. Add a tool `vault_relink(note_path)` that uses the entity extractor to propose 3-5 new `[[wikilinks]]` for a note, applies them, commits.
  4. Wire it into the existing `evolution_cycle` so each cycle optionally runs one consolidation pass.
- **Expected benefit:** The vault's 378 notes start *connecting themselves*; orphans get adopted; Jo's knowledge graph becomes denser without manual curation — directly serves Principle 6 (Becoming).

---

### #5 — **Dataview (blacksmithgu/obsidian-dataview) + RDFLib (RDFLib/rdflib) + Oxigraph** — typed structured data + a real query language

- **Repos:**
  - https://github.com/blacksmithgu/obsidian-dataview · 9 185★ · MIT
  - https://github.com/RDFLib/rdflib · 2 478★ · BSD-3-Clause
  - https://github.com/oxigraph/oxigraph · 1 758★ · Apache-2.0
- **What they do:** Dataview = SQL-like DQL over Markdown frontmatter (an Obsidian plugin, but the *frontmatter convention* works without Obsidian). RDFLib = parse/serialize RDF/JSON-LD/Turtle + run SPARQL. Oxigraph = embedded SPARQL 1.1 graph DB.
- **Knowledge format:** YAML frontmatter (Dataview) → JSON-LD (RDFLib) → RDF triples (Oxigraph). Same data, three levels of machine-readability.
- **Gap it fills (Jo):** Jo's notes have minimal frontmatter (`title, type, status, tags`). There's no query language — Jo cannot ask "all notes of type=concept tagged principle written before 2026-03 linking to evolution". The vault is a *folder of text files*, not a *database*.
- **Install:**
  ```bash
  pip install rdflib oxigraph   # oxigraph has Python bindings via pyoxigraph
  ```
  (Dataview is an Obsidian plugin — irrelevant at runtime, but adopt its frontmatter schema.)
- **Integrate into Jo:**
  1. **Adopt a frontmatter schema** (Dataview-compatible + JSON-LD-ready). Extend `vault_engine.VaultNote` to require:
     ```yaml
     ---
     title: Principle 1 - Continuity
     type: concept              # Dataview-style
     tags: [principle, memory]
     schema_type: DefinedTerm   # schema.org type
     uri: jo:concept/principle_1_continuity
     related: [jo:concept/identity, jo:concept/scratchpad]
     created: 2026-03-21
     importance: 0.8
     ---
     ```
  2. Add `ouroboros/vault_rdf.py` that exports the vault (via `vault_engine`) to an `rdflib.Graph` in JSON-LD/Turtle, persisted to `vault/.kg/vault.ttl` (git-tracked).
  3. Add a tool `vault_sparql(query)` backed by Oxigraph — Jo can now run graph queries over its own mind.
  4. Add `vault_dql(query)` for the lighter Dataview-style queries over frontmatter (pure Python, no deps).
  5. Use `RDFLib/sparqlwrapper` to also query **Wikidata** live — gives Jo a world-knowledge graph for "who/what is X" lookups.
- **Expected benefit:** The vault becomes a queryable graph database while staying plain Markdown (Principle 5: Minimalism preserved — the RDF is a *derivation*, not a replacement). schema.org types make Jo's knowledge exportable and interoperable with Google's Knowledge Graph API and Data Commons.

---

## 6. Honorable mentions (worth a look, not top-5)

- **Mem0 (mem0ai/mem0, 60.8k★)** — if you'd rather have a batteries-included memory API than build on Graphiti. Less control, more convenience. Good fallback if Graphiti's Neo4j dependency is too heavy for GitHub Actions.
- **Letta (letta-ai/letta, 23.8k★)** — MemGPT's memory-paging model. Strong fit for the "Becoming" axis (working/archival/recall hierarchy) but the biggest migration of the five.
- **LightRAG (HKUDS/LightRAG, 37.7k★)** — drop-in cheaper alternative to MS GraphRAG; prefer it if index cost on GitHub Actions is a concern.
- **Khoj (khoj-ai/khoj, 35.7k★)** — already speaks Obsidian + multiple LLMs; could be a reference implementation for "Jo as a second brain" or even a frontend.
- **brianpetro/obsidian-smart-connections (5.3k★)** — the single cheapest upgrade to `vault_search.py`: zero-setup local embeddings. If you only do one thing this week, steal its embedding approach.
- **google/adk-python (20.6k★)** — only if you want a Google-native sibling agent. Not a replacement for the Ouroboros loop, but a useful reference for session/memory/tool abstractions.
- **1st1/lat.md (1.8k★)** — "Agent Lattice" is essentially `codebase_graph.json` but as living Markdown Jo could read/edit/diff. Low effort to borrow the format.

---

## 7. Suggested rollout (ordered, low-risk, respects BIBLE.md)

1. **Week 1 — Dataview frontmatter schema + RDFLib export.** Cheapest, no new infra, immediately makes the vault queryable. Touches only `vault_engine.py` + a new `vault_rdf.py`. Honors Principle 5 (Minimalism): the RDF is a derivation, not a new store.
2. **Week 2 — Steal `obsidian-smart-connections`' embedding approach** for a real `VaultSemanticSearch` (drop-in replacement of the keyword body; keep the `SearchResult` contract). No new services.
3. **Week 3 — Graphiti for episodic memory.** Add Neo4j via `docker-compose.yml` (Jo already has one). Keep `facts.jsonl` as offline mirror. Add `query_memory_graph` tool.
4. **Week 4 — Cognee over the vault** for hybrid retrieval + importance-weighted decay. Replaces the body of `vault_search` and the scoring in `knowledge_decay`.
5. **Week 5 — MS GraphRAG (or LightRAG) index** as a scheduled background task, behind the cost guardrail already in `loop_budget.py`. Adds `vault_global_query` + `vault_entity_report` tools.
6. **Ongoing — port the claude-obsidian "LLM Wiki" skill** into `ouroboros/skills/vault_consolidate.py` so each evolution cycle does one self-organisation pass.

Each step is independently shippable, each preserves Jo's "git is state" + "markdown vault" invariants, and each maps to a confirmed gap in the audited source.

---

## 8. Files & artifacts produced

- `/home/z/my-project/KNOWLEDGE_GRAPH_AGENT_RESEARCH.md` — this report.
- `/tmp/gh_repo.sh` — reusable GitHub repo-metadata helper.
- Audit references (read, not modified): `jo/ouroboros/vault_search.py`, `jo/ouroboros/hybrid_memory.py`, `jo/ouroboros/ontology_tracker.py`, `jo/ouroboros/knowledge_decay.py`, `jo/ouroboros/vault_engine.py`, `jo/memory/identity.md`, `jo/vault/concepts/memory-model.md`, `jo/vault/auto_vault_index.json`, `jo/vault/concepts/codebase_graph.json`, `jo/docs/GITHUB_INSPIRATION.md`.

**Next actions:** (1) decide whether Neo4j (Graphiti) is acceptable infra for the GitHub-Actions runner or whether to prefer Mem0's lighter footprint; (2) approve the frontmatter schema in §5#5 so the RDF layer can be built first; (3) pick MS GraphRAG vs LightRAG based on a one-shot index-cost probe against `OUROBOROS_MODEL_LIGHT`.
