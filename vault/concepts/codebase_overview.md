---
title: Codebase Overview
created: 2026-03-25
category: concepts
tags:  []

---

# Codebase Overview

Generated: 2026-03-24 21:13 (git: 061d5b2c8d51)
Repository: C:\Users\JO\OneDrive\Desktop\jo

> Freshness: This note reflects the codebase at commit `061d5b2c8d51`. If HEAD has moved since generation, run `codebase_graph.scan_repo()` to refresh.

## Summary

- **Total Nodes:** 585
- **Total Edges:** 4233
- **Files:** 30
- **Classes:** 50
- **Functions:** 352

## Architecture Layers

### Core (50 nodes)

- **ouroboros\agent.py** (49 items)
  - `datetime` (line 11)
  - `ouroboros.utils.safe_relpath` (line 26)
  - `ouroboros.utils.sanitize_task_for_event` (line 26)
  - `ouroboros.llm.add_usage` (line 35)
  - `ouroboros.tools.ToolRegistry` (line 36)
  - ... and 44 more

### Module (530 nodes)

- **archive\deprecated\full_startup.py** (7 items)
  - `git_orchestrator.GitOrchestrator` (line 19)
  - `FullStartup` (line 33)
  - `FullStartup.__init__` (line 36)
  - `FullStartup.start` (line 45)
  - `FullStartup.start_launcher` (line 68)
  - ... and 2 more
- **archive\deprecated\git_orchestrator.py** (36 items)
  - `GitLock` (line 36)
  - `GitLock.__init__` (line 39)
  - `GitLock.acquire` (line 43)
  - `GitLock.release` (line 77)
  - `GitLock.get_instance_id` (line 82)
  - ... and 31 more
- **archive\deprecated\git_state_manager.py** (10 items)
  - `GitStateManager` (line 14)
  - `GitStateManager.__init__` (line 17)
  - `GitStateManager.get_clean_state` (line 22)
  - `GitStateManager.stash_changes` (line 32)
  - `GitStateManager.pull_with_rebase` (line 47)
  - ... and 5 more
- **archive\deprecated\instance_id.py** (8 items)
  - `platform` (line 6)
  - `socket` (line 7)
  - `InstanceIdentifier` (line 13)
  - `InstanceIdentifier.__init__` (line 16)
  - `InstanceIdentifier._load_or_create_id` (line 25)
  - ... and 3 more
- **archive\deprecated\integrated_orchestrator.py** (10 items)
  - `model_orchestrator.ModelStatus` (line 22)
  - `AgentRole` (line 27)
  - `AgentInstance` (line 38)
  - `IntegratedOrchestrator` (line 49)
  - `IntegratedOrchestrator.__init__` (line 54)
  - ... and 5 more
- **archive\deprecated\model_orchestrator.py** (13 items)
  - `random` (line 10)
  - `enum.Enum` (line 13)
  - `requests` (line 15)
  - `dotenv.load_dotenv` (line 16)
  - `ModelStatus` (line 23)
  - ... and 8 more
- **archive\deprecated\monitor.py** (9 items)
  - `signal` (line 12)
  - `OuroborosMonitor` (line 29)
  - `OuroborosMonitor.__init__` (line 32)
  - `OuroborosMonitor.sync_git_state` (line 56)
  - `OuroborosMonitor.start_launcher` (line 78)
  - ... and 4 more
- **archive\deprecated\ouroboros_system.py** (17 items)
  - `uuid` (line 13)
  - `instance_id.InstanceIdentifier` (line 21)
  - `git_state_manager.GitStateManager` (line 22)
  - `model_orchestrator.ModelOrchestrator` (line 23)
  - `TaskQueue` (line 28)
  - ... and 12 more
- **archive\deprecated\service_setup.py** (2 items)
  - `setup_systemd_service` (line 11)
  - `setup_cron_job` (line 50)
- **archive\deprecated\start_ouroboros.py** (2 items)
  - `ouroboros_system.OuroborosSystem` (line 15)
  - `main` (line 29)
- **colab_launcher.py** (52 items)
  - `install_launcher_deps` (line 20)
  - `ensure_claude_code_cli` (line 29)
  - `ouroboros.apply_patch.install` (line 54)
  - `google.colab.userdata` (line 64)
  - `google.colab.drive` (line 65)
  - ... and 47 more
- **debug_check.py** (4 items)
  - `check_imports` (line 8)
  - `check_version_sync` (line 39)
  - `check_module_sizes` (line 65)
  - `main` (line 88)
- **ouroboros\apply_patch.py** (1 items)
  - `install` (line 174)
- **ouroboros\awareness.py** (12 items)
  - `AwarenessSystem` (line 9)
  - `AwarenessSystem.__init__` (line 10)
  - `AwarenessSystem.scan` (line 22)
  - `AwarenessSystem._get_git_info` (line 99)
  - `AwarenessSystem._is_git_clean` (line 130)
  - ... and 7 more
- **ouroboros\codebase_graph.py** (40 items)
  - `typing.Set` (line 18)
  - `GraphNode` (line 24)
  - `GraphEdge` (line 38)
  - `CodebaseGraph` (line 49)
  - `CodebaseGraph.add_node` (line 58)
  - ... and 35 more
- **ouroboros\config_manager.py** (23 items)
  - `yaml` (line 21)
  - `ConfigSchema` (line 27)
  - `ConfigurationManager` (line 93)
  - `ConfigurationManager.get_instance` (line 100)
  - `ConfigurationManager.__init__` (line 109)
  - ... and 18 more
- **ouroboros\consciousness.py** (32 items)
  - `concurrent.futures` (line 19)
  - `queue` (line 24)
  - `threading` (line 25)
  - `traceback` (line 27)
  - `ouroboros.utils.append_jsonl` (line 30)
  - ... and 27 more
- **ouroboros\context.py** (42 items)
  - `copy` (line 10)
  - `ouroboros.utils.read_text` (line 18)
  - `ouroboros.utils.clip_text` (line 18)
  - `ouroboros.utils.estimate_tokens` (line 18)
  - `_build_user_content` (line 30)
  - ... and 37 more
- **ouroboros\context_cache.py** (17 items)
  - `hashlib` (line 13)
  - `CacheEntry` (line 25)
  - `CacheEntry.is_expired` (line 36)
  - `CacheEntry.age_seconds` (line 40)
  - `ContextCache` (line 44)
  - ... and 12 more
- **ouroboros\context_enricher.py** (17 items)
  - `ContextEnricher` (line 15)
  - `ContextEnricher.__init__` (line 18)
  - `ContextEnricher.is_enabled` (line 27)
  - `ContextEnricher.enrich_for_task` (line 30)
  - `ContextEnricher.build_enrichment_text` (line 61)
  - ... and 12 more
- **ouroboros\context_runtime.py** (4 items)
  - `ouroboros.utils.utc_now_iso` (line 10)
  - `ouroboros.utils.get_git_info` (line 10)
  - `build_runtime_section` (line 15)
  - `_safe_read` (line 52)
- **ouroboros\cost_tracker.py** (13 items)
  - `CostEntry` (line 17)
  - `CostReport` (line 29)
  - `CostTracker` (line 39)
  - `CostTracker.__init__` (line 53)
  - `CostTracker.is_enabled` (line 58)
  - ... and 8 more
- **ouroboros\delta_eval.py** (17 items)
  - `DeltaResult` (line 29)
  - `EvaluationHistory` (line 43)
  - `EvaluationHistory.add` (line 49)
  - `EvaluationHistory.trend` (line 61)
  - `DeltaEvaluator` (line 70)
  - ... and 12 more
- **ouroboros\drift_detector.py** (14 items)
  - `DriftDetector` (line 25)
  - `DriftDetector.__init__` (line 28)
  - `DriftDetector._load_json` (line 34)
  - `DriftDetector.run_all_checks` (line 43)
  - `DriftDetector.get_report` (line 56)
  - ... and 9 more
- **ouroboros\episodic_memory.py** (17 items)
  - `time` (line 18)
  - `Episode` (line 27)
  - `Episode.to_dict` (line 40)
  - `Episode.from_dict` (line 54)
  - `EpisodicMemory` (line 68)
  - ... and 12 more
- **ouroboros\eval.py** (21 items)
  - `subprocess` (line 8)
  - `typing.Callable` (line 11)
  - `EvalResult` (line 17)
  - `EvalReport` (line 25)
  - `TaskEvaluator` (line 32)
  - ... and 16 more
- **ouroboros\extraction.py** (32 items)
  - `__future__.annotations` (line 16)
  - `json` (line 18)
  - `logging` (line 19)
  - `os` (line 20)
  - `re` (line 21)
  - ... and 27 more
- **self_check.py** (30 items)
  - `check_git_status` (line 20)
  - `check_git_diff` (line 49)
  - `check_version` (line 68)
  - `check_python_syntax` (line 80)
  - `check_requirements` (line 101)
  - ... and 25 more

### Test (5 nodes)

- **archive\deprecated\test_orchestrator.py** (4 items)
  - `asyncio` (line 4)
  - `sys` (line 5)
  - `integrated_orchestrator.IntegratedOrchestrator` (line 8)
  - `test` (line 10)

## Most Connected Nodes

- **main** (function) - 174 connections
- **_build_health_invariants** (function) - 136 connections
- **OuroborosAgent.handle_task** (function) - 87 connections
- **main** (function) - 84 connections
- **colab_launcher.py** (file) - 75 connections
- **OuroborosAgent._emit_task_results** (function) - 73 connections
- **context.py** (file) - 67 connections
- **agent.py** (file) - 57 connections
- **compact_tool_history_llm** (function) - 53 connections
- **AwarenessSystem.scan** (function) - 51 connections

---
*Auto-generated by Jo's codebase graph system*