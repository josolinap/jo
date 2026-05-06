# Module Health Report

Generated: 2026-05-06T10:09:55.747104

## Summary

- **Critical**: 4 modules
- **Warning**: 26 modules
- **OK**: 207 modules

## Critical Violations

| Module | Lines | Classes | Functions |
|--------|-------|---------|-----------|
| `C:\Users\S\Desktop\jo\ouroboros\tools\consciousness_tools.py` | 1272 | 0 | 58 |
| `C:\Users\S\Desktop\jo\ouroboros\agent.py` | 1232 | 2 | 27 |
| `C:\Users\S\Desktop\jo\ouroboros\loop.py` | 1146 | 0 | 14 |
| `C:\Users\S\Desktop\jo\ouroboros\tools\intelligence_tools.py` | 1051 | 0 | 14 |

## Warnings

| Module | Lines | Classes | Functions |
|--------|-------|---------|-----------|
| `C:\Users\S\Desktop\jo\ouroboros\context.py` | 947 | 1 | 23 |
| `C:\Users\S\Desktop\jo\ouroboros\tools\browser.py` | 888 | 0 | 19 |
| `C:\Users\S\Desktop\jo\ouroboros\tools\web_research.py` | 871 | 3 | 20 |
| `C:\Users\S\Desktop\jo\ouroboros\llm.py` | 854 | 3 | 32 |
| `C:\Users\S\Desktop\jo\ouroboros\tools\skills_tools.py` | 810 | 0 | 36 |
| `C:\Users\S\Desktop\jo\ouroboros\tools\control.py` | 776 | 0 | 21 |
| `C:\Users\S\Desktop\jo\supervisor\workers.py` | 771 | 1 | 18 |
| `C:\Users\S\Desktop\jo\ouroboros\tools\core.py` | 763 | 0 | 18 |
| `C:\Users\S\Desktop\jo\supervisor\state.py` | 742 | 0 | 24 |
| `C:\Users\S\Desktop\jo\ouroboros\consciousness.py` | 711 | 1 | 19 |
| `C:\Users\S\Desktop\jo\ouroboros\tools\connection_weavers.py` | 676 | 0 | 11 |
| `C:\Users\S\Desktop\jo\ouroboros\tools\skill_registry.py` | 670 | 0 | 9 |
| `C:\Users\S\Desktop\jo\ouroboros\vault_improvements.py` | 664 | 7 | 19 |
| `C:\Users\S\Desktop\jo\ouroboros\tools\neural_map.py` | 649 | 0 | 11 |
| `C:\Users\S\Desktop\jo\ouroboros\health_invariants.py` | 627 | 0 | 2 |
| `C:\Users\S\Desktop\jo\ouroboros\tools\evolution_loop.py` | 614 | 2 | 12 |
| `C:\Users\S\Desktop\jo\ouroboros\response_analyzer.py` | 612 | 3 | 16 |
| `C:\Users\S\Desktop\jo\ouroboros\tool_executor.py` | 583 | 1 | 12 |
| `C:\Users\S\Desktop\jo\ouroboros\vault_manager.py` | 578 | 1 | 34 |
| `C:\Users\S\Desktop\jo\ouroboros\eval.py` | 569 | 4 | 15 |
| `C:\Users\S\Desktop\jo\ouroboros\vault_engine.py` | 539 | 4 | 25 |
| `C:\Users\S\Desktop\jo\ouroboros\extraction.py` | 536 | 3 | 15 |
| `C:\Users\S\Desktop\jo\supervisor\queue.py` | 528 | 0 | 17 |
| `C:\Users\S\Desktop\jo\supervisor\telegram.py` | 528 | 1 | 23 |
| `C:\Users\S\Desktop\jo\ouroboros\tools\vault.py` | 527 | 0 | 18 |
| `C:\Users\S\Desktop\jo\ouroboros\skills\pulse_supervisor.py` | 509 | 5 | 22 |

## Decomposition Suggestions

### `C:\Users\S\Desktop\jo\ouroboros\tools\consciousness_tools.py` (1272 lines)

- Module is 772 lines over soft limit. Extract ~772 lines to submodules.

### `C:\Users\S\Desktop\jo\ouroboros\agent.py` (1232 lines)

- Extract 4 functions (171 lines) with prefix '_emit_' -> agent_emit.py
- Extract 3 functions (179 lines) with prefix '_check_' -> agent_check.py
- Consider extracting class 'Env' -> agent_env.py
- Consider extracting class 'OuroborosAgent' -> agent_ouroborosagent.py
- Module is 732 lines over soft limit. Extract ~732 lines to submodules.

### `C:\Users\S\Desktop\jo\ouroboros\loop.py` (1146 lines)

- Module is 646 lines over soft limit. Extract ~646 lines to submodules.

### `C:\Users\S\Desktop\jo\ouroboros\tools\intelligence_tools.py` (1051 lines)

- Extract 4 functions (271 lines) with prefix '_get_' -> intelligence_tools_get.py
- Module is 551 lines over soft limit. Extract ~551 lines to submodules.

### `C:\Users\S\Desktop\jo\ouroboros\context.py` (947 lines)

- Extract 9 functions (250 lines) with prefix '_build_' -> context_build.py
- Consider extracting class 'DifferentialContext' -> context_differentialcontext.py

### `C:\Users\S\Desktop\jo\ouroboros\tools\browser.py` (888 lines)

- Extract 5 functions (224 lines) with prefix '_browser_' -> browser_browser.py

### `C:\Users\S\Desktop\jo\ouroboros\tools\web_research.py` (871 lines)

- Extract 4 functions (144 lines) with prefix '_search_' -> web_research_search.py
- Consider extracting class 'SearchResult' -> web_research_searchresult.py
- Consider extracting class 'ResearchSource' -> web_research_researchsource.py
- Consider extracting class 'ResearchResult' -> web_research_researchresult.py

### `C:\Users\S\Desktop\jo\ouroboros\llm.py` (854 lines)

- Extract 3 functions (227 lines) with prefix 'other' -> llm_other.py
- Consider extracting class 'NvidiaLLMClient' -> llm_nvidiallmclient.py
- Consider extracting class 'LocalLLMClient' -> llm_localllmclient.py
- Consider extracting class 'LLMClient' -> llm_llmclient.py

### `C:\Users\S\Desktop\jo\supervisor\workers.py` (771 lines)

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

### `C:\Users\S\Desktop\jo\ouroboros\tools\evolution_loop.py` (614 lines)

- Consider extracting class 'EvolutionCycle' -> evolution_loop_evolutioncycle.py
- Consider extracting class 'EvolutionLoop' -> evolution_loop_evolutionloop.py

### `C:\Users\S\Desktop\jo\ouroboros\response_analyzer.py` (612 lines)

- Extract 4 functions (274 lines) with prefix '_detect_' -> response_analyzer_detect.py
- Extract 3 functions (138 lines) with prefix '_verify_' -> response_analyzer_verify.py
- Consider extracting class 'QualityIssue' -> response_analyzer_qualityissue.py
- Consider extracting class 'ResponseAnalysis' -> response_analyzer_responseanalysis.py
- Consider extracting class 'ResponseAnalyzer' -> response_analyzer_responseanalyzer.py

### `C:\Users\S\Desktop\jo\ouroboros\tool_executor.py` (583 lines)

- Consider extracting class '_StatefulToolExecutor' -> tool_executor__statefultoolexecutor.py

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

### `C:\Users\S\Desktop\jo\supervisor\telegram.py` (528 lines)

- Consider extracting class 'TelegramClient' -> telegram_telegramclient.py

### `C:\Users\S\Desktop\jo\ouroboros\tools\vault.py` (527 lines)

- Extract 15 functions (209 lines) with prefix '_vault_' -> vault_vault.py

### `C:\Users\S\Desktop\jo\ouroboros\skills\pulse_supervisor.py` (509 lines)

- Consider extracting class 'PulseState' -> pulse_supervisor_pulsestate.py
- Consider extracting class 'PulseConfig' -> pulse_supervisor_pulseconfig.py
- Consider extracting class 'PulseMetrics' -> pulse_supervisor_pulsemetrics.py
- Consider extracting class 'Mission' -> pulse_supervisor_mission.py
- Consider extracting class 'PulseSupervisor' -> pulse_supervisor_pulsesupervisor.py

## Circular Import Chains

- `ouroboros.health_invariants -> ouroboros.modification_pipeline -> ouroboros.health_invariants`
- `ouroboros.context -> ouroboros.health_invariants -> ouroboros.modification_pipeline -> ouroboros.agent -> ouroboros.context`
- `ouroboros.loop -> ouroboros.context -> ouroboros.health_invariants -> ouroboros.modification_pipeline -> ouroboros.agent -> ouroboros.loop`
- `ouroboros.tools.evolution_loop -> ouroboros.tools.evolution_tools -> ouroboros.tools.evolution_loop`

## All Modules

| Module | Lines | Status |
|--------|-------|--------|
| `C:\Users\S\Desktop\jo\ouroboros\tools\consciousness_tools.py` | 1272 | 🔴 CRITICAL |
| `C:\Users\S\Desktop\jo\ouroboros\agent.py` | 1232 | 🔴 CRITICAL |
| `C:\Users\S\Desktop\jo\ouroboros\loop.py` | 1146 | 🔴 CRITICAL |
| `C:\Users\S\Desktop\jo\ouroboros\tools\intelligence_tools.py` | 1051 | 🔴 CRITICAL |
| `C:\Users\S\Desktop\jo\ouroboros\context.py` | 947 | 🟡 WARNING |
| `C:\Users\S\Desktop\jo\ouroboros\tools\browser.py` | 888 | 🟡 WARNING |
| `C:\Users\S\Desktop\jo\ouroboros\tools\web_research.py` | 871 | 🟡 WARNING |
| `C:\Users\S\Desktop\jo\ouroboros\llm.py` | 854 | 🟡 WARNING |
| `C:\Users\S\Desktop\jo\ouroboros\tools\skills_tools.py` | 810 | 🟡 WARNING |
| `C:\Users\S\Desktop\jo\ouroboros\tools\control.py` | 776 | 🟡 WARNING |
| `C:\Users\S\Desktop\jo\supervisor\workers.py` | 771 | 🟡 WARNING |
| `C:\Users\S\Desktop\jo\ouroboros\tools\core.py` | 763 | 🟡 WARNING |
| `C:\Users\S\Desktop\jo\supervisor\state.py` | 742 | 🟡 WARNING |
| `C:\Users\S\Desktop\jo\ouroboros\consciousness.py` | 711 | 🟡 WARNING |
| `C:\Users\S\Desktop\jo\ouroboros\tools\connection_weavers.py` | 676 | 🟡 WARNING |
| `C:\Users\S\Desktop\jo\ouroboros\tools\skill_registry.py` | 670 | 🟡 WARNING |
| `C:\Users\S\Desktop\jo\ouroboros\vault_improvements.py` | 664 | 🟡 WARNING |
| `C:\Users\S\Desktop\jo\ouroboros\tools\neural_map.py` | 649 | 🟡 WARNING |
| `C:\Users\S\Desktop\jo\ouroboros\health_invariants.py` | 627 | 🟡 WARNING |
| `C:\Users\S\Desktop\jo\ouroboros\tools\evolution_loop.py` | 614 | 🟡 WARNING |
| `C:\Users\S\Desktop\jo\ouroboros\response_analyzer.py` | 612 | 🟡 WARNING |
| `C:\Users\S\Desktop\jo\ouroboros\tool_executor.py` | 583 | 🟡 WARNING |
| `C:\Users\S\Desktop\jo\ouroboros\vault_manager.py` | 578 | 🟡 WARNING |
| `C:\Users\S\Desktop\jo\ouroboros\eval.py` | 569 | 🟡 WARNING |
| `C:\Users\S\Desktop\jo\ouroboros\vault_engine.py` | 539 | 🟡 WARNING |
| `C:\Users\S\Desktop\jo\ouroboros\extraction.py` | 536 | 🟡 WARNING |
| `C:\Users\S\Desktop\jo\supervisor\queue.py` | 528 | 🟡 WARNING |
| `C:\Users\S\Desktop\jo\supervisor\telegram.py` | 528 | 🟡 WARNING |
| `C:\Users\S\Desktop\jo\ouroboros\tools\vault.py` | 527 | 🟡 WARNING |
| `C:\Users\S\Desktop\jo\ouroboros\skills\pulse_supervisor.py` | 509 | 🟡 WARNING |
| `C:\Users\S\Desktop\jo\ouroboros\quality_gates.py` | 495 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\memory.py` | 488 | 🟢 OK |
| `C:\Users\S\Desktop\jo\supervisor\events.py` | 484 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\hybrid_memory.py` | 480 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\agent_coordinator.py` | 479 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\loop\budget.py` | 477 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\codebase_graph.py` | 464 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\shell.py` | 463 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\ai_code.py` | 462 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\skills\state_manager.py` | 452 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\skills\multi_model_verifier.py` | 451 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\vault_search.py` | 445 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\dspy_integration.py` | 443 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\parallel_reasoning.py` | 435 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\context_compaction.py` | 431 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\simulation.py` | 423 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\skills\task_dag.py` | 419 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\dashboard.py` | 413 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\dspy_tools.py` | 411 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\self_healing.py` | 410 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\file_ops.py` | 407 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\skills\agent_system.py` | 404 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\config_manager.py` | 400 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\system_map.py` | 389 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\codebase_analysis.py` | 387 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\modification_pipeline.py` | 386 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\memory_extractor.py` | 378 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\synthesis.py` | 377 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\runtime_tool_creator.py` | 373 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\evolution_tools.py` | 372 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\workspace_organizer.py` | 364 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\context_enricher.py` | 362 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\pi_prompts.py` | 358 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\stability_manager.py` | 352 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\skills\paper2code.py` | 352 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\output_compressor.py` | 352 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\utils.py` | 348 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\request_tools.py` | 347 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\embedding_simple.py` | 341 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\debug_analyzer.py` | 340 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\hot_reload.py` | 338 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\cli_anything.py` | 338 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\pipeline.py` | 337 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\skills\coordinator.py` | 335 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tree_of_thought.py` | 329 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\anatomy.py` | 325 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\git.py` | 325 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\auto_vault.py` | 322 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\neural_map_tools.py` | 320 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\dependency_graph.py` | 316 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\skills\design_system.py` | 315 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\knowledge.py` | 315 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\knowledge_discovery.py` | 314 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\complexity_router.py` | 312 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\rtk_wrapper.py` | 308 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\skills\verification.py` | 307 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\database.py` | 307 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\registry.py` | 306 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\query.py` | 305 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\traceability.py` | 305 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\skills\keyword_detector.py` | 305 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\ontology_tracker.py` | 302 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\context_compact.py` | 298 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\vault_flow_tool.py` | 297 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\drift_detector.py` | 292 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\cerebrum.py` | 291 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\normalizer.py` | 289 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tool_permissions.py` | 287 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tool_router.py` | 287 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\token_ledger.py` | 283 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\ideation.py` | 282 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\skill_selection.py` | 280 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\cost_tracker.py` | 279 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\agent_health.py` | 276 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\health_auto_fix.py` | 276 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\self_critique.py` | 276 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\review.py` | 275 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\evolution_fingerprint.py` | 273 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\evolution_proposal.py` | 271 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\codebase_cohesion.py` | 267 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\classification_engine.py` | 266 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\github.py` | 266 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\inner_skills.py` | 264 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\task_graph.py` | 262 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\skills\skill_manager.py` | 262 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\evolution_strategy.py` | 257 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\three_axis_tracker.py` | 257 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\policy.py` | 256 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tool_orchestrator.py` | 256 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\working_memory.py` | 256 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\quality_metrics.py` | 255 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\loop_llm.py` | 254 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\stack_detector.py` | 254 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\skills\cost_tracker.py` | 253 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\skills\permission_system.py` | 250 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\background_consciousness.py` | 249 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\spice.py` | 249 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\instinct_evolver.py` | 246 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\work_checkpoint.py` | 246 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\health_predictor.py` | 245 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\checkpoint.py` | 244 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\skill_logging.py` | 244 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\proactive_outreach.py` | 243 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\persistent_identity.py` | 242 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\evolution_stats.py` | 242 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\neural_map_models.py` | 242 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\awareness.py` | 240 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\episodic_memory.py` | 239 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\delta_eval.py` | 236 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\buglog.py` | 235 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\temporal_learning.py` | 232 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\vault_parser.py` | 229 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\skills\dream_system.py` | 228 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\evolution_benchmark.py` | 224 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\orchestrator.py` | 223 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\knowledge_decay.py` | 218 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\vault_models.py` | 218 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\behavioral_drift.py` | 217 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\decision_trace.py` | 216 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\proof_gate.py` | 213 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\sparse_executor.py` | 213 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\confidence.py` | 209 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\vault_links.py` | 208 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\capability_gap.py` | 207 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\progressive_disclosure.py` | 207 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\session_compaction.py` | 207 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\gap_detector.py` | 202 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\review.py` | 200 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\stuck_detector.py` | 200 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\loop_budget.py` | 199 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\context_cache.py` | 198 | 🟢 OK |
| `C:\Users\S\Desktop\jo\supervisor\git_ops.py` | 197 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\multi_verify.py` | 196 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\agent_state.py` | 195 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\dead_letter_queue.py` | 195 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\hallucination_guard.py` | 195 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\evolution_fitness.py` | 194 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\vision.py` | 194 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\resilience\circuit_breaker.py` | 192 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\resilience\degradation.py` | 190 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\mcp_server.py` | 188 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\embedding_tool.py` | 188 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\resilience\supervisor.py` | 187 | 🟢 OK |
| `C:\Users\S\Desktop\jo\supervisor\watchdog.py` | 183 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\apply_patch.py` | 178 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\workflow.py` | 177 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\bulkhead_executor.py` | 176 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\budget_router.py` | 170 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\resilience\stuck_detector.py` | 169 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\resilience\checkpoint.py` | 168 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\skills.py` | 164 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\neural_map_scan.py` | 156 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\codebase_models.py` | 154 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\resilience\context_manager.py` | 153 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\runtime_tools.py` | 153 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\loop_response.py` | 146 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\worktree_tools.py` | 145 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\workspace_tools.py` | 134 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\auto_system.py` | 130 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\worktree_manager.py` | 130 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\tool_discovery.py` | 128 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\semantic_filter.py` | 122 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\task_tools.py` | 113 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\query_engine.py` | 112 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\experience_indexer.py` | 108 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\resilience\backoff.py` | 108 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\skills\repository.py` | 108 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\owner_inject.py` | 103 | 🟢 OK |
| `C:\Users\S\Desktop\jo\supervisor\github_api.py` | 102 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\agent_index.py` | 100 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\agent_messaging.py` | 96 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\memory_consolidator.py` | 95 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\compression.py` | 93 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\factory.py` | 85 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\health.py` | 83 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\skills\runtime.py` | 82 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\compact_context.py` | 80 | 🟢 OK |
| `C:\Users\S\Desktop\jo\supervisor\health_reporter.py` | 77 | 🟢 OK |
| `C:\Users\S\Desktop\jo\supervisor\sys_ops.py` | 59 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\plan_mode_tools.py` | 58 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\rules.py` | 57 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\skill_definitions.py` | 56 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\experience_search.py` | 55 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\analytics.py` | 48 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\search.py` | 46 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\vault.py` | 19 | 🟢 OK |
| `C:\Users\S\Desktop\jo\supervisor\states.py` | 16 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\anatomy_tools.py` | 5 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\buglog_tools.py` | 5 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\cerebrum_tools.py` | 5 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\compaction_tools.py` | 5 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\complexity_tools.py` | 5 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\debug_tools.py` | 5 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\depgraph_tools.py` | 5 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\gap_tools.py` | 5 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\hallucination_tools.py` | 5 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\ideation_tools.py` | 5 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\memory_extractor_tools.py` | 5 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\multi_verify_tools.py` | 5 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\orchestrator_tools.py` | 5 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\permission_tools.py` | 5 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\plugin_tools.py` | 5 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\quality_gates_tools.py` | 5 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\query_tools.py` | 5 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\stack_tools.py` | 5 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\stuck_tools.py` | 5 | 🟢 OK |
| `C:\Users\S\Desktop\jo\ouroboros\tools\token_ledger_tools.py` | 5 | 🟢 OK |