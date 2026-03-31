# Module Health Report

Generated: 2026-03-31T08:41:56.019758

## Summary

- **Critical**: 6 modules
- **Warning**: 18 modules
- **OK**: 89 modules

## Critical Violations

| Module | Lines | Classes | Functions |
|--------|-------|---------|-----------|
| `C:\Users\S\Desktop\jo\ouroboros\loop.py` | 1450 | 0 | 25 |
| `C:\Users\S\Desktop\jo\ouroboros\codebase_graph.py` | 1354 | 5 | 45 |
| `C:\Users\S\Desktop\jo\ouroboros\tools\neural_map.py` | 1209 | 3 | 26 |
| `C:\Users\S\Desktop\jo\ouroboros\context.py` | 1202 | 1 | 29 |
| `C:\Users\S\Desktop\jo\ouroboros\agent.py` | 1190 | 2 | 27 |
| `C:\Users\S\Desktop\jo\ouroboros\tools\evolution_loop.py` | 1028 | 2 | 24 |

## Warnings

| Module | Lines | Classes | Functions |
|--------|-------|---------|-----------|
| `C:\Users\S\Desktop\jo\ouroboros\tools\intelligence_tools.py` | 927 | 0 | 12 |
| `C:\Users\S\Desktop\jo\ouroboros\tools\browser.py` | 888 | 0 | 19 |
| `C:\Users\S\Desktop\jo\ouroboros\tools\web_research.py` | 871 | 3 | 20 |
| `C:\Users\S\Desktop\jo\ouroboros\tools\control.py` | 776 | 0 | 21 |
| `C:\Users\S\Desktop\jo\supervisor\workers.py` | 758 | 1 | 18 |
| `C:\Users\S\Desktop\jo\ouroboros\tools\core.py` | 757 | 0 | 18 |
| `C:\Users\S\Desktop\jo\supervisor\state.py` | 741 | 0 | 24 |
| `C:\Users\S\Desktop\jo\ouroboros\consciousness.py` | 711 | 1 | 19 |
| `C:\Users\S\Desktop\jo\ouroboros\tools\connection_weavers.py` | 676 | 0 | 11 |
| `C:\Users\S\Desktop\jo\ouroboros\tools\skill_registry.py` | 670 | 0 | 9 |
| `C:\Users\S\Desktop\jo\ouroboros\vault_improvements.py` | 664 | 7 | 19 |
| `C:\Users\S\Desktop\jo\ouroboros\response_analyzer.py` | 612 | 3 | 16 |
| `C:\Users\S\Desktop\jo\ouroboros\vault_manager.py` | 578 | 1 | 34 |
| `C:\Users\S\Desktop\jo\ouroboros\eval.py` | 569 | 4 | 15 |
| `C:\Users\S\Desktop\jo\ouroboros\vault_engine.py` | 539 | 4 | 25 |
| `C:\Users\S\Desktop\jo\ouroboros\extraction.py` | 536 | 3 | 15 |
| `C:\Users\S\Desktop\jo\supervisor\queue.py` | 528 | 0 | 17 |
| `C:\Users\S\Desktop\jo\ouroboros\tools\vault.py` | 519 | 0 | 18 |

## Decomposition Suggestions

### `C:\Users\S\Desktop\jo\ouroboros\loop.py` (1450 lines)

- Extract 6 functions (262 lines) with prefix '_handle_' -> loop_handle.py
- Module is 950 lines over soft limit. Extract ~950 lines to submodules.

### `C:\Users\S\Desktop\jo\ouroboros\codebase_graph.py` (1354 lines)

- Consider extracting class 'GraphNode' -> codebase_graph_graphnode.py
- Consider extracting class 'GraphEdge' -> codebase_graph_graphedge.py
- Consider extracting class 'CodebaseGraph' -> codebase_graph_codebasegraph.py
- Consider extracting class 'OntologyTracker' -> codebase_graph_ontologytracker.py
- Consider extracting class 'CallVisitor' -> codebase_graph_callvisitor.py
- Module is 854 lines over soft limit. Extract ~854 lines to submodules.

### `C:\Users\S\Desktop\jo\ouroboros\tools\neural_map.py` (1209 lines)

- Extract 3 functions (118 lines) with prefix '_scan_' -> neural_map_scan.py
- Consider extracting class 'Concept' -> neural_map_concept.py
- Consider extracting class 'Connection' -> neural_map_connection.py
- Consider extracting class 'NeuralMap' -> neural_map_neuralmap.py
- Module is 709 lines over soft limit. Extract ~709 lines to submodules.

### `C:\Users\S\Desktop\jo\ouroboros\context.py` (1202 lines)

- Extract 8 functions (231 lines) with prefix '_build_' -> context_build.py
- Extract 3 functions (111 lines) with prefix '_compact_' -> context_compact.py
- Consider extracting class 'DifferentialContext' -> context_differentialcontext.py
- Module is 702 lines over soft limit. Extract ~702 lines to submodules.

### `C:\Users\S\Desktop\jo\ouroboros\agent.py` (1190 lines)

- Extract 4 functions (159 lines) with prefix '_emit_' -> agent_emit.py
- Extract 3 functions (177 lines) with prefix '_check_' -> agent_check.py
- Consider extracting class 'Env' -> agent_env.py
- Consider extracting class 'OuroborosAgent' -> agent_ouroborosagent.py
- Module is 690 lines over soft limit. Extract ~690 lines to submodules.

### `C:\Users\S\Desktop\jo\ouroboros\tools\evolution_loop.py` (1028 lines)

- Extract 5 functions (134 lines) with prefix '_check_' -> evolution_loop_check.py
- Consider extracting class 'EvolutionCycle' -> evolution_loop_evolutioncycle.py
- Consider extracting class 'EvolutionLoop' -> evolution_loop_evolutionloop.py
- Module is 528 lines over soft limit. Extract ~528 lines to submodules.

### `C:\Users\S\Desktop\jo\ouroboros\tools\intelligence_tools.py` (927 lines)

- Extract 4 functions (271 lines) with prefix '_get_' -> intelligence_tools_get.py

### `C:\Users\S\Desktop\jo\ouroboros\tools\browser.py` (888 lines)

- Extract 5 functions (224 lines) with prefix '_browser_' -> browser_browser.py

### `C:\Users\S\Desktop\jo\ouroboros\tools\web_research.py` (871 lines)

- Extract 4 functions (144 lines) with prefix '_search_' -> web_research_search.py
- Consider extracting class 'SearchResult' -> web_research_searchresult.py
- Consider extracting class 'ResearchSource' -> web_research_researchsource.py
- Consider extracting class 'ResearchResult' -> web_research_researchresult.py

### `C:\Users\S\Desktop\jo\supervisor\workers.py` (758 lines)

- Consider extracting class 'Worker' -> workers_worker.py

### `C:\Users\S\Desktop\jo\ouroboros\consciousness.py` (711 lines)

- Consider extracting class 'BackgroundConsciousness' -> consciousness_backgroundconsciousness.py

### `C:\Users\S\Desktop\jo\ouroboros\vault_improvements.py` (664 lines)

- Consider extracting class 'LinkSuggestion' -> vault_improvements_linksuggestion.py
- Consider extracting class 'QualityViolation' -> vault_improvements_qualityviolation.py
- Consider extracting class 'VaultHealthReport' -> vault_improvements_vaulthealthreport.py
- Consider extracting class 'VaultGuardrails' -> vault_improvements_vaultguardrails.py
- Consider extracting class 'VaultAutoLinker' -> vault_improvements_vaultautolinker.py
- Consider extracting class 'ImprovementResult' -> vault_improvements_improvementresult.py
- Consider extracting class 'VaultAutoFixer' -> vault_improvements_vaultautofixer.py

### `C:\Users\S\Desktop\jo\ouroboros\response_analyzer.py` (612 lines)

- Extract 4 functions (274 lines) with prefix '_detect_' -> response_analyzer_detect.py
- Extract 3 functions (138 lines) with prefix '_verify_' -> response_analyzer_verify.py
- Consider extracting class 'QualityIssue' -> response_analyzer_qualityissue.py
- Consider extracting class 'ResponseAnalysis' -> response_analyzer_responseanalysis.py
- Consider extracting class 'ResponseAnalyzer' -> response_analyzer_responseanalyzer.py

### `C:\Users\S\Desktop\jo\ouroboros\vault_manager.py` (578 lines)

- Consider extracting class 'VaultManager' -> vault_manager_vaultmanager.py

### `C:\Users\S\Desktop\jo\ouroboros\eval.py` (569 lines)

- Extract 5 functions (199 lines) with prefix '_eval_' -> eval_eval.py
- Consider extracting class 'EvalResult' -> eval_evalresult.py
- Consider extracting class 'EvalReport' -> eval_evalreport.py
- Consider extracting class 'TaskEvaluator' -> eval_taskevaluator.py
- Consider extracting class 'BlindValidationResult' -> eval_blindvalidationresult.py

### `C:\Users\S\Desktop\jo\ouroboros\vault_engine.py` (539 lines)

- Consider extracting class 'VaultNote' -> vault_engine_vaultnote.py
- Consider extracting class 'VaultGraph' -> vault_engine_vaultgraph.py
- Consider extracting class 'QualityMetrics' -> vault_engine_qualitymetrics.py
- Consider extracting class 'VaultGraphEngine' -> vault_engine_vaultgraphengine.py

### `C:\Users\S\Desktop\jo\ouroboros\extraction.py` (536 lines)

- Consider extracting class 'Extraction' -> extraction_extraction.py
- Consider extracting class 'ExampleData' -> extraction_exampledata.py
- Consider extracting class 'ExtractionResult' -> extraction_extractionresult.py

### `C:\Users\S\Desktop\jo\ouroboros\tools\vault.py` (519 lines)

- Extract 15 functions (209 lines) with prefix '_vault_' -> vault_vault.py

## Circular Import Chains

- `ouroboros.tools.neural_map -> ouroboros.knowledge_discovery -> ouroboros.tools.neural_map`
- `ouroboros.traceability -> ouroboros.tools.vault -> ouroboros.tools.git -> ouroboros.traceability`
- `ouroboros.traceability -> ouroboros.tools.control -> ouroboros.traceability`

## All Modules

| Module | Lines | Status |
|--------|-------|--------|
| `C:\Users\S\Desktop\jo\ouroboros\loop.py` | 1450 | 🔴 CRITICAL |
| `C:\Users\S\Desktop\jo\ouroboros\codebase_graph.py` | 1354 | 🔴 CRITICAL |
| `C:\Users\S\Desktop\jo\ouroboros\tools\neural_map.py` | 1209 | 🔴 CRITICAL |
| `C:\Users\S\Desktop\jo\ouroboros\context.py` | 1202 | 🔴 CRITICAL |
| `C:\Users\S\Desktop\jo\ouroboros\agent.py` | 1190 | 🔴 CRITICAL |
| `C:\Users\S\Desktop\jo\ouroboros\tools\evolution_loop.py` | 1028 | 🔴 CRITICAL |
| `C:\Users\S\Desktop\jo\ouroboros\tools\intelligence_tools.py` | 927 | 🟡 WARNING |
| `C:\Users\S\Desktop\jo\ouroboros\tools\browser.py` | 888 | 🟡 WARNING |
| `C:\Users\S\Desktop\jo\ouroboros\tools\web_research.py` | 871 | 🟡 WARNING |
| `C:\Users\S\Desktop\jo\ouroboros\tools\control.py` | 776 | 🟡 WARNING |
| `C:\Users\S\Desktop\jo\supervisor\workers.py` | 758 | 🟡 WARNING |
| `C:\Users\S\Desktop\jo\ouroboros\tools\core.py` | 757 | 🟡 WARNING |
| `C:\Users\S\Desktop\jo\supervisor\state.py` | 741 | 🟡 WARNING |
| `C:\Users\S\Desktop\jo\ouroboros\consciousness.py` | 711 | 🟡 WARNING |
| `C:\Users\S\Desktop\jo\ouroboros\tools\connection_weavers.py` | 676 | 🟡 WARNING |
| `C:\Users\S\Desktop\jo\ouroboros\tools\skill_registry.py` | 670 | 🟡 WARNING |
| `C:\Users\S\Desktop\jo\ouroboros\vault_improvements.py` | 664 | 🟡 WARNING |
| `C:\Users\S\Desktop\jo\ouroboros\response_analyzer.py` | 612 | 🟡 WARNING |
| `C:\Users\S\Desktop\jo\ouroboros\vault_manager.py` | 578 | 🟡 WARNING |
| `C:\Users\S\Desktop\jo\ouroboros\eval.py` | 569 | 🟡 WARNING |
| `C:\Users\S\Desktop\jo\ouroboros\vault_engine.py` | 539 | 🟡 WARNING |
| `C:\Users\S\Desktop\jo\ouroboros\extraction.py` | 536 | 🟡 WARNING |
| `C:\Users\S\Desktop\jo\supervisor\queue.py` | 528 | 🟡 WARNING |
| `C:\Users\S\Desktop\jo\ouroboros\tools\vault.py` | 519 | 🟡 WARNING |
| `C:\Users\S\Desktop\jo\ouroboros\memory.py` | 488 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\hybrid_memory.py` | 480 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\agent_coordinator.py` | 479 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\loop\budget.py` | 477 | 🟢 OK |
| `C:\Users\S\Desktop\jo\supervisor\telegram.py` | 477 | 🟢 OK |
| `C:\Users\S\Desktop\jo\supervisor\events.py` | 467 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tool_executor.py` | 462 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\ai_code.py` | 462 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\llm.py` | 450 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\vault_search.py` | 445 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\dspy_integration.py` | 443 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\simulation.py` | 423 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\dashboard.py` | 413 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\file_ops.py` | 407 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\dspy_tools.py` | 402 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\system_map.py` | 379 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\synthesis.py` | 377 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\runtime_tool_creator.py` | 373 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\context_enricher.py` | 366 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\shell.py` | 358 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\health_invariants.py` | 356 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\pi_prompts.py` | 350 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\utils.py` | 348 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\request_tools.py` | 347 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\embedding_simple.py` | 341 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\hot_reload.py` | 338 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\cli_anything.py` | 338 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\git.py` | 325 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\pipeline.py` | 316 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\knowledge.py` | 315 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\knowledge_discovery.py` | 314 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\config_manager.py` | 310 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\evolution_strategy.py` | 308 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\database.py` | 307 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\vault_flow_tool.py` | 297 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\drift_detector.py` | 292 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\normalizer.py` | 289 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\registry.py` | 288 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\skill_selection.py` | 280 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\traceability.py` | 277 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\health_auto_fix.py` | 276 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\review.py` | 275 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tool_router.py` | 273 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\evolution_proposal.py` | 271 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\evolution_fingerprint.py` | 269 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\github.py` | 266 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\task_graph.py` | 250 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\spice.py` | 249 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\instinct_evolver.py` | 246 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\checkpoint.py` | 244 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\skill_logging.py` | 244 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\evolution_stats.py` | 242 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\health_predictor.py` | 241 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\awareness.py` | 240 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\episodic_memory.py` | 239 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\delta_eval.py` | 236 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\temporal_learning.py` | 232 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\cost_tracker.py` | 231 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\vault_parser.py` | 229 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\vault_models.py` | 218 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\decision_trace.py` | 216 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\knowledge_decay.py` | 214 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\proof_gate.py` | 213 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\confidence.py` | 209 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\review.py` | 200 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\context_cache.py` | 198 | 🟢 OK |
| `C:\Users\S\Desktop\jo\supervisor\git_ops.py` | 197 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\vision.py` | 194 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\mcp_server.py` | 188 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\embedding_tool.py` | 188 | 🟢 OK |
| `C:\Users\S\Desktop\jo\supervisor\watchdog.py` | 183 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\apply_patch.py` | 178 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\runtime_tools.py` | 153 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\auto_system.py` | 130 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\tool_discovery.py` | 128 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\experience_indexer.py` | 108 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\owner_inject.py` | 103 | 🟢 OK |
| `C:\Users\S\Desktop\jo\supervisor\github_api.py` | 102 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\memory_consolidator.py` | 95 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\health.py` | 83 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\compact_context.py` | 80 | 🟢 OK |
| `C:\Users\S\Desktop\jo\supervisor\health_reporter.py` | 77 | 🟢 OK |
| `C:\Users\S\Desktop\jo\supervisor\sys_ops.py` | 59 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\skill_definitions.py` | 56 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\experience_search.py` | 55 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\skills.py` | 50 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\search.py` | 46 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\vault.py` | 19 | 🟢 OK |
| `C:\Users\S\Desktop\jo\supervisor\states.py` | 16 | 🟢 OK |