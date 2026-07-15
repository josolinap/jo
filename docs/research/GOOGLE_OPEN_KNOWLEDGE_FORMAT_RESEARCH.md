# Google "Open Knowledge Format" & Knowledge-Representation Initiatives — Technical Analysis

**Prepared for:** the Jo autonomous agent (Ouroboros), to drive architectural decisions about the Vault.
**Method:** direct live fetches of authoritative documentation (developers.google.com, cloud.google.com, schema.org, docs.datacommons.org, okfn.org, PyPI, arXiv API) + audit of Jo's actual source (`ouroboros/vault_models.py`, `ouroboros/vault_parser.py`, `vault/concepts/identity.md`). Sandbox clock reads 2026; "active" verdicts are relative to that.
**Companion file:** `KNOWLEDGE_GRAPH_AGENT_RESEARCH.md` (the OSS-landscape scan). This document is the **Google-specific deep-dive** complement.

---

## 0. Executive summary (TL;DR)

1. **There is no single Google product/spec literally named "Open Knowledge Format" (OKF).** "OKF" as an acronym belongs to the **Open Knowledge Foundation** (okfn.org) — a UK non-profit, *not* Google. The phrase "Google's Open Knowledge Format" is an umbrella for Google's cluster of open knowledge-representation efforts.

2. The **four real candidates** behind that umbrella, in order of relevance:
   - **schema.org + JSON-LD** — the actual *open vocabulary + format* Google co-created. This is the most defensible interpretation of an "open knowledge format" from Google. (v30.0, March 2026 — very active.)
   - **Google Data Commons** — Google's explicitly-named **"open knowledge graph,"** with its own human-writable **MCF (Meta Content Framework)** format, open-source tooling, and a 2025-era **MCP server for AI agents**.
   - **Google Knowledge Graph Search API** — read-only JSON-LD endpoint that *returns* schema.org-typed entities. Google itself says: for interconnected graphs "use data dumps from **Wikidata** instead."
   - **Wikidata / Wikibase** — not Google, but the *de facto* open knowledge graph that Google's own docs point to and that powers Knowledge Panels.

3. **Historical root:** all of the above descend from **MCF (Meta Content Framework, 1997)** by **R.V.Guha** (Netscape → Apple → Google), who later **initiated schema.org**. MCF → RDF → schema.org/JSON-LD is one continuous lineage. This is the "knowledge format" genealogy.

4. **Recommendation for Jo:** adopt a **two-layer knowledge representation** over the existing Obsidian Vault:
   - **Layer 1 — typed vocabulary: schema.org in JSON-LD**, embedded in markdown frontmatter (`@type`, `@id`, `sameAs`). Gives the Vault typed entities, typed relations, and stable identity.
   - **Layer 2 — LLM-writable memory: an MCF-style property-list dialect**, either in fenced code blocks or sidecar `.mcf` files. MCF is *deliberately designed* to be written by machines and read by humans/LLMs — simpler than full RDF, embeds in markdown, round-trips with JSON-LD.
   - Use **Wikidata Q-IDs / Data Commons DCIDs as `sameAs`** for entity resolution. Use **schema.org's `Action` type** to describe Jo's tools.

---

## 1. The literal term "Open Knowledge Format" / OKF

### 1.1 What it IS
A targeted search for the exact phrase returns **no Google product, spec, or repo**. The acronym **OKF** resolves to the **Open Knowledge Foundation** (okfn.org) — a UK non-profit (founded 2004) that maintains the **Open Definition**, **Frictionless Data / Data Package v2**, the **Open Data Editor (ODE)**, and related open-data tooling. It is **not** a Google initiative.

> Source: okfn.org homepage (fetched live) — "Open Knowledge Foundation – For a fair, sustainable and open future … Open Data Editor (ODE), Sustainable Data Commons, Open Data Day … Updating the Open Definition."

### 1.2 Conclusion on the literal term
"Google's Open Knowledge Format" is almost certainly a **conflation/misremembering** of one or more of:
- **MCF** = *Meta Content Framework* (Guha, 1997) — the "M→O" phonetic/initial slip is plausible;
- **schema.org** = the open *vocabulary*;
- **Data Commons** = Google's *open knowledge graph*;
- The **Open Knowledge Foundation** itself (the OKF acronym).

Throughout the rest of this report, "Google's open knowledge efforts" = the cluster of §2–§8.

---

## 2. Google Knowledge Graph & Knowledge Graph Search API

### What it IS
The **Knowledge Graph** is Google's proprietary, internal knowledge base (announced 2012, "things, not strings") powering Search Knowledge Panels. The public surface is the **Knowledge Graph Search API**, a **read-only** lookup that returns entities matching a query/ID/type. As of 2024–2025 it is being **migrated to Cloud Enterprise Knowledge Graph** (Preview/Pre-GA); Google tells new users to use EKG instead.

### The actual FORMAT — JSON-LD over schema.org (+ Google extension)
`GET https://kgsearch.googleapis.com/v1/entities:search?query=taylor+swift&key=…&limit=1`

Returns **JSON-LD** whose `@context` maps to **schema.org** plus a Google extension namespace (`goog:` → `http://schema.googleapis.com/`):

```json
{
  "@context": {
    "@vocab": "http://schema.org/",
    "goog": "http://schema.googleapis.com/",
    "resultScore": "goog:resultScore",
    "detailedDescription": "goog:detailedDescription",
    "EntitySearchResult": "goog:EntitySearchResult",
    "kg": "http://g.co/kg"
  },
  "@type": "ItemList",
  "itemListElement": [
    {
      "@type": "EntitySearchResult",
      "result": {
        "@id": "kg:/m/0dl567",          // Freebase MID
        "name": "Taylor Swift",
        "@type": ["Thing", "Person"],
        "description": "Singer-songwriter",
        "image": { "contentUrl": "...", "url": "...wikipedia.org/wiki/Taylor_Swift", "license": "CC-BY-SA 2.0" },
        "detailedDescription": { "articleBody": "…", "url": "…wikipedia.org/…", "license": "…" },
        "url": "http://taylorswift.com/"
      },
      "resultScore": 4850
    }
  ]
}
```
> Source: developers.google.com/knowledge-graph (fetched live; the example above is the documented sample response verbatim).

### Is it OPEN?
- **Spec/format:** ✅ open (JSON-LD + schema.org are W3C/open).
- **Data/graph:** ❌ **not open** — the underlying Knowledge Graph is proprietary; no bulk dump.
- **API:** ⚠️ **read-only, free with API key, low quota, "not suitable as a production-critical service," "do not form a critical dependence."**
- **License:** docs CC-BY-4.0, code samples Apache-2.0.
- **Critical caveat (verbatim from Google):** *"The Knowledge Graph Search API returns only individual matching entities, rather than graphs of interconnected entities. If you need the latter, we recommend using data dumps from **Wikidata** instead."*

### SDK / open-source
- Client libraries: Python, Java, Go, Node, PHP, Ruby (linked from the docs). No open-source *engine* — it's a hosted API.

### Use cases (for an agent like Jo)
- **Entity lookup / disambiguation:** map a surface string ("Taylor Swift") to a stable `@id` (`kg:/m/0dl567`) + Wikipedia URL.
- **Grounding a fact** with a `resultScore` (relevance/confidence) and a CC-licensed `articleBody`.
- ❌ **Not** suitable as the agent's own knowledge store (read-only, low quota, no interconnections).

### Activity / last update
API docs page last updated **2026-07-10 UTC** (EKG page). Migrating to EKG. Functionally stable but deprecated-in-spirit.

---

## 3. schema.org — the actual "open knowledge format"

### What it IS
A **collaborative, community vocabulary** of types and properties for structured data on the web, **co-founded by Google, Microsoft, Yahoo and Yandex (2011)**. Run day-to-day by **Dan Brickley (Google)**; **initiated by R.V.Guha (Google)**, who also created MCF (1997) — the direct lineage. Since April 2015 it lives under the **W3C Schema.org Community Group**. **This is the closest thing to "Google's Open Knowledge Format."**

### The actual FORMAT
- **Primary serialization: JSON-LD** (1.0; context published at `https://schema.org/docs/jsonldcontext.json`).
- Also published/exchangeable as **RDF/Turtle, RDFa, N-Triples, JSON-LD, CSV** (downloadable vocab dumps on GitHub `schemaorg/schemaorg`, `data/releases/`).
- The `@context` contains **3 080 terms** (`@vocab: http://schema.org/`, plus prefixes for GS1, Dublin Core, Open Graph, FIBO, etc.).
- **~800+ types, 1 500+ properties**, rooted at `Thing` → `Action`, `Person`, `Place`, `Organization`, `Event`, `CreativeWork`, `Intangible`, `Product`, … with deep subclass hierarchies.
- Exports now include **equivalence annotations** to GS1 / Dublin Core / Open Graph (v30.0, March 2026).

Example (the form Google Search consumes):
```json
{
  "@context": "https://schema.org/",
  "@type": "Person",
  "@id": "https://jo-agent.dev/i/identity",
  "name": "Jo",
  "sameAs": ["https://www.wikidata.org/wiki/Q130407921"],
  "knowsAbout": ["https://schema.org/SoftwareApplication","autonomous agents"],
  "description": "An autonomous agent (Ouroboros)."
}
```

### Is it OPEN?
- ✅ **Fully open.** Vocabulary under permissive terms; data dumps CC0-ish/CC-BY-SA; on GitHub; W3C community-governed; no proprietary extension.
- ✅ **No API key, no quota** — it's a vocabulary, not a service.

### SDK / open-source
- No single SDK, but it's just JSON-LD; consumable by **RDFLib** (Python), **pyld**, **Oxigraph** (Rust/SPARQL), **json-ld** (JS), plus validators (Google Rich Results Test, Schema Markup Validator). The vocabulary itself is versioned on GitHub.

### Use cases (for an agent)
- **Type the Vault's entities** (`Person`, `SoftwareApplication`, `Concept`/`DefinedTerm`, `Action`, `Event`, `Task`).
- **Type the Vault's relations** (`knowsAbout`, `partOf`, `isBasedOn`, `author`, `subjectOf`, `about`, `instrument`).
- **Type the agent's tools** (`Action` subclasses: `SearchAction`, `ReadAction`, `SoftwareApplication`).
- **Interoperate** with Google Search / Dataset Search / KG API (they all speak schema.org).

### Activity / last update
**Release 30.0 — 2026-03-19.** Recent additions: GS1/DCAT/Open Graph equivalence, EU Digital Product Passport, a `Credential` class, an `Error` class. **Very actively maintained.**

---

## 4. Google Data Commons — Google's explicitly "open knowledge graph"

### What it IS
Google's **"open knowledge graph"** combining statistical + factual data from Wikipedia, CIA World Factbook, census bureaus (US, India, Brazil, …), WHO, World Bank, NOAA, etc. Described in its docs as *"a knowledge graph"*, with a data model of **nodes, properties, triples, entities, statistical variables, observations**. Uniquely, it ships **"Build your own Data Commons"** (open-source, Dockerized, SQLite-backed) and an **MCP server for AI agents** (2025-era).

### The actual FORMAT — three layers
Data Commons is a graph whose data model is RDF-style (triples, DCIDs, classes, subClassOf). It exposes **four input/serialization formats**:

**(a) MCF — Meta Content Framework** (the human/LLM-writable node format, `.mcf` files). Property-list syntax, one block per node:
```
Node: dcid:who/Adult_curr_cig_smokers
typeOf: dcid:StatisticalVariable
name: "Prevalence of current cigarette smoking among adults (%)"
populationType: dcid:Person
measuredProperty: dcid:percent
```
Entity-type definition uses RDF-Schema vocabulary:
```
Node: dcid:mystategov/Agency
name: "Government agency"
typeOf: schema:Class
subClassOf: dcs:Government
description: "Agency of a government, such as legal, legislative, …"
```
> Note `schema:Class` and `subClassOf` — MCF is **RDF-Schema expressed in a friendly property-list syntax**, and `schema:` = schema.org. This is the lineage: MCF (1997) → RDF → schema.org → Data Commons MCF.

**(b) CSV** — the observation values (statistical time series), with a defined schema (date, value, unit, measurement method, observation period, …).

**(c) JSON `config.json`** — maps CSV columns + MCF nodes to the graph (entities, variables, facets, provenance).

**(d) API output: JSON** (REST V2), also queryable via **BigQuery (SQL)** and an **MCP server**. Identifiers are **DCIDs** (`geoId/06` = California, `country/IND` = India, `Count_Person` = population).

### Is it OPEN?
- ✅ **Data:** open (graph data openly browsable; BigQuery public dataset).
- ✅ **Engine:** **open-source** — "Build your own Data Commons" (Docker, SQLite, Terraform to GCS); Python package `datacommons` on PyPI (**v1.4.4, Apache-2.0**, home `github.com/datacommonsorg/api-python`).
- ✅ **API:** free, but **requires an API key** (apikeys.datacommons.org). Verified live: unauthenticated `GET /v2/node` → `401 UNAUTHENTICATED`.
- ✅ **Docs:** CC-BY-4.0.
- ⚠️ The hosted graph at datacommons.org is a Google-operated service; the *software* to run your own is open.

### SDK / open-source
- Python: `pip install datacommons` (v1.4.4).
- REST V2, MCP server, BigQuery, Sheets add-on.
- GitHub org: `datacommonsorg` (api-python, documentation, mix-n-match components).

### Use cases (for an agent)
- **Structured factual/statistical grounding** (populations, GDP, geography) with **provenance + facets** (multiple sources, measurement methods).
- **Entity resolution** via DCIDs and the `resolve` endpoint.
- **Agent-native:** the **MCP server** lets an LLM agent query the graph interactively — directly relevant to Jo's tool/MCP architecture (`ouroboros/mcp_server.py`).
- **Self-hostable:** Jo could run a local Custom Data Commons over its *own* vault facts.

### Activity / last update
Docs heavily updated through 2025–2026 (MCP server, REST V2, Python V2 tutorials). **Very active.** One of Google's most agent-relevant open projects.

---

## 5. Vertex AI Search / Generative AI "Knowledge Foundation" (Gemini Enterprise Agent Platform)

### What it IS
Google Cloud's managed **grounding + RAG** stack for LLMs, rebranded several times: **Vertex AI Search** → **Vertex AI Agent Builder** → (2025) **"Gemini Enterprise Agent Platform."** It is *not* a knowledge-graph format — it is a **retrieval-and-grounding service**: connect an LLM to verifiable sources so output is anchored and hallucinations drop.

### The actual FORMAT
- **No open knowledge-graph format.** Internally: **document chunks + vector embeddings** in a managed vector store; optional structured-data stores; Knowledge Graph *connectors* (not a format).
- Grounding responses return **support/citations** (URI + chunk text), not triples.
- Grounding "types" offered (verbatim from docs): **Google Search, Google Maps, Agent Search (RAG on your docs/site), RAG Engine, Elasticsearch, your own search API, Web Grounding for Enterprise, Parallel web search.**

### Is it OPEN?
- ❌ **Not open.** Proprietary Google Cloud product; pay-per-use; no open-source engine.
- ✅ Docs CC-BY-4.0, code samples Apache-2.0.

### SDK / open-source
- Cloud client libraries (Python, Node, Java, …) + gRPC/REST. No OSS engine.

### Use cases (for an agent)
- **Production RAG grounding** for an enterprise Jo deployment.
- **Cited/auditable answers** (support links).
- ❌ Not a candidate for Jo's *local* Vault representation — it's a hosted retrieval service, not a knowledge format.

### Activity / last update
Rebranded to "Gemini Enterprise Agent Platform" in 2025; docs updated 2026-07-10. **Active but closed.**

---

## 6. Google Open Buildings / Open Data / Dataset Search

### What it IS
- **Open Buildings** — a large-scale **open geospatial dataset** (1.8B building footprints, 58M km², Africa/Global South, v3). Per-building: polygon + confidence + Plus Code. **Open dataset, not a knowledge graph.**
- **Dataset Search** — a Google search tool that finds datasets across the web by reading **schema.org `Dataset` / `DataCatalog` / `DataDownload`** JSON-LD markup on dataset pages. Confirms schema.org is *the* format Google uses for open-data discovery.
- **Google open data** generally is published as downloadable files (GeoJSON/CSV/Shapefile on Cloud Storage / Earth Engine) plus schema.org markup.

### The actual FORMAT
- Open Buildings: **GeoJSON / CSV / Shapefile** (geometry + attributes). Plain open geodata.
- Dataset Search: **schema.org JSON-LD** (`Dataset` type with `name`, `creator`, `distribution`, `temporalCoverage`, `spatialCoverage`, `license`, …).

### Is it OPEN?
- ✅ **Open Buildings:** open dataset (CC-BY-4.0), freely downloadable.
- ✅ **Dataset Search:** free; uses open schema.org vocabulary.

### SDK / open-source
- Open Buildings: downloadable from Cloud Storage / Earth Engine; no SDK needed (standard GIS formats).

### Use cases (for an agent)
- Geospatial grounding (e.g., "how many buildings in region X") — niche for Jo.
- **Dataset Search as a tool:** Jo could emit a schema.org `Dataset` query to discover open datasets — relevant only if Jo does data science.

### Activity / last update
Open Buildings v3 (2023–2024); Dataset Search ongoing. **Maintained, but peripheral to a knowledge-format decision.**

---

## 7. Wikidata / Wikibase — the *de facto* open knowledge graph

### What it IS
**Wikidata** is the Wikimedia Foundation's **open, multi-lingual knowledge graph** (100M+ items) — the practical standard for open machine-readable world knowledge. **Wikibase** is its open-source software (run your own). Google's own Knowledge Graph API docs point users here for "graphs of interconnected entities," and Google Knowledge Panels draw heavily on Wikidata/Wikipedia.

### The actual FORMAT — three serializations
**(a) Wikibase JSON model** (the canonical API form): each Item (Q-id) has `labels`, `descriptions`, `aliases`, `claims` (statements = `property (P-id)` → `value`, each with **qualifiers**, **references**, and a **rank**: preferred/normal/deprecated), and `sitelinks`.
**(b) RDF export** — `Special:EntityData/Q42.ttl|.rdf|.nt|.jsonld` (RDF/Turtle, RDF/XML, N-Triples, JSON-LD). Wikidata's RDF maps P-properties to `wdt:`/`p:`/`ps:`/`pq:`/`prov:` IRIs.
**(c) SPARQL** — `query.wikidata.org/sparql` (full SPARQL 1.1 endpoint, JSON/CSV/XML out).

```
wd:Q42  wdt:P31  wd:Q5 ;          # instance of: human
        wdt:P19  wd:Q350 ;        # place of birth: Cambridge
        rdfs:label "Douglas Adams"@en .
```

### Is it OPEN?
- ✅ **Data: CC0** (public domain) — the whole graph is free to use.
- ✅ **Software: Wikibase (GPL)** — run your own.
- ✅ **API/dumps: free**, full weekly RDF/JSON dumps.

### SDK / open-source
- `Wikibase` (PHP/JS), `wikidata` Python helpers, `SPARQLWrapper`, `rdflib`, `pyshex`, `qwikidata`. Massive tooling ecosystem.

### How Google uses it
- KG API docs explicitly recommend Wikidata for interconnected graphs (see §2 quote).
- Google's Knowledge Panels are sourced substantially from Wikidata/Wikipedia.
- Data Commons integrates/cross-links Wikidata.

### Use cases (for an agent)
- **Entity resolution** via stable Q-IDs and `sameAs`.
- **Factual grounding** with provenance/references and temporal validity (ranks).
- **Agent memory as a local Wikibase** — fully self-hostable, SPARQL-queryable, bi-temporal-ish (via qualifiers). This is arguably the most mature "open knowledge graph" stack available.

### Activity / last update
100M+ items, daily edits, active WMF development. **Extremely active.**

---

## 8. Google's recent (2024–2025) "Knowledge Compact" / knowledge-base-for-LLMs research

### What it IS
There is **no single Google paper titled "Open Knowledge Format" or "Knowledge Compact."** But there is an **active research wave** on structured/compact knowledge for LLMs and agents. A live arXiv API search (sorted by recency) for *"knowledge base" + LLM + agent* returned, among others (2024–2026):

- **"Progressive Disclosure for LLM-Maintained Wiki Knowledge Bases"** (arXiv 2607.04576) — LLMs curating wiki KBs with staged disclosure.
- **"Scaling Expert Feedback with Reflective Edit Propagation in Compositional Knowledge Bases"** (2606.05023) — human-in-the-loop KB editing.
- **"Kintsugi: Learning Policies by Repairing Executable Knowledge Bases"** (2605.09487) — KBs as executable, repairable artefacts.
- **"AgenticRAG: Agentic Retrieval for Enterprise Knowledge Bases"** (2605.05538) — agent-driven RAG over KBs.
- **"Joint Knowledge Base Completion and Question Answering by Combining LLMs and Small LMs"** (2604.05875) — hybrid KB completion + QA.
- **"Architecture Matters: Comparing RAG Systems under Knowledge Base Poisoning"** (2605.05632) — KB robustness.

> arXiv rate-limited some queries; the above were returned from the successful query. No result was specifically a Google-authored "open knowledge format" spec.

### Google-side relevant lines of work (not a single paper)
- **Gemini + grounding** (§5) — Google's production answer to "ground LLMs in structured knowledge."
- **Data Commons MCP** (§4) — Google's explicit "query a knowledge graph with an AI agent" surface.
- **google/adk-python** (Agent Development Kit, ~20.6k★, very active, per the companion file) — Google's 2025 agent framework with built-in memory + tool abstractions.
- **Google SLING** (`google/sling`, ~1.9k★, **archived 2021**) — frame-semantics KB parser; the closest Google ever shipped to an "open knowledge format *engine*" as OSS, now dormant.

### Use cases / verdict
The research trend is clear: **structured, editable, provenance-tracked knowledge bases maintained by/for LLM agents** are a first-class 2024–2026 topic. None of it invents a new "open knowledge format" — they all build on **triples/RDF, JSON-LD/schema.org, or property-list (MCF-like) representations**. The format question is settled; the open problems are *maintenance, disclosure, and repair* of such KBs by agents.

---

## 9. Synthesis — what the user means, and what Jo should adopt

### 9.1 Which is "Google's Open Knowledge Format"?
**No literal product by that name exists.** Ranked by likelihood of intent:

| Rank | Candidate | Why it's the "open knowledge format" |
|---:|---|---|
| 1 | **schema.org + JSON-LD** | The actual open *vocabulary + serialization* Google co-created; the format every Google knowledge surface (Search, KG API, Dataset Search) speaks. |
| 2 | **Google Data Commons (MCF)** | Google's only product literally called an **"open knowledge graph,"** with its own **named format (MCF)** that is LLM-writable. Closest match to "format." |
| 3 | **Knowledge Graph Search API (JSON-LD output)** | Returns open-formatted entities, but is a read-only API, not a format you author in. |
| 4 | **MCF (1997, Guha)** | The historical root; if "OKF" was a mishearing of "MCF," this is it. |
| 5 | **Wikidata (CC0)** | What Google *points to* for open interconnected graphs; not Google's, but the de facto standard. |

**Bottom line:** if forced to name *the* "Google Open Knowledge Format," the most defensible answer is **"schema.org serialized as JSON-LD"** — with **Data Commons' MCF** as Google's native *authoring* format and **Wikidata** as the open *data* layer.

### 9.2 Which format is most useful for an autonomous agent (Jo) with a Vault, tools, memory, and LLM reasoning?

**Recommendation: a two-layer representation, not a single format.**

**Layer A — schema.org JSON-LD as the typed vocabulary layer** (embedded in Vault frontmatter). This gives the Vault what it lacks today: **typed entities and typed relations**.

Jo's current state (audited in `vault_models.py` / `vault_parser.py`):
- `VaultNote.frontmatter: Dict[str, Any]` — **untyped YAML** (e.g., `identity.md` has `type: concept`, `status: active`, `tags: [identity, manifesto]` — free strings, not linked to any schema).
- `VaultGraph.links / backlinks: Dict[str, Set[str]]` — **untyped note→note edges only**. `find_path()` does BFS over these bare links.
- `WikilinkParser` parses `[[Note]]`, `[[Note#Heading]]`, `[[Note|Display]]`, `[[Note#^block]]` — Obsidian-native, but **relations carry no semantics**.

Proposed frontmatter upgrade (back-compatible with what Jo already parses):
```yaml
---
title: Identity
created: 2026-03-30T02:25:42+00:00
modified: 2026-04-02T12:07:05+00:00
type: concept
status: active
tags: [identity, manifesto]
# --- NEW: schema.org JSON-LD entity block ---
jsonld:
  "@context": "https://schema.org/"
  "@type": ["DefinedTerm", "Concept"]          # schema.org type for a concept
  "@id": "jo://concept/identity"
  "name": "Identity"
  "sameAs":
    - "https://www.wikidata.org/wiki/Q130407921"   # cross-ref for resolution
  "isPartOf": "jo://vault"
  "about": ["jo://concept/agency", "jo://concept/continuity"]
---
```
Wikilinks get a typed companion. Instead of relying solely on `[[Continuity]]`, Jo can emit a **typed edge** (a `json-ld` relation in a sidecar or a `[[Continuity|rel=partOf]]` micro-syntax the parser already partially supports via the `|display` field):
- `jo://concept/identity` `schema:isPartOf` `jo://vault`
- `jo://concept/identity` `schema:about` `jo://concept/agency`

This is **exactly the gap** the companion file flags: *"No typed/structured data in vault frontmatter (no JSON-LD, no schema.org)."*

**Layer B — an MCF-style property-list dialect as the LLM-writable memory/scratch format.** MCF is *purpose-built* to be authored by machines and read by humans, and it embeds trivially in markdown fenced blocks. For Jo's `hybrid_memory.py` facts (currently a **flat** `MemoryFact{fact, keywords, persons, topic, session_key, vector}` with no edges), an MCF-style fact store adds **typed edges, entity nodes, and provenance** without the verbosity of full RDF:

````
```mcf
Node: jo://fact/always_git_status
typeOf: jo:MemoryFact
name: "Always check git status before committing"
statement: "Run `git status` before any commit."
confidence: 0.93
provenance: ["jo://session/2026-05-09", "jo://lesson/task_77456aaa"]
subject: jo://concept/git_workflow
object: jo://concept/versioning
relation: schema:requires
recordedAt: 2026-05-09T11:02:00Z
```
````

Why MCF over raw JSON-LD for memory:
- **Line-oriented, diff-friendly** (git tracks changes line-by-line — critical for Jo's git-synced Vault).
- **LLMs write it reliably** (no bracket/quote-balancing failures of nested JSON).
- **Round-trips to JSON-LD/RDF** (Data Commons itself compiles MCF → triples; the same compiler logic applies).
- **Provenance/confidence are first-class** (`provenance:`, `confidence:`) — matching Jo's existing `confidence.py` and `proof_gate.py` machinery.

**Layer C (identity/resolution) — Wikidata Q-IDs / Data Commons DCIDs as `sameAs`.**
- For *world* entities Jo encounters, resolve to a Wikidata Q-ID (`sameAs`) once, reuse everywhere → kills the "Jo/BIBLE/evolution scattered across 50 notes" entity-resolution gap.
- For *statistical/geographic* facts, a DCID gives a stable, queryable handle (and Jo can hit the Data Commons MCP server as a tool).

### 9.3 Specific gaps this fills in Jo's architecture (mapped to audited code)

| # | Audited Jo gap (file) | What the format adds |
|---|---|---|
| 1 | Vault has **no typed entities** — `VaultNote.frontmatter` is untyped YAML (`vault_models.py`) | schema.org `@type` in frontmatter → queryable, typed concept ontology |
| 2 | Vault graph has **only untyped link edges** — `VaultGraph.links/backlinks` (`vault_models.py`) | schema.org relation properties (`partOf`, `about`, `isBasedOn`, `author`) → semantic edges |
| 3 | **No entity resolution** — "Jo"/"BIBLE"/"evolution" never unify across 378 notes | `@id` (jo://…) + `sameAs` (Wikidata Q-ID) → single canonical identity per entity |
| 4 | Memory facts are **flat**, no edges (`hybrid_memory.py` `MemoryFact`) | MCF nodes with `subject/relation/object` → a real fact graph, not a list |
| 5 | `knowledge_decay.py` scores value from **link count only** | `confidence` + `provenance` + `lastUsed` fields → semantic importance, not just popularity |
| 6 | **No graph query language** over the Vault | JSON-LD → load into **Oxigraph/RDFLib** → SPARQL ("all concepts `about` Principle 1 that `partOf` evolution") |
| 7 | No **typed tool descriptions** aligned to a vocabulary | schema.org `Action` subclasses (`SearchAction`, `ReadAction`) type Jo's 50+ tools (`ouroboros/tools/*`) |
| 8 | Memory is append-only JSONL, **no temporal validity** | MCF `recordedAt`/`validUntil` + Wikidata-style ranks (preferred/normal/deprecated) → bi-temporal memory |
| 9 | Agent never **re-organizes** the Vault (`auto_vault.py` exists but weak) | Typed graph enables agent-driven re-linking: detect orphans by `@type`/`sameAs`, propose typed links |
| 10 | No **external grounding** with provenance | KG API `resultScore` + Data Commons `facet/provenance` → auditable, cited facts |

### 9.4 Pragmatic adoption path (lowest-risk first)
1. **Add an optional `jsonld:` block to frontmatter** — zero disruption to `vault_parser.py` (it already extracts arbitrary YAML). One new validator in `vault_engine.py`.
2. **Emit a `.mcf` sidecar** for `hybrid_memory.py` facts (start with new facts only). Write a 60-line MCF↔JSON-LD converter in `ouroboros/`.
3. **Add a `wikidata_sameas` resolver tool** that calls the Wikidata REST API / SPARQL to mint Q-IDs for new world entities.
4. **Stand up Oxigraph** (embedded Rust SPARQL store, pip-installable `pyoxigraph`) over the union of frontmatter JSON-LD + MCF facts → first real **graph queries** over the Vault.
5. **(Optional) run a local Custom Data Commons** instance for Jo's own statistical/structured facts — reuse Google's open engine rather than rebuilding.

---

## 10. One-page comparison matrix

| Initiative | Format | Truly open? | OSS impl/SDK | Best use for Jo | Activity |
|---|---|---|---|---|---|
| **"Open Knowledge Format" (literal)** | n/a — does not exist | — | — | — | — |
| **OKF (the acronym)** | Open Definition / Data Package v2 (UK NGO, not Google) | ✅ | ✅ | peripheral | active |
| **Knowledge Graph Search API** | JSON-LD (schema.org + `goog:` ext) | format ✅; data ❌; API read-only/low-quota | client libs (no engine) | entity lookup/disambiguation | migrating to EKG; 2026-07 docs |
| **schema.org** | **JSON-LD** (primary); RDF/Turtle/N-Triples/CSV | ✅ fully | RDFLib, pyld, Oxigraph, validators | **typed Vault vocabulary + relations** | **v30.0 (2026-03); very active** |
| **Data Commons** | **MCF** (nodes) + CSV + JSON config; API=JSON; BigQuery=SQL; MCP | ✅ data + ✅ OSS engine; API needs key | `pip install datacommons` (Apache-2.0); self-host Docker | **LLM-writable memory format; MCP agent grounding; self-hostable** | very active (MCP, REST V2) |
| **Vertex AI / Gen AI Knowledge Foundation** | vector chunks + citations (no KG format) | ❌ closed | cloud SDKs only | production RAG grounding (hosted) | rebranded 2025; active |
| **Open Buildings / Dataset Search** | GeoJSON/CSV/Shapefile; schema.org `Dataset` JSON-LD | ✅ | downloads | geospatial grounding; dataset discovery | maintained; peripheral |
| **Wikidata / Wikibase** | Wikibase JSON + RDF (Turtle/JSON-LD/NT) + SPARQL | ✅ CC0 data + GPL software | Wikibase, RDFLib, SPARQLWrapper, pyoxigraph | **entity resolution (Q-IDs); local KB engine; SPARQL** | extremely active (100M+ items) |
| **MCF (1997, Guha)** | property-list node format | ✅ spec (W3C NOTE) | historical; revived inside Data Commons | **the LLM-writable memory dialect** | spec frozen; live via Data Commons |
| **google/sling** | frame-semantics KB | ✅ OSS | repo **archived 2021** | (dormant) | **dead** |
| **google/adk-python** | agent memory + tool abstractions (not a KG format) | ✅ Apache-2.0 | ~20.6k★, very active | Google-native agent framework if leaning on Gemini | active (2025) |

---

## 11. Key citations (live-fetched)

- **Knowledge Graph Search API** (overview + JSON-LD sample response): https://developers.google.com/knowledge-graph — *"uses standard schema.org types and is compliant with the JSON-LD specification"*; *"returns only individual matching entities … we recommend using data dumps from Wikidata instead."*
- **Knowledge Graph API reference**: https://developers.google.com/knowledge-graph/reference/rest/v1 — `GET https://kgsearch.googleapis.com/v1/entities:search`; returns JSON-LD `ItemList`/`EntitySearchResult`.
- **Cloud Enterprise Knowledge Graph** (successor, Preview): https://cloud.google.com/enterprise-knowledge-graph/docs — "organizes siloed information into organizational knowledge"; entity reconciliation jobs; docs CC-BY-4.0.
- **schema.org** vocabulary + governance: https://schema.org/docs/about.html — founded by Google, Microsoft, Yahoo, Yandex; R.V.Guha initiated it; Dan Brickley runs daily ops; W3C Community Group since 2015.
- **schema.org full hierarchy**: https://schema.org/docs/full.html — Thing-rooted, ~800+ types.
- **schema.org JSON-LD context**: https://schema.org/docs/jsonldcontext.json — 3 080 `@context` terms, `@vocab: http://schema.org/`.
- **schema.org releases**: https://schema.org/docs/releases.html — **v30.0 (2026-03-19)**; GS1/DCAT/Open Graph equivalence; EU Digital Product Passport.
- **schema.org downloads** (RDF/Turtle/NT/CSV/JSON-LD): https://schema.org/docs/developers.html — `data/releases/` on GitHub.
- **Data Commons REST API V2**: https://docs.datacommons.org/api/rest/v2 — REST library, JSON out, DCIDs, relation expressions, pagination; requires API key.
- **Data Commons glossary/model**: https://docs.datacommons.org/glossary.html — entities, statistical variables, observations, **Triples**, **Properties**, **DCIDs**, **Provenance**, **Facets**.
- **Data Commons custom data (MCF + CSV + config.json)**: https://docs.datacommons.org/custom_dc/custom_data.html — MCF syntax example (`Node:`/`typeOf`/`name`/`populationType`/`measuredProperty`).
- **Data Commons custom entities (MCF for classes)**: https://docs.datacommons.org/custom_dc/custom_entities.html — `typeOf: schema:Class`, `subClassOf:` (RDF-Schema in MCF).
- **Data Commons "Build your own"** (open-source, Docker, SQLite, MCP): https://docs.datacommons.org/custom_dc/index.html
- **Data Commons Python SDK**: https://pypi.org/pypi/datacommons/json — v1.4.4, Apache-2.0, `github.com/datacommonsorg/api-python`.
- **Vertex AI / Gemini Enterprise Agent Platform — Grounding**: https://cloud.google.com/vertex-ai/generative-ai/docs/grounding/overview — grounding types (Google Search, Maps, Agent Search/RAG, RAG Engine, Elasticsearch, custom search API, Web Grounding, Parallel web search).
- **Google Search structured data intro** (JSON-LD is the format): https://developers.google.com/search/docs/appearance/structured-data/intro-structured-data
- **Dataset structured data** (schema.org `Dataset`/`DataCatalog`/`DataDownload`): https://developers.google.com/search/docs/data-types/datasets
- **Open Buildings**: https://sites.research.google/open-buildings/ — 1.8B footprints, v3, open dataset.
- **Open Knowledge Foundation (the real "OKF")**: https://okfn.org/ — Open Definition, Frictionless Data/Data Package v2, Open Data Editor.
- **Wikidata RDF/SPARQL model**: https://www.wikidata.org/wiki/Wikidata:Introduction ; https://query.wikidata.org/ ; `Special:EntityData/Q42.{ttl,rdf,nt,jsonld}` (live fetch was rate-limited from the sandbox IP; endpoints are authoritative).
- **arXiv search** (knowledge-base + LLM + agent, recent): http://export.arxiv.org/api/ — Progressive Disclosure (2607.04576), Reflective Edit Propagation (2606.05023), Kintsugi (2605.09487), AgenticRAG (2605.05538), Joint KB Completion+QA (2604.05875), KB Poisoning (2605.05632).
- **Jo source audit**: `ouroboros/vault_models.py` (`VaultNote`, `VaultGraph` — untyped links), `ouroboros/vault_parser.py` (`WikilinkParser` — `[[Note]]`, frontmatter YAML), `vault/concepts/identity.md` (sample untyped frontmatter).

---

## 12. Final recommendation (one paragraph)

**"Google's Open Knowledge Format" is best understood as schema.org-in-JSON-LD (the open vocabulary Google co-created), with Data Commons' MCF as Google's native authoring dialect and Wikidata as the open data layer.** For Jo, adopt a **two-layer representation**: (1) embed **schema.org JSON-LD** in Vault frontmatter (`@type`, `@id`, `sameAs`, typed relation properties) to upgrade today's untyped YAML + bare wikilinks into a typed, queryable concept graph; (2) store **LLM-authored memory facts in an MCF-style property-list dialect** (line-oriented, git-diff-friendly, provenance/confidence first-class) that round-trips to JSON-LD/RDF and plugs into Jo's existing `confidence.py`/`proof_gate.py`. Resolve world entities to **Wikidata Q-IDs / Data Commons DCIDs** via `sameAs`. Stand up **pyoxigraph** for SPARQL over the union store. This closes the eight audited gaps (no typed entities/relations, no entity resolution, flat memory, link-count-only decay, no graph query language, untyped tools, no temporal validity, no agent-driven re-linking) using **only open, Google-aligned, agent-native formats** — and reuses Google's own open Data Commons engine if Jo ever needs a self-hosted statistical KB.
