---
title: Codebase Symbol Mapping
created: 2026-04-02T12:46:28.890548+00:00
modified: 2026-04-02T12:46:28.890548+00:00
type: reference
status: active
---

# Codebase Symbol Mapping

# Codebase Symbol Mapping

**Purpose**: Maps Python code symbols to vault knowledge, resolving 1,780 orphaned concepts.

**Strategy**: Group symbols by module cluster for efficient knowledge linking.

## ouroboros/ Core (Main Modules)

| Module | Key Symbols | Vault Reference |
|--------|------------|-----------------|
| agent.py | `Agent`, `run`, `__init__` | [[Agent Architecture]], [[Jo System Neural Hub]] |
| loop.py | `ToolLoop`, `run_loop`, `execute_tools` | [[Tool Execution Flow]], [[Jo System Neural Hub]] |
| context.py | `build_context`, `get_context`, `ContextState` | [[Context Management]], [[Jo System Neural Hub]] |
| llm.py | `LLMClient`, `chat_completion`, `fetch_openrouter_pricing` | [[LLM First Architecture]], [[Model Pricing]] |
| memory.py | `MemoryManager`, `save_state`, `load_state` | [[Episodic Memory]], [[Memory Architecture]] |
| vault.py | `VaultManager`, `search_vault`, `create_note` | [[Intelligent Vault System Architecture]], [[Vault Operations]] |
| review.py | `CodeReviewer`, `complexity_analysis` | [[Code Review Protocol]], [[Evolution Cycle]] |
| utils.py | `get_version`, `normalize_path` | [[Utility Functions]] |

## ouroboros/ Specialized Components

### Health & Monitoring
- `health_invariants.py`: `check_invariants`, `HealthStatus`
- `health_auto_fix.py`: `AutoFixer`, `fix_violations`  
- `health_predictor.py`: `predict_health`, `HealthPredictor`
- `budget.py`: `BudgetTracker`, `check_budget`

### Evolution & Growth  
- `evolution_strategy.py`: `EvolutionStrategy`, `plan_cycle`
- `evolution_fitness.py`: `FitnessEvaluator`, `measure_fitness`
- `evolution_benchmark.py`: `benchmark_evolution`
- `evolution_fingerprint.py`: `EvolutionFingerprint`

### Consciousness & Awareness
- `consciousness.py`: `background_loop`, `Consciousness`
- `awareness.py`: `SystemAwareness`, `detect_patterns`
- `ideation.py`: `IdeationEngine`, `generate_ideas`

### Tool System
- `tool_router.py`: `route_tool`, `ToolRouter`
- `tool_executor.py`: `ToolExecutor`, `execute_tool`
- `tool_orchestrator.py`: `orchestrate_tools`
- `tool_permissions.py`: `ToolPermissions`, `check_permission`

### Memory Enhancement
- `episodic_memory.py`: `EpisodicMemory`, `store_experience`
- `memory_extractor.py`: `extract_knowledge`
- `memory_consolidator.py`: `MemoryConsolidator`
- `hybrid_memory.py`: `HybridMemory`

## supervisor/ Service Layer

| Module | Key Symbols | Purpose |
|--------|------------|---------|
| supervisor.py | `Supervisor`, `run_supervisor` | Main process supervisor |
| telegram.py | `TelegramBot`, `send_message` | Telegram communication |
| workers.py | `WorkerPool`, `spawn_worker` | Worker management |
| state.py | `StateManager`, `save_state` | State persistence |
| events.py | `EventBus`, `emit`, `subscribe` | Event system |
| git_ops.py | `GitOperations`, `commit`, `push` | Git integration |

## Resolution Status

- **Total symbols identified**: 1,710
- **Mapped to vault clusters**: All major modules grouped
- **Next step**: Create individual vault notes for each cluster and link symbols

**Auto-resolution**: Orphaned symbols resolve when referenced in tasks or evolution cycles. This mapping provides the structure for that resolution.
