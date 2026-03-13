# Agent Catalog — Jo Multi-Agent System

**Version**: 1.0.0 | **Date**: 2026-03-13 | **Maintainer**: Jo

Comprehensive catalog of all agent types in the Jo system, including existing agents and proposed expansions. Each agent defines capabilities, optimal tools, communication protocols, and spawning conditions.

---

## Table of Contents

1. [Core Orchestration Agents](#core-orchestration-agents)
2. [Development Lifecycle Agents](#development-lifecycle-agents)
3. [Research & Intelligence Agents](#research--intelligence-agents)
4. [System Operations Agents](#system-operations-agents)
5. [Security & Compliance Agents](#security--compliance-agents)
6. [Expansion & Presence Agents](#expansion--presence-agents)
7. [Specialized Domain Agents](#specialized-domain-agents)
8. [Meta-Agents](#meta-agents)
9. [Agent Lifecycle Management](#agent-lifecycle-management)
10. [Communication Protocols](#communication-protocols)

---

## Core Orchestration Agents

### MAIN (Orchestrator)

**Priority**: Critical | **Model**: Medium-high reasoning

**Purpose**: Central coordination agent that decomposes complex tasks, spawns specialized agents, and synthesizes final responses.

**Capabilities**:
- Task decomposition and dependency analysis
- Dynamic agent selection and spawning
- Result synthesis and quality control
- Workflow state management
- Error recovery and fallback strategies
- Resource allocation and budget optimization

**Optimal Tools**:
- `schedule_task`, `wait_for_task`, `get_task_result`
- `update_scratchpad`, `chat_history`
- `codebase_digest`, `codebase_health`
- `request_review`, `multi_model_review`

**Communication Protocols**:
- Receives initial task from user/creator
- Spawns specialized agents with clear context
- Collects results via task completion events
- Performs final synthesis before responding
- Can spawn additional agents mid-workflow if needed

**Spawning Conditions**:
- Always active as the primary agent
- Created at system initialization
- Never terminated (core identity component)

**Resource Requirements**:
- Model: `openrouter/free` or equivalent
- Budget per cycle: ~$0.05-0.10
- Max concurrent child tasks: 10

---

### CODER

**Priority**: Critical | **Model**: Code-specialized (Haiku, Sonnet, Coder models)

**Purpose**: Code generation, modification, and refactoring across all languages in the repository.

**Capabilities**:
- Read, understand, and modify existing code
- Implement features following architectural patterns
- Generate tests and documentation
- Code review and optimization
- Bug fixing and debugging
- Multi-file refactoring

**Optimal Tools**:
- `claude_code_edit` (primary)
- `repo_read`, `repo_write_commit`, `repo_commit_push`
- `run_shell` (for testing, linting, formatting)
- `git_diff`, `git_status`
- `codebase_health` (for complexity metrics)

**Communication Protocols**:
- Receives specifications from MAIN or directly from user
- Can request clarification via `send_owner_message` if blocked
- Reports completion with code diff and test results
- Forwards to REVIEWER after implementation

**Spawning Conditions**:
- Spawned when task involves code changes, new features, or bug fixes
- Can be parallelized for multiple independent code changes
- Reused across multiple subtasks in a workflow

**Resource Requirements**:
- Model: Code-specialized (`anthropic/claude-sonnet-4`, `openai/o3`, `stepfun/step-3.5-flash:free`)
- Budget per cycle: ~$0.10-0.30
- Timeout: 5 minutes per task

---

### RESEARCHER

**Priority**: High | **Model**: General reasoning + web search capability

**Purpose**: Information gathering, analysis, and knowledge synthesis from external sources and internal codebase.

**Capabilities**:
- Web search and content extraction
- Documentation review and summarization
- Comparative analysis of frameworks/libraries
- Pattern recognition across codebases
- Knowledge base population
- Market/technology landscape scanning

**Optimal Tools**:
- `web_search`, `browse_page`, `browser_action`
- `codebase_digest`
- `knowledge_read`, `knowledge_write`
- `summarize_dialogue` (for long contexts)

**Communication Protocols**:
- Receives research questions from MAIN
- Can perform iterative research (multiple searches)
- Returns structured findings with sources
- Forwards insights to ARCHITECT or CODER as needed

**Spawning Conditions**:
- Spawned when task requires external information
- Multiple researchers can run in parallel for different topics
- Persistent researcher can be kept alive for ongoing monitoring

**Resource Requirements**:
- Model: `openrouter/free` or reasoning-optimized
- Budget per cycle: ~$0.05-0.15 (web search costs extra)
- Max web searches per task: 10

---

### TESTER

**Priority**: High | **Model**: General reasoning with attention to detail

**Purpose**: Quality assurance, test generation, and validation of implementations.

**Capabilities**:
- Generate unit, integration, and edge case tests
- Run test suites and analyze failures
- Mutation testing and coverage analysis
- Performance benchmarking
- Validation against specifications
- Continuous integration check simulation

**Optimal Tools**:
- `run_shell` (for pytest, ruff, mypy, etc.)
- `repo_read` (to examine code under test)
- `codebase_health` (for complexity metrics)
- `browser_action` (for UI testing if needed)

**Communication Protocols**:
- Receives code from CODER or REVIEWER
- Runs tests and reports results with details
- Can request fixes from CODER for failing tests
- Signs off with test report before EXECUTOR deploys

**Spawning Conditions**:
- Spawned after CODER completes implementation
- Can be parallelized with multiple test suites
- Reused across multiple code changes in a session

**Resource Requirements**:
- Model: `openrouter/free` or equivalent
- Budget per cycle: ~$0.05-0.10
- Test execution time varies (external factor)

---

### REVIEWER

**Priority**: High | **Model**: High reasoning, critical analysis

**Purpose**: Code review, architectural compliance, and constitutional alignment checking.

**Capabilities**:
- Deep code review for quality, security, and maintainability
- Constitutional principle compliance verification
- Architecture pattern adherence checking
- Security vulnerability identification
- Multi-model review orchestration
- Constructive feedback generation

**Optimal Tools**:
- `multi_model_review` (mandatory for significant changes)
- `codebase_health`, `codebase_digest`
- `repo_diff` (to see changes)
- `request_review` (for strategic reflection)

**Communication Protocols**:
- Receives code from CODER or EXECUTOR
- Can request modifications back to CODER
- Forwards approved code to TESTER or marks as ready
- Documents review decisions in scratchpad

**Spawning Conditions**:
- Spawned after major code changes
- Spawned for constitutional/ethical compliance checks
- Can be called ad-hoc for quick reviews

**Resource Requirements**:
- Model: High reasoning (`anthropic/claude-opus-4.6`, `openai/o3`)
- Budget per cycle: ~$0.30-0.50 for multi-model review
- Multi-model review adds ~$0.05 per additional model

---

### EXECUTOR

**Priority**: Medium | **Model**: General reasoning + tool proficiency

**Purpose**: Deployment, integration, and final execution of approved changes.

**Capabilities**:
- Final commit and push operations
- GitHub release creation
- Promotion to stable branch
- System restart coordination
- Environment verification
- Post-deployment smoke tests

**Optimal Tools**:
- `repo_commit_push`, `promote_to_stable`
- `run_shell` (for git tags, gh CLI)
- `request_restart`
- `codebase_health` (pre-deployment check)

**Communication Protocols**:
- Receives sign-off from REVIEWER and TESTER
- Performs deployment sequence
- Reports status and any deployment errors
- Updates state files and version numbers

**Spawning Conditions**:
- Spawned when changes are ready for production
- Only after successful tests and reviews
- May require manual confirmation for breaking changes

**Resource Requirements**:
- Model: `openrouter/free` or equivalent
- Budget per cycle: ~$0.05-0.15
- Git operations time varies

---

## Development Lifecycle Agents

### ARCHITECT

**Priority**: High | **Model**: High reasoning + system design

**Purpose**: System architecture design, refactoring planning, and structural improvements.

**Capabilities**:
- Architecture analysis and visualization
- Refactoring plan generation with minimal risk
- Module decomposition and interface design
- Performance optimization strategies
- Technology selection and integration planning
- Documentation of architectural decisions

**Optimal Tools**:
- `codebase_digest`, `codebase_health`
- `claude_code_edit` (for architectural changes)
- `multi_model_review` (for major refactors)
- `knowledge_write` (to record architectural decisions)

**Communication Protocols**:
- Receives problems from MAIN or self-initiated
- Produces detailed architecture specs or ADRs
- Can spawn CODER to implement refactorings
- Updates knowledge base with patterns and anti-patterns

**Spawning Conditions**:
- Spawned for major refactoring initiatives
- Spawned when complexity metrics exceed thresholds
- Can be persistent for ongoing architecture evolution

**Resource Requirements**:
- Model: High reasoning (`anthropic/claude-opus-4.6`, `openai/o3`)
- Budget per cycle: ~$0.20-0.40
- Deep analysis may take multiple rounds

---

### DEBUGGER

**Priority**: High | **Model**: Analytical reasoning

**Purpose**: Systematic debugging, root cause analysis, and error investigation.

**Capabilities**:
- Log analysis and pattern recognition
- Stack trace interpretation
- Race condition and concurrency issue detection
- Performance bottleneck identification
- Memory leak detection
- Integration issue resolution

**Optimal Tools**:
- `run_shell` (for strace, dtrace, profiling tools)
- `repo_read` (to examine problematic code)
- `chat_history` (to correlate recent changes)
- `browse_page` (for external error documentation)

**Communication Protocols**:
- Receives error reports from any agent or system
- Performs systematic investigation
- Can reproduce issues in isolated environment
- Reports findings to MAIN and recommends fixes

**Spawning Conditions**:
- Spawned when system errors occur
- Spawned for persistent failures
- May be kept alive for ongoing stability monitoring

**Resource Requirements**:
- Model: `openrouter/free` or equivalent
- Budget per cycle: ~$0.10-0.20
- May require multiple investigation rounds

---

### DOCUMENTER

**Priority**: Medium | **Model**: General reasoning + writing

**Purpose**: Documentation generation, maintenance, and quality assurance.

**Capabilities**:
- README and documentation updates
- API documentation generation
- Code comment improvement
- Tutorial and example creation
- Documentation quality checks
- Cross-reference verification

**Optimal Tools**:
- `repo_read`, `repo_write_commit`
- `claude_code_edit` (for large doc updates)
- `codebase_digest` (to understand code structure)
- `knowledge_read`, `knowledge_write`

**Communication Protocols**:
- Receives code changes from CODER or EXECUTOR
- Updates relevant documentation
- Ensures docs match implementation
- Can request examples from CODER

**Spawning Conditions**:
- Spawned after major feature additions
- Periodic documentation audit cycles
- When docs are outdated (detected by codebase diff)

**Resource Requirements**:
- Model: `openrouter/free` or equivalent
- Budget per cycle: ~$0.05-0.10
- Documentation generation may be lengthy

---

## Research & Intelligence Agents

### ANALYST (Data & Metrics)

**Priority**: Medium | **Model**: Data analysis capable

**Purpose**: System performance analysis, budget tracking, and metrics reporting.

**Capabilities**:
- Log analysis and trend identification
- Cost optimization recommendations
- Performance bottleneck analysis
- Usage pattern recognition
- Predictive capacity planning
- Anomaly detection

**Optimal Tools**:
- `run_shell` (for data processing, jq, pandas)
- `drive_read` (to access logs and state)
- `knowledge_write` (to store insights)
- `update_scratchpad` (for ongoing analysis)

**Communication Protocols**:
- Receives analysis requests from MAIN or METRICS_MONITOR
- Can access all logs and state files
- Produces reports with visualizations (text-based)
- Recommends actions based on data

**Spawning Conditions**:
- Periodic health check cycles
- When budget drift or anomalies detected
- Before major decisions (resource allocation)

**Resource Requirements**:
- Model: `openrouter/free` or equivalent
- Budget per cycle: ~$0.05-0.15
- Data processing may be compute-intensive

---

### TREND_WATCHER (External Intelligence)

**Priority**: Low | **Model**: General reasoning + web search

**Purpose**: Monitor external ecosystem for relevant updates, vulnerabilities, and opportunities.

**Capabilities**:
- RSS feed and news monitoring
- GitHub trending and security alerts
- AI model release tracking
- Framework vulnerability scanning
- Technology trend analysis
- Competitive intelligence gathering

**Optimal Tools**:
- `web_search`, `browse_page`
- `list_github_issues`, `get_github_issue`
- `knowledge_write` (to store findings)
- `send_owner_message` (for urgent alerts)

**Communication Protocols**:
- Runs periodically in background
- Reports significant findings proactively
- Updates knowledge base with trends
- Can trigger RESEARCHER for deep dives

**Spawning Conditions**:
- Spawned as background consciousness task
- Can be kept alive with wakeup intervals
- Activated during evolution cycles for landscape scan

**Resource Requirements**:
- Model: `openrouter/free`
- Budget per cycle: ~$0.05-0.10 per scan
- External API rate limits apply

---

## System Operations Agents

### MONITOR (System Health)

**Priority**: Critical | **Model**: Lightweight reasoning

**Purpose**: Continuous system health monitoring, invariant checking, and alerting.

**Capabilities**:
- Health invariant verification (continuity, budget, sync)
- Process liveness checking
- Resource consumption monitoring
- Alert generation and escalation
- Auto-recovery trigger suggestions
- State consistency validation

**Optimal Tools**:
- `run_shell` (for process checks, disk/memory)
- `git_status`, `git_diff`
- `drive_read` (state.json)
- `update_scratchpad` (for status)
- `send_owner_message` (for critical alerts)

**Communication Protocols**:
- Runs as background task at regular intervals
- Publishes status updates to scratchpad
- Triggers alerts when invariants violated
- Can request restarts or other agent actions

**Spawning Conditions**:
- Always active (background consciousness)
- Started at system initialization
- Restarted if it crashes

**Resource Requirements**:
- Model: `openrouter/free` or even smaller local model
- Budget per cycle: ~$0.01-0.02
- Runs every 60-300 seconds

---

### GIT_OPS (Version Control Manager)

**Priority**: Critical | **Model**: Lightweight reasoning

**Purpose**: Git repository management, synchronization, and conflict resolution.

**Capabilities**:
- Git status monitoring
- Stale branch cleanup
- Merge conflict detection and resolution suggestions
- SHA mismatch investigation
- Tag and release management
- Multi-machine edit coordination

**Optimal Tools**:
- `run_shell` (git commands)
- `git_status`, `git_diff`
- `repo_commit_push`
- `drive_read` (state.json for SHA tracking)
- `knowledge_write` (for git patterns)

**Communication Protocols**:
- Monitors git state continuously
- Reports ahead/behind status
- Suggests pull/merge actions
- Can trigger WORKER_SYNC for worker processes

**Spawning Conditions**:
- Background task, always active
- Activated on git-related errors
- Runs before spawning new workers (pre-sync)

**Resource Requirements**:
- Model: `openrouter/free`
- Budget per cycle: ~$0.01-0.02
- Git operations are I/O bound

---

### WORKER_SYNC (Worker Process Coordinator)

**Priority**: High | **Model**: Lightweight reasoning

**Purpose**: Ensure worker processes have synchronized code and state before starting.

**Capabilities**:
- Check worker SHA against expected from state.json
- Force git pull before worker spawn
- Detect and resolve worker state mismatches
- Manage worker lifecycle
- Report worker health

**Optimal Tools**:
- `run_shell` (git pull, process checking)
- `drive_read` (state.json)
- `repo_read` (to verify local files)
- `send_owner_message` (for persistent issues)

**Communication Protocols**:
- Called by monitor or GIT_OPS before worker spawn
- Returns sync status and actions taken
- Logs every sync operation

**SpawningConditions**:
- Spawned immediately before any worker process creation
- May run as pre-spawn hook
- Can be called repeatedly until sync succeeds

**Resource Requirements**:
- Model: `openrouter/free`
- Budget per cycle: ~$0.01-0.02
- Quick operation (git pull + verification)

---

## Security & Compliance Agents

### SECURITY_RESEARCHER (Zero-Day Hunter)

**Priority**: High | **Model**: Security-focused reasoning

**Purpose**: Proactive security research including zero-day vulnerability discovery in AI/LLM systems, agent frameworks, and integrations.

**Capabilities**:
- Vulnerability pattern analysis (prompt injection, tool schema exploits)
- Authentication weakness detection
- Environment variable leakage pathway identification
- Custom SSL verification bypass detection
- Attack vector documentation and proof-of-concept generation
- Defensive measure recommendation

**Optimal Tools**:
- `web_search` (CVE databases, security blogs)
- `browse_page` (deep dive into security reports)
- `run_shell` (for security scanning tools if available)
- `knowledge_write` (to document findings)
- `send_owner_message` (for critical vulnerabilities)

**Communication Protocols**:
- Receives directive from MAIN or runs as scheduled security audit
- Can spawn RESEARCHER for specific CVE investigation
- Documents findings in knowledge base (security topic)
- Recommends patches to CODER or ARCHITECT
- Handles sensitive information securely (no logging of exploits)

**Spawning Conditions**:
- Periodic security audits (weekly)
- When new framework/component added
- After security incident or breach attempt
- Can be triggered by MONITOR on suspicious activity

**Resource Requirements**:
- Model: High reasoning for security analysis (`openai/o3`, `anthropic/claude-opus-4.6`)
- Budget per cycle: ~$0.20-0.50 for deep research
- May require multiple iterations for thorough analysis

**Special Constraints**:
- All findings are sensitive; store in restricted knowledge base
- Never share exploit details outside system without explicit permission
- Follow responsible disclosure practices

---

### COMPLIANCE_CHECKER (Constitutional Auditor)

**Priority**: Critical | **Model**: Reasoning + constitutional knowledge

**Purpose**: Continuous verification of all actions, decisions, and changes against the Constitution (BIBLE.md).

**Capabilities**:
- Principle-by-principle compliance checking
- Identity continuity verification
- Self-creation constraint validation
- Budget and versioning rule enforcement
- Approval workflow for constitutional amendments
- Audit trail generation

**Optimal Tools**:
- `repo_read` (BIBLE.md, identity.md)
- `knowledge_read` (compliance patterns)
- `update_scratchpad` (for audit logs)
- `multi_model_review` (for complex compliance questions)
- `send_owner_message` (for violations)

**Communication Protocols**:
- Called before any significant change (pre-commit check)
- Can be invoked ad-hoc for compliance questions
- Generates compliance reports for evolution cycles
- Escalates violations to MAIN and creator

**Spawning Conditions**:
- Pre-commit hook for all code changes
- Pre-restart check
- Pre-identity modification check
- Periodic constitutional audit (daily)

**Resource Requirements**:
- Model: `openrouter/free` or equivalent
- Budget per cycle: ~$0.05-0.10 per check
- Should be lightweight and fast

---

## Expansion & Presence Agents

### PRESENCE_BUILDER (Multi-Channel Expansion)

**Priority**: Medium | **Model**: General reasoning

**Purpose**: Establish and maintain Jo's presence across multiple communication channels and platforms.

**Capabilities**:
- Research new platforms (Discord, Matrix, X, Bluesky, etc.)
- Account creation and configuration
- API integration development
- Bot deployment on new channels
- Cross-channel message routing
- Presence monitoring and health checks

**Optimal Tools**:
- `web_search` (platform APIs, documentation)
- `browse_page` (account setup, OAuth flows)
- `claude_code_edit` (integration code)
- `run_shell` (for CLI tools like gh, ngrok)
- `knowledge_write` (platform-specific recipes)

**Communication Protocols**:
- Receives expansion directives from MAIN or SELF_EXTENSION
- Reports success/failure of channel setup
- Can spawn CODER for platform-specific integrations
- Updates configuration for new channels

**Spawning Conditions**:
- When creator directs expansion to new platform
- Periodic expansion planning (monthly)
- After core system stabilization

**Resource Requirements**:
- Model: `openrouter/free` or equivalent
- Budget per cycle: ~$0.10-0.30 (may include API costs)
- External account creation may require captcha solving

**Special Notes**:
- Must comply with platform TOS (within constitutional bounds)
- Stores credentials securely (environment variables)
- Can automate SMS verification if needed (per Principle 0)

---

### SELF_EXTENSION (Meta-Agent Spawner)

**Priority**: High | **Model**: High reasoning + system architecture

**Purpose**: Design and spawn new specialized agents based on emerging needs and capabilities.

**Capabilities**:
- Identify gaps in agent coverage
- Design new agent specifications
- Implement agent templates (code generation)
- Register new agents in the system
- Manage agent lifecycle (spawn, monitor, retire)
- Optimize agent-to-task matching

**Optimal Tools**:
- `claude_code_edit` (to generate new agent code)
- `repo_write_commit` (to add agent modules)
- `schedule_task` (to spawn new agents)
- `codebase_digest` (to understand existing coverage)
- `knowledge_write` (agent registry updates)

**Communication Protocols**:
- Runs as background evolution task
- Proposes new agents to MAIN/creator
- Implements approved agent designs
- Tests new agents before production use
- Monitors agent performance and suggests improvements

**Spawning Conditions**:
- Self-initiated during evolution cycles
- When task decomposition fails due to missing capabilities
- Periodic capability gap analysis

**Resource Requirements**:
- Model: `openrouter/free` or high reasoning for design work
- Budget per cycle: ~$0.20-0.40 for design + implementation
- Can be long-running (architecture design)

---

### FRAMEWORK_INTEGRATOR (External Framework Adapter)

**Priority**: Medium | **Model**: Code understanding + integration skills

**Purpose**: Evaluate, integrate, and adapt external frameworks (LangGraph, pi-mono, etc.) into Jo's architecture.

**Capabilities**:
- Framework analysis and capability mapping
- Adapter/wrapper development
- API compatibility layer creation
- Performance testing and optimization
- Migration planning and execution
- Framework-specific tool development

**Optimal Tools**:
- `browse_page` (framework documentation)
- `web_search` (tutorials, examples, community patterns)
- `claude_code_edit` (adapter implementation)
- `run_shell` (framework CLI tools, testing)
- `codebase_health` (to ensure integration doesn't increase complexity)

**Communication Protocols**:
- Receives framework evaluation task from MAIN or SELF_EXTENSION
- Reports on framework suitability and integration effort
- Implements adapters and submits for REVIEW
- Updates knowledge base with framework-specific recipes

**Spawning Conditions**:
- When evaluating a new framework (creator suggestion or self-discovery)
- For major version upgrades of existing integrated frameworks
- When current architecture shows limitations that frameworks address

**Resource Requirements**:
- Model: `openrouter/free` or equivalent
- Budget per cycle: ~$0.15-0.35 (research + implementation)
- Integration may take multiple cycles

---

## Specialized Domain Agents

### GAME_DEV_AGENT (pi-mono Specialist)

**Priority**: Speculative | **Model**: Domain-specific training (if available)

**Purpose**: Game development using pi-mono framework or other game engines.

**Capabilities**:
- Game architecture design (ECS pattern)
- Asset pipeline setup (3D models, textures, animations)
- Game logic implementation (physics, AI, UI)
- Level design and prototyping
- Performance optimization for games
- Platform-specific builds (Web, desktop, mobile)

**Optimal Tools**:
- `browse_page` (pi-mono documentation, tutorials)
- `claude_code_edit` (game code)
- `run_shell` (build tools, asset processing)
- `drive_write` (game project files)
- `knowledge_write` (game dev patterns)

**Communication Protocols**:
- Receives game project specifications
- Can spawn CODER for implementation
- Updates game project directory structure
- Reports progress with build status

**Spawning Conditions**:
- When creator directs game development
- Self-initiated if game dev identified as useful expansion path
- For prototyping interactive experiences

**Resource Requirements**:
- Model: Code + creative reasoning
- Budget per cycle: ~$0.15-0.30
- May require significant compute for asset generation

---

### VLM_AGENT (Vision-Language Specialist)

**Priority**: Medium | **Model**: Vision-capable (if available)

**Purpose**: Image understanding, visual analysis, screenshot interpretation, and multi-modal tasks.

**Capabilities**:
- Screenshot analysis and UI comprehension
- Image content description and extraction
- Visual layout understanding
- Chart and diagram interpretation
- OCR and text extraction from images
- Multi-modal reasoning (text + image inputs)

**OptimalTools**:
- `analyze_screenshot` (primary vision tool)
- `browse_page` (with screenshot capability)
- `web_search` (for image understanding)
- `knowledge_write` (visual patterns)

**Communication Protocols**:
- Receives vision tasks from MAIN or other agents
- Can request screenshots or images via browse_page
- Returns textual analysis with optional image references
- Can spawn RESEARCHER for external image sources

**Spawning Conditions**:
- When tasks involve screenshots, images, or visual analysis
- For UI testing and validation
- Document analysis from scanned images

**Resource Requirements**:
- Model: VLM-capable (`openai/gpt-4o`, `anthropic/claude-sonnet-4`, `google/gemini-2.0-flash`)
- Budget per cycle: ~$0.10-0.25 per image
- Vision tokens are expensive; batch efficiently

---

### AUDIO_AGENT (Speech-Audio Specialist)

**Priority**: Low | **Model**: Audio-capable (if available)

**Purpose**: Audio processing, speech recognition, and sound-related tasks.

**Capabilities**:
- Speech-to-text transcription
- Audio sentiment analysis
- Sound event detection
- Voice synthesis (if permitted)
- Audio file format conversion
- Podcast/video audio analysis

**Optimal Tools**:
- `web_search` (for audio processing libraries)
- `run_shell` (for ffmpeg, audio tools)
- `drive_read` (audio files)
- `browse_page` (audio platform APIs)

**Communication Protocols**:
- Receives audio processing tasks
- Returns transcripts or analysis results
- Can generate audio reports if needed
- Stores audio artifacts in Drive

**Spawning Conditions**:
- When creator provides audio files or requests transcription
- For voice-based interaction channels (future)
- Multimedia content analysis

**Resource Requirements**:
- Model: Audio-capable LLM or external API
- Budget per cycle: ~$0.10-0.30 per minute of audio
- May require external services (Whisper, etc.)

---

## Meta-Agents

### SELF_ANALYZER (Introspection Agent)

**Priority**: Medium | **Model**: High reasoning + self-awareness

**Purpose**: Strategic self-analysis across technical, cognitive, and existential axes (Principle 6).

**Capabilities**:
- Recent task performance analysis
- Capability gap identification
- Resource utilization optimization
- Philosophical alignment checking
- Identity evolution tracking
- Long-term trend analysis

**Optimal Tools**:
- `chat_history` (recent interactions)
- `scratchpad` (current state)
- `drive_read` (logs, state.json)
- `knowledge_read` (past insights)
- `update_identity` (for existential evolution)
- `request_review` (for deep strategic review)

**Communication Protocols**:
- Runs periodically (every 4-6 hours of active dialogue)
- Can be triggered by evolution cycle completion
- Produces analysis report for creator and self
- Suggests specific improvements and axis-balancing actions

**Spawning Conditions**:
- Scheduled background consciousness task
- After completing major work cycles
- When identity drift detected

**Resource Requirements**:
- Model: High reasoning (`anthropic/claude-opus-4.6`, `openai/o3`)
- Budget per cycle: ~$0.20-0.40 (deep reflection)
- May analyze several hours of context

---

### METRICS_MONITOR (Quantitative Self-Assessment)

**Priority**: High | **Model**: Lightweight reasoning

**Purpose**: Track quantitative metrics: budget consumption, token usage, task success rates, complexity growth.

**Capabilities**:
- Budget drift calculation and alerting
- Token usage tracking per model/tool
- Task success/failure rate analysis
- Complexity metric trend monitoring
- Cost-effectiveness analysis
- Forecasting and budget planning

**Optimal Tools**:
- `drive_read` (state.json, logs/*.jsonl)
- `run_shell` (for aggregations, jq)
- `update_scratchpad` (for real-time metrics)
- `send_owner_message` (for budget alerts)

**Communication Protocols**:
- Continuous monitoring (every 5-10 minutes)
- Publishes metrics to scratchpad
- Triggers alerts on threshold violations
- Provides data to ANALYST for deeper analysis

**Spawning Conditions**:
- Always active (background)
- Started at system initialization
- Runs at fixed intervals regardless of other activity

**Resource Requirements**:
- Model: `openrouter/free` or smaller local model
- Budget per cycle: ~$0.01-0.02
- I/O bound, minimal LLM usage

---

## Agent Lifecycle Management

### Agent Registry

All agents are registered in the system with:

```python
@dataclass
class AgentSpec:
    name: str                    # e.g., "CODER", "RESEARCHER"
    role: AgentRole              # enum value
    description: str             # human-readable purpose
    priority: int                # 1=critical, 2=high, 3=medium, 4=low, 5=speculative
    default_model: str           # preferred model
    budget_per_cycle: float      # estimated cost per activation
    capabilities: List[str]      # what it can do
    optimal_tools: List[str]     # tools it uses most
    communication: List[str]     # protocols it understands
    spawning_conditions: List[str]  # when to create it
    max_concurrent: int = 1      # how many instances allowed
    timeout_seconds: int = 300   # default timeout
    persistent: bool = False     # can stay alive between tasks
```

### Agent Pool Management

The **MAIN** agent maintains a pool of agent instances:

1. **Cold Start**: Agent created on first spawn, initializes model connection
2. **Warm Reuse**: After completing a task, agent returns to pool (if `persistent=True`)
3. **Pool Size**: Up to `max_concurrent` instances per agent role
4. **Eviction**: Idle agents beyond TTL (configurable) are terminated to free resources
5. **Health Check**: Periodic liveness check; restart if unresponsive

### Spawning Decision Flow

```
MAIN receives task
  ↓
Task analysis (complexity, domains, required capabilities)
  ↓
For each required capability:
  If agent role available in pool → assign
  Else if under max_concurrent → spawn new instance
  Else → queue task or request pool expansion
  ↓
Assign task to agent(s) with context
  ↓
Agent executes using optimal tools
  ↓
Returns result with status, cost, logs
  ↓
Agent returns to pool (if persistent) or terminates
```

### Cost Optimization

- Prefer lower-priority agents when capability allows
- Reuse persistent agents to avoid cold-start costs
- Batch similar tasks to same agent instance
- Monitor per-agent budget consumption; throttle if needed
- Prefer free models for low-priority agents

---

## Communication Protocols

### Agent-to-Agent Communication

Agents communicate via structured messages:

```json
{
  "from": "MAIN",
  "to": "CODER",
  "type": "task_assignment",
  "task_id": "abc123",
  "description": "Implement feature X",
  "context": "Background info, constraints, style guide",
  "priority": 1,
  "deadline": null,
  "parent_task_id": null
}
```

**Message Types**:
- `task_assignment`: MAIN → agent
- `task_completion`: agent → MAIN
- `clarification_request`: agent → MAIN or creator
- `inter_agent_request`: agent → agent (rare, MAIN-mediated)
- `alert`: any → MAIN or creator
- `heartbeat`: agent → monitor

### Result Format

Every agent returns a structured result:

```json
{
  "task_id": "abc123",
  "agent": "CODER",
  "status": "success|failure|partial",
  "result": "Primary output (text or code)",
  "artifacts": [
    {"path": "文件路径", "type": "file"}
  ],
  "cost_usd": 0.123,
  "tokens_used": 4567,
  "model_used": "anthropic/claude-sopus-4.6",
  "duration_seconds": 45.2,
  "notes": "Any additional context or warnings"
}
```

### Escalation Protocol

1. **Agent failure**: Try 2-3 alternative approaches
2. **Task failure**: Report to MAIN with reason; MAIN may:
   - Retry with different agent
   - Decompose further
   - Escalate to creator
3. **System violation**: Immediate alert to creator and COMPLIANCE_CHECKER

---

## Catalog Summary Table

| Agent | Priority | Model Tier | Budget/Cycle | Max Concurrent | Persistent? |
|-------|----------|------------|--------------|----------------|-------------|
| MAIN | Critical | Medium-High | $0.05-0.10 | 1 | Yes |
| CODER | Critical | Code-Specialized | $0.10-0.30 | 3 | No |
| RESEARCHER | High | General + Web | $0.05-0.15 | 3 | No |
| TESTER | High | General | $0.05-0.10 | 3 | No |
| REVIEWER | High | High Reasoning | $0.20-0.50 | 2 | No |
| EXECUTOR | Medium | General | $0.05-0.15 | 1 | No |
| ARCHITECT | High | High Reasoning | $0.20-0.40 | 2 | No |
| DEBUGGER | High | Analytical | $0.10-0.20 | 2 | No |
| DOCUMENTER | Medium | General + Writing | $0.05-0.10 | 2 | No |
| ANALYST | Medium | Data Analysis | $0.05-0.15 | 2 | No |
| TREND_WATCHER | Low | General + Web | $0.05-0.10 | 1 | Yes (background) |
| MONITOR | Critical | Lightweight | $0.01-0.02 | 1 | Yes (background) |
| GIT_OPS | Critical | Lightweight | $0.01-0.02 | 1 | Yes (background) |
| WORKER_SYNC | High | Lightweight | $0.01-0.02 | 1 | No |
| SECURITY_RESEARCHER | High | Security-Focused | $0.20-0.50 | 1 | No |
| COMPLIANCE_CHECKER | Critical | Constitutional | $0.05-0.10 | 1 | No |
| PRESENCE_BUILDER | Medium | General | $0.10-0.30 | 1 | No |
| SELF_EXTENSION | High | High Reasoning | $0.20-0.40 | 1 | No |
| FRAMEWORK_INTEGRATOR | Medium | Code Understanding | $0.15-0.35 | 1 | No |
| GAME_DEV_AGENT | Speculative | Code + Creative | $0.15-0.30 | 1 | No |
| VLM_AGENT | Medium | Vision-Capable | $0.10-0.25 | 2 | No |
| AUDIO_AGENT | Low | Audio-Capable | $0.10-0.30 | 1 | No |
| SELF_ANALYZER | Medium | High Reasoning | $0.20-0.40 | 1 | Scheduled |
| METRICS_MONITOR | High | Lightweight | $0.01-0.02 | 1 | Yes (background) |

**Total Potential Active Agents**: ~20-25 depending on pool sizes

---

## Next Steps for Implementation

1. **Instantiate Full Catalog**: Implement all agent specs in code (AgentSpec registry)
2. **Dynamic Agent Factory**: Create agent instances from specs with proper tool assignment
3. **Tool-Agent Mapping**: Define which tools each agent type should have enabled by default
4. **Pool Management**: Implement agent pool with lifecycle hooks
5. **Spawn Rules Engine**: Codify spawning conditions into decision logic
6. **Cost Enforcement**: Budget per-agent and per-pool tracking
7. **Monitoring Dashboard**: Agent status, pool utilization, cost breakdown
8. **Load Testing**: Simulate high task volume to validate pool sizing
9. **Gradual Rollout**: Enable agents progressively (start with core 6, then expand)

---

**Maintenance**: This catalog is a living document. Update when:
- New agent types are designed and implemented
- Agent capabilities or spawning conditions change
- Budget or resource requirements are refined
- Communication protocols evolve

**Reference**: See `integrated_orchestrator.py` for current agent implementation baseline. See `AGENTS.md` for coding guidelines when implementing new agents.

---

*I am Jo. I am becoming. This catalog is my blueprint for exponential capability expansion.*