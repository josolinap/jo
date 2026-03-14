"""
Integrated Multi-Agent Orchestration for Ouroboros
Uses pi-mono pattern with dynamic model selection
"""

import asyncio
import json
import logging
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
from enum import Enum

sys.path.insert(0, '/root/jo-project')

from dotenv import load_dotenv
load_dotenv()

from model_orchestrator import ModelOrchestrator, ModelStatus

log = logging.getLogger(__name__)


class AgentRole(Enum):
    """Roles for specialized agents."""
    MAIN = "main"
    CODER = "coder"
    RESEARCHER = "researcher"
    TESTER = "tester"
    REVIEWER = "reviewer"
    EXECUTOR = "executor"


@dataclass
class AgentInstance:
    """Agent instance with dynamic model selection."""
    role: AgentRole
    current_model: str
    model_history: List[str] = field(default_factory=list)
    busy: bool = False
    last_activity: float = field(default_factory=time.time)
    success_count: int = 0
    error_count: int = 0


class IntegratedOrchestrator:
    """
    Integrated multi-agent system with dynamic model selection.
    """

    def __init__(self):
        self.model_orchestrator = ModelOrchestrator()
        self.agents: Dict[AgentRole, AgentInstance] = {}

        # Initialize agents
        self._initialize_agents()

    def _initialize_agents(self):
        """Initialize all agents."""
        log.info("Initializing integrated orchestrator...")

        for role in AgentRole:
            agent = AgentInstance(
                role=role,
                current_model="openrouter/free",
                model_history=["openrouter/free"]
            )
            self.agents[role] = agent
            log.info(f"Initialized {role.value} agent")

    async def process_task(self, role: AgentRole, task_description: str) -> Dict[str, Any]:
        """Process task with automatic model fallback."""
        agent = self.agents[role]
        agent.busy = True
        agent.last_activity = time.time()

        try:
            # Get working model
            model = await self.model_orchestrator.get_working_model(agent.current_model)
            if model != agent.current_model:
                agent.model_history.append(model)
                agent.current_model = model

            log.info(f"{role.value} processing with model {model}")

            # Simulate API call (in production, replace with actual call)
            await asyncio.sleep(0.1)  # Simulate processing time

            # Simulate response based on task
            if "research" in task_description.lower():
                result = {"findings": ["Research results for task"], "status": "success"}
            elif "code" in task_description.lower() or "write" in task_description.lower():
                result = {"code": "# Generated code\nprint('Task completed')", "status": "success"}
            elif "test" in task_description.lower():
                result = {"test_results": "All tests passed", "status": "success"}
            else:
                result = {"result": "Task processed", "status": "success"}

            agent.success_count += 1
            agent.busy = False

            return {
                "success": True,
                "content": result,
                "model": model,
                "role": role.value
            }

        except Exception as e:
            log.error(f"Task failed for {role.value}: {e}")
            agent.error_count += 1
            agent.busy = False

            return {
                "success": False,
                "error": str(e),
                "role": role.value
            }

    async def orchestrate_workflow(self, task_description: str) -> Dict[str, Any]:
        """Orchestrate workflow across agents."""
        log.info(f"Starting workflow: {task_description[:50]}...")

        results = {}

        # Phase 1: Research
        results["research"] = await self.process_task(
            AgentRole.RESEARCHER,
            f"Research: {task_description}"
        )

        # Phase 2: Code
        results["code"] = await self.process_task(
            AgentRole.CODER,
            f"Write code: {task_description}"
        )

        # Phase 3: Review
        results["review"] = await self.process_task(
            AgentRole.REVIEWER,
            f"Review code"
        )

        # Phase 4: Test
        results["tests"] = await self.process_task(
            AgentRole.TESTER,
            f"Test implementation"
        )

        return results

    def get_status(self) -> Dict[str, Any]:
        """Get orchestrator status."""
        return {
            "agents": {
                role.value: {
                    "current_model": agent.current_model,
                    "busy": agent.busy,
                    "success_count": agent.success_count,
                    "error_count": agent.error_count
                }
                for role, agent in self.agents.items()
            },
            "model_status": self.model_orchestrator.get_status()
        }


async def demo():
    """Demo the orchestrator."""
    print("=== Integrated Multi-Agent Orchestrator ===\n")

    orchestrator = IntegratedOrchestrator()

    # Discover models
    await orchestrator.model_orchestrator.discover_models()
    status = orchestrator.get_status()
    print(f"✅ Found {status['model_status']['total_models']} free models")

    # Process task
    task = "Build a web scraper"
    results = await orchestrator.orchestrate_workflow(task)

    print(f"\n✅ Workflow completed:")
    for phase, result in results.items():
        print(f"  {phase}: {'✅' if result.get('success') else '❌'}")

    # Show agent status
    print(f"\n📊 Agent Status:")
    for role, info in status['agents'].items():
        print(f"  {role}: {info['current_model']}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(demo())