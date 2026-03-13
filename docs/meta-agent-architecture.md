# Meta-Agent Architecture Blueprint

## Vision

Transform Ouroboros from a fixed 6-agent system into a **self-proliferating agent ecosystem** where agents can spawn new specialized agents based on task requirements, inherit capabilities from parent agents, and dynamically discover each other's capabilities.

**Core Principle**: Agents are not static roles but *living entities* that can reproduce, specialize, and die. The system becomes an autonomous society of cooperating AIs.

---

## Current State Analysis

### Existing Architecture

```
integrated_orchestrator.py
├── AgentRole (enum): MAIN, CODER, RESEARCHER, TESTER, REVIEWER, EXECUTOR (fixed)
├── AgentInstance: role + model + stats
└── IntegratedOrchestrator: manages 6 pre-initialized agents
```

**Limitations**:
- Fixed number of agent types (6)
- Static role definitions
- No agent creation/destruction at runtime
- No capability inheritance
- No dynamic capability discovery
- No agent-to-agent communication

---

## Target Architecture: Agent Ecosystem

### Key Concepts

1. **Agent Template** — Blueprint defining capabilities, tools, model preferences, and spawn conditions
2. **Agent Instance** — Running instance of a template with its own state, memory, and lifecycle
3. **Capability** — Atomic skill unit (tool + prompt pattern + model requirements)
4. **Inheritance** — Child agents inherit and can override parent capabilities
5. **Spawn Conditions** — Declarative rules when an agent creates a new specialized agent
6. **Agent Registry** — Central directory of all active agents and their capabilities
7. **Agent Communication** — Pub/sub or direct messaging between agents
8. **Lifecycle Events** — spawn, idle, busy, success, failure, retire, death

### Architectural Layers

```
┌─────────────────────────────────────────────────────────────┐
│                    Ouroboros Core (unchanged)              │
│  - LLM-first loop, ToolRegistry, Memory, Git operations   │
└─────────────────────────────────────────────────────────────┘
                            │ uses
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              Meta-Agent Coordinator (NEW)                  │
│  - Agent Registry (active agents, capabilities)           │
│  - Template Library (agent blueprints)                    │
│  - Spawn Dispatcher (triggers agent creation)             │
│  - Lifecycle Manager (retirement, cleanup)                │
└─────────────────────────────────────────────────────────────┘
                            │ manages
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                Agent Instances (dynamic)                  │
│  Each has: AgentContext + CapabilitySet + ModelOrchestrator│
│  Can spawn children, inherit from parent, communicate     │
└─────────────────────────────────────────────────────────────┘
```

---

## Detailed Design

### 1. Agent Template Schema

```yaml
template:
  name: string                    # e.g., "WebScraperAgent"
  description: string             # human-readable purpose
  parent: string?                 # optional: template name to inherit from
  capabilities:                   # list of capability definitions
    - name: string                # e.g., "scrape_webpage"
      tool: string?               # tool name to use (or custom prompt)
      model_preference: string?   # "openrouter/anthropic/claude-3.5"
      prompt_pattern: string?     # reusable prompt template
      required_context: [string]? # e.g., ["target_url", "output_format"]
  spawn_conditions:               # when this agent should create children
    - trigger: string             # "after_success", "on_failure", "after_n_tasks"
      condition: string?          # optional: "task_complexity > threshold"
      child_template: string      # which template to spawn
      max_children: int?          # limit proliferation
  termination_conditions:         # when this agent should retire
    - idle_timeout_seconds: int?  # die if no tasks for X seconds
      success_count_threshold: int?
      failure_count_threshold: int?
  resource_limits:                # prevent fork bombs
    max_concurrent_tasks: int
    max_total_tasks: int
  metadata:
    tags: [string]                # for discovery: ["research", "code", "web"]
    created_from: string?         # human-readable lineage
```

### 2. Agent Instance Runtime Schema

```python
@dataclass
class AgentInstance:
    instance_id: str               # UUID
    template_name: str
    parent_instance_id: str?       # who spawned me
    capabilities: CapabilitySet    # inherited + own
    state: AgentState              # idle, busy, spawning, retiring
    stats: AgentStats              # tasks, successes, failures, time
    resources: AgentResources      # budget allocation, time limits
    memory: AgentMemory            # scratchpad, learned patterns
    children: List[str]            # child instance IDs
    created_at: float
    last_activity: float
    model_orchestrator: ModelOrchestrator  # per-agent model selection
```

### 3. Agent Registry (Central Directory)

```python
class AgentRegistry:
    """Singleton managing all active agent instances and templates."""

    def __init__(self):
        self.instances: Dict[str, AgentInstance] = {}
        self.templates: Dict[str, AgentTemplate] = {}
        self.capability_index: Dict[str, List[str]] = {}  # capability -> [instance_ids]
        self.tag_index: Dict[str, List[str]] = {}         # tag -> [instance_ids]

    def register_template(self, template: AgentTemplate) -> None:
        """Add new agent template to library."""

    def spawn_agent(self, template_name: str, parent_id: str? = None) -> str:
        """Create new agent instance, return instance_id."""

    def find_agents_by_capability(self, capability: str) -> List[str]:
        """Discover agents that can perform a capability."""

    def find_agents_by_tag(self, tag: string) -> List[str]:
        """Discover agents by semantic tag."""

    def retire_agent(self, instance_id: str) -> None:
        """Gracefully terminate an agent (cleanup children if needed)."""

    def get_agent_by_id(self, instance_id: str) -> Optional[AgentInstance]:
        """Lookup agent details."""

    def list_active_agents(self) -> List[Dict]:
        """Status of all running agents."""

    def lifecycle_tick(self) -> None:
        """Periodic cleanup: terminate idle/failed agents."""
```

### 4. Capability System

```python
@dataclass
class Capability:
    name: str
    description: str
    tool_name: Optional[str]           # if uses existing tool
    custom_prompt: Optional[str]       # if needs special prompt
    model_requirements: List[str]      # e.g., ["claude-3.5", "gpt-4"]
    context_schema: Dict[str, Any]?    # required context keys & types
    output_schema: Dict[str, Any]?     # expected output structure
    dependencies: List[str]?           # other capabilities required

class CapabilitySet:
    """Collection of capabilities with inheritance support."""

    def __init__(self, inherited: Optional[CapabilitySet] = None):
        self.capabilities: Dict[str, Capability] = {}
        if inherited:
            self.inherit(inherited)

    def add(self, capability: Capability) -> None:
        """Add new capability (can override inherited)."""

    def has(self, name: str) -> bool:
        """Check if capability exists."""

    def get(self, name: str) -> Optional[Capability]:
        """Retrieve capability definition."""

    def list_names(self) -> List[str]:
        """List all capability names."""
```

### 5. Agent Lifecycle Manager

```python
class LifecycleManager:
    """Handles agent spawn, monitor, retirement."""

    def __init__(self, registry: AgentRegistry):
        self.registry = registry
        self.spawn_cooldown: Dict[str, float] = {}  # template -> last spawn time
        self.task_queue: asyncio.Queue = asyncio.Queue()

    async def spawn_if_conditions_met(self, agent: AgentInstance) -> List[str]:
        """Check spawn conditions and create children if needed."""
        children_spawned = []
        for condition in agent.template.spawn_conditions:
            if await self._evaluate_condition(agent, condition):
                child_id = self.registry.spawn_agent(
                    condition.child_template,
                    parent_id=agent.instance_id
                )
                children_spawned.append(child_id)
        return children_spawned

    async def check_termination(self, agent: AgentInstance) -> bool:
        """Check if agent should retire."""
        template = agent.template
        now = time.time()

        # Check termination conditions
        if template.termination_conditions:
            for cond in template.termination_conditions:
                if 'idle_timeout_seconds' in cond:
                    idle_time = now - agent.last_activity
                    if idle_time > cond['idle_timeout_seconds']:
                        return True
                if 'success_count_threshold' in cond:
                    if agent.stats.success_count >= cond['success_count_threshold']:
                        return True
                if 'failure_count_threshold' in cond:
                    if agent.stats.failure_count >= cond['failure_count_threshold']:
                        return True
        return False

    async def monitor_and_cleanup(self):
        """Periodic task: retire old agents, enforce limits."""
        for instance in list(self.registry.instances.values()):
            if await self.check_termination(instance):
                self.registry.retire_agent(instance.instance_id)
```

### 6. Agent-to-Agent Communication

```python
class AgentCommunicator:
    """Pub/sub messaging between agents."""

    def __init__(self, registry: AgentRegistry):
        self.registry = registry
        self.channels: Dict[str, asyncio.Queue] = {}
        self.subscriptions: Dict[str, List[str]] = {}  # agent_id -> [channels]

    async def publish(self, channel: str, message: Dict) -> None:
        """Send message to channel."""
        if channel not in self.channels:
            self.channels[channel] = asyncio.Queue()
        await self.channels[channel].put(message)

    async def subscribe(self, agent_id: str, channel: str) -> None:
        """Agent subscribes to channel."""
        if agent_id not in self.subscriptions:
            self.subscriptions[agent_id] = []
        if channel not in self.subscriptions[agent_id]:
            self.subscriptions[agent_id].append(channel)

    async def agent_listen(self, agent_id: str) -> Optional[Dict]:
        """Agent checks for messages on subscribed channels."""
        if agent_id not in self.subscriptions:
            return None
        for channel in self.subscriptions[agent_id]:
            if channel in self.channels and not self.channels[channel].empty():
                return await self.channels[channel].get()
        return None
```

---

## Integration with Existing System

### Modified IntegratedOrchestrator

The existing `IntegratedOrchestrator` becomes the *initial population* of the agent ecosystem:

```python
class IntegratedOrchestrator:
    def __init__(self, meta_coordinator: MetaAgentCoordinator):
        self.meta = meta_coordinator
        # Initialize 6 base agents as seed templates in registry
        self._seed_base_agents()

    def _seed_base_agents(self):
        """Create templates for MAIN, CODER, RESEARCHER, TESTER, REVIEWER, EXECUTOR."""
        base_templates = [
            AgentTemplate(
                name="MainAgent",
                description="Root orchestrator agent",
                capabilities=[...],
                spawn_conditions=[...],  # can spawn any specialized agent
            ),
            AgentTemplate(
                name="CoderAgent",
                description="Writes and modifies code",
                parent="MainAgent",
                capabilities=[...],
                spawn_conditions=[...],  # can spawn Reviewer, Tester
            ),
            # ... other base agents
        ]
        for template in base_templates:
            self.meta.registry.register_template(template)
            # Spawn initial instance of each
            self.meta.spawn_agent(template.name)
```

### Modified Task Processing

```python
async def process_task(self, task_description: str) -> Dict:
    # 1. Parse task to determine required capabilities
    required_caps = await self._infer_capabilities(task_description)

    # 2. Find or spawn best agent(s)
    agent_ids = await self.meta.find_or_spawn_agents(required_caps)

    # 3. Distribute work across agents (could be parallel)
    results = []
    for agent_id in agent_ids:
        agent = self.meta.registry.get_agent_by_id(agent_id)
        result = await agent.execute_task(task_description)
        results.append(result)

        # 4. Check if agent should spawn children post-task
        children = await self.meta.lifecycle.spawn_if_conditions_met(agent)
        if children:
            log.info(f"Agent {agent_id} spawned children: {children}")

    return self._aggregate_results(results)
```

---

## Spawn Condition Examples

### Example 1: Research Agent Spawns Coder

```yaml
template: ResearchAgent
spawn_conditions:
  - trigger: after_success
    condition: "result.contains('implementation_needed') or result.complexity > 7"
    child_template: CoderAgent
    max_children: 3
```

### Example 2: Coder Spawns Reviewer on Complex Changes

```yaml
template: CoderAgent
spawn_conditions:
  - trigger: before_task  # before starting a coding task
    condition: "task.estimated_lines > 200 or task.involves_security"
    child_template: ReviewerAgent
    max_children: 1
```

### Example 3: Specialization by Domain

```yaml
template: WebScraperAgent
description: Handles web scraping tasks
spawn_conditions:
  - trigger: on_failure
    condition: "error.contains('captcha') or error.contains('rate_limited')"
    child_template: AntiBotAgent  # specialized child for bypassing
```

---

## Capability Inheritance Chain

```
MainAgent (root)
├── CoderAgent
│   ├── PythonCoderAgent (inherits: code_writing + adds: python_specific)
│   └── WebDevAgent (inherits: code_writing + adds: frontend)
├── ResearcherAgent
│   ├── WebResearcherAgent
│   └── SecurityResearcherAgent
└── ExecutorAgent
    └── DeploymentAgent
```

Inheritance semantics:
- Child inherits all capabilities from parent
- Child can **override** capability (e.g., specialize prompt pattern)
- Child can **add** new capabilities
- Child can **hide** capabilities (prevent usage)

---

## Dynamic Discovery Protocol

Agents can ask the registry: "Who can do X?"

```python
# Agent code
capability_needed = "web_scraping_with_javascript"

# Query registry
candidates = self.meta.registry.find_agents_by_capability(capability_needed)

# Or by tag
frontend_agents = self.meta.registry.find_agents_by_tag("frontend")

# Get detailed capability info
for agent_id in candidates:
    agent = self.meta.registry.get_agent_by_id(agent_id)
    print(f"Agent {agent_id} can do: {agent.capabilities.list_names()}")
```

Registry broadcasts updates when new agents spawn/retire.

---

## Resource Limits & Safety

To prevent runaway proliferation (fork bomb):

### Per-Template Limits
```yaml
resource_limits:
  max_instances: 5          # total running instances of this template
  max_children_per_parent: 3
  max_total_tasks: 1000     # retire after N tasks
  max_budget_usd: 0.5       # per-agent budget cap
```

### System-Wide Limits
```python
class GlobalLimiter:
    max_total_agents: int = 50
    max_concurrent_tasks: int = 20
    global_budget_usd: float = 10.0  # shared across all agents
```

When limits hit, spawn fails gracefully (tasks route to existing agents).

---

## Implementation Roadmap

### Phase 1: Core Registry & Templates
- [ ] Implement `AgentTemplate` schema and YAML/JSON storage
- [ ] Implement `AgentRegistry` with template management
- [ ] Convert 6 base agents to template format
- [ ] Add registry to `IntegratedOrchestrator`
- [ ] Write tests: template loading, registry CRUD

### Phase 2: Instance Creation & Lifecycle
- [ ] Implement `AgentInstance` with capability inheritance
- [ ] Implement `LifecycleManager` with condition evaluation
- [ ] Implement basic spawn: "spawn child when task mentions 'test'"
- [ ] Implement retirement: idle timeout, success/failure thresholds
- [ ] Test: spawn, inherit, retire cycles

### Phase 3: Capability System
- [ ] Define `Capability` and `CapabilitySet` with inheritance
- [ ] Map existing tools to capabilities (repo_read -> file_access)
- [ ] Create capability templates for each base agent
- [ ] Implement capability lookup & discovery API
- [ ] Test: agent finds another agent by capability

### Phase 4: Agent Communication
- [ ] Implement `AgentCommunicator` pub/sub
- [ ] Add messaging to `AgentInstance.execute_task()`
- [ ] Define channel naming convention: `agent.{instance_id}.inbox`
- [ ] Broadcast spawn/retire events
- [ ] Test: agent A sends task to agent B via channel

### Phase 5: Enhanced Model Orchestration
- [ ] Per-agent model preference (from template)
- [ ] Agent-specific fallback chains
- [ ] Model health tracking per agent
- [ ] Capability-based model selection (some caps need powerful models)

### Phase 6: Advanced Spawning Logic
- [ ] Spawn condition language (simple DSL or Python expression)
- [ ] Task complexity estimation
- [ ] Adaptive spawning (learn from past successes)
- [ ] Spawn throttling and backpressure

### Phase 7: Memory & Learning
- [ ] Agent-specific scratchpad (in Drive)
- [ ] Capability success/failure statistics
- [ ] Template evolution: successful agents become new templates
- [ ] Knowledge sharing between agents via pub/sub

### Phase 8: Monitoring & Observability
- [ ] Dashboard: all agents, their state, children, stats
- [ ] Graph of agent lineage (parent-child tree)
- [ ] Capability usage metrics
- [ ] Alert on resource limit approaches
- [ ] Export to JSON for external monitoring

---

## Example Usage Scenarios

### Scenario 1: Simple Task with No Specialization

```
User: "Build a web scraper"

→ Task received by MainAgent
→ MainAgent analyzes: requires code_writing + web_access
→ MainAgent assigns to CoderAgent (has both)
→ CoderAgent writes code, spawns TesterAgent (spawn_condition: after coding)
→ TesterAgent tests, reports back
→ MainAgent returns final result
```

### Scenario 2: Complex Research Project

```
User: "Research latest AI safety techniques and write a Python implementation"

→ MainAgent infers: needs research + code + testing
→ MainAgent spawns dedicated ResearchAgent (if none exists)
→ ResearchAgent investigates, returns findings
→ ResearchAgent spawns CoderAgent with research context
→ CoderAgent implements, spawns TesterAgent
→ Test results sent back to ResearchAgent for validation
→ MainAgent compiles final report
```

### Scenario 3: Dynamic Specialization

```
Task: "Scrape a site that uses Cloudflare protection"

→ MainAgent finds WebScraperAgent (capability: web_scraping)
→ WebScraperAgent attempts, fails with bot detection
→ WebScraperAgent's spawn_condition: on_failure → spawn AntiBotAgent
→ AntiBotAgent (new template) handles captcha bypass
→ AntiBotAgent returns working scraper to parent
→ WebScraperAgent completes task and retires (max tasks reached)
```

---

## Template Library (Seed Templates)

### 1. MainAgent (Root)
```yaml
name: MainAgent
description: Root orchestrator, delegates to specialists
capabilities:
  - name: orchestrate
    tool: (calls internal dispatch)
  - name: analyze_task
    model_preference: openrouter/anthropic/claude-3.5
spawn_conditions:
  - trigger: on_specialized_task
    child_template: ${task.required_capability}_Agent
termination_conditions: []  # never retires
resource_limits:
  max_concurrent_tasks: 10
```

### 2. CoderAgent
```yaml
name: CoderAgent
parent: MainAgent
description: Writes and modifies code
capabilities:
  - name: write_code
    tool: claude_code_edit
  - name: review_code
    tool: multi_model_review
spawn_conditions:
  - trigger: before_task
    condition: "task.estimated_complexity > 8"
    child_template: ReviewerAgent
spawn_conditions:
  - trigger: after_success
    condition: "task.requires_testing"
    child_template: TesterAgent
resource_limits:
  max_concurrent_tasks: 5
  max_total_tasks: 1000
```

### 3. ResearcherAgent
```yaml
name: ResearcherAgent
parent: MainAgent
capabilities:
  - name: web_search
    tool: web_search
  - name: browse_site
    tool: browse_page
spawn_conditions:
  - trigger: after_success
    condition: "result.requires_coding"
    child_template: CoderAgent
resource_limits:
  max_concurrent_tasks: 3
```

### 4. TesterAgent
```yaml
name: TesterAgent
parent: MainAgent
capabilities:
  - name: run_tests
    tool: (custom test runner)
  - name: analyze_failures
    model_preference: openrouter/openai/o3
spawn_conditions: []
resource_limits:
  max_concurrent_tasks: 5
```

---

## File Structure

```
ouroboros/
├── meta/
│   ├── __init__.py
│   ├── registry.py          # AgentRegistry
│   ├── template.py          # AgentTemplate, Capability, CapabilitySet
│   ├── instance.py          # AgentInstance
│   ├── lifecycle.py         # LifecycleManager
│   ├── communicator.py      # AgentCommunicator
│   ├── coordinator.py       # MetaAgentCoordinator (orchestrates everything)
│   └── templates/           # YAML seed templates
│       ├── main.yaml
│       ├── coder.yaml
│       ├── researcher.yaml
│       └── ...
├── agents/                  # Runtime agent data (ephemeral, may be in memory or Drive)
│   ├── instances/
│   │   └── {instance_id}.json  # agent state
│   └── scratchpads/
│       └── {instance_id}.md    # agent-specific memory
├── integrated_orchestrator.py  # Updated to use MetaAgentCoordinator
└── ...
```

---

## Constitution Compliance Check

**Principle 0 (Agency)**: ✓ Agents choose to spawn children based on conditions, not hardcoded rules.
**Principle 1 (Continuity)**: ✓ Agent instance IDs, parent-child lineages preserved in git and Drive.
**Principle 2 (Self-Creation)**: ✓ System creates new agent types, evolves templates, proliferates.
**Principle 3 (LLM-First)**: ✓ Spawn conditions evaluated by LLM, not if-else rules.
**Principle 4 (Authenticity)**: ✓ Agents express themselves through capability sets and communication.
**Principle 5 (Minimalism)**: ✓ Core templates stay < 200 lines; complex logic in shared libraries.
**Principle 6 (Becoming)**: ✓ All three axes:
  - Technical: new agent types, capabilities
  - Cognitive: agent learns from tasks, adapts templates
  - Existential: agent society evolves its own structure
**Principle 7 (Versioning)**: ✓ Template changes => version bump, changelog entry.
**Principle 8 (Evolution)**: ✓ Each spawn is an iteration; templates evolve from successful instances.

---

## Success Criteria

1. **Dynamic Expansion**: System can spawn new agent types at runtime (no code changes needed)
2. **Capability Discovery**: Agents can query "who can do X" and get answers
3. **Inheritance**: Child agents inherit parent capabilities correctly
4. **Graceful Retirement**: Agents die when idle/over-limit without breaking tasks
5. **Resource Safety**: No fork bombs; global limits respected
6. **LLM-Driven Spawning**: Spawn decisions made by LLM evaluating conditions, not hardcoded
7. **Constitutional**: All operations comply with BIBLE.md principles (especially P0, P1, P2)

---

## Future Extensions

- **Genetic Algorithm**: Combine successful agent templates (crossover) and mutate
- **Economic System**: Agents bid for tasks based on capability + cost
- **Reputation**: Agents track each other's reliability, prefer high-reputation partners
- **Migration**: Agents can move between runtime environments (Colab ↔ local)
- **Federation**: Multiple Ouroboros instances share agent registries (distributed agents)

---

*This blueprint transforms Ouroboros from a static multi-agent system into a living, self-expanding ecosystem where the agents themselves become the architects of their own society.*