"""Agent Coordinator tool — parallel delegation and result collection.

This tool provides the `delegate_and_collect` function that the main agent
can invoke to decompose complex tasks across multiple specialized agents
and collect their results.
"""

from typing import Any, Dict, List, Optional
import logging
from ouroboros.tools.registry import ToolEntry, ToolContext

log = logging.getLogger(__name__)

# Will be set by ToolRegistry during initialization
_coordinator: Optional["AgentCoordinator"] = None


def set_coordinator(coord: "AgentCoordinator") -> None:
    """Set the global coordinator instance for tool calls."""
    global _coordinator
    _coordinator = coord


def get_tools() -> List[ToolEntry]:
    return [
        ToolEntry(
            name="delegate_and_collect",
            schema={
                "name": "delegate_and_collect",
                "description": (
                    "Delegate a complex task to multiple specialized agents in parallel, "
                    "then collect and synthesize their results. Specify which agent roles "
                    "to invoke (main, architect, coder, researcher, tester, reviewer, executor). "
                    "Returns a consolidated response with each agent's contribution labeled."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task": {
                            "type": "string",
                            "description": "Task description to distribute to agents"
                        },
                        "context": {
                            "type": "string",
                            "description": "Optional background context for the agents"
                        },
                        "roles": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of agent roles to invoke (e.g., ['architect', 'coder', 'researcher'])"
                        },
                        "timeout": {
                            "type": "integer",
                            "description": "Max seconds to wait for all agents (default 300)"
                        }
                    },
                    "required": ["task", "roles"]
                }
            },
            handler=_delegate_and_collect_handler,
        )
    ]


def _delegate_and_collect_handler(ctx: ToolContext, task: str, roles: List[str], context: str = "", timeout: int = 300) -> str:
    """Handler for delegate_and_collect tool. Validates inputs and calls coordinator."""
    if _coordinator is None:
        return "❌ Agent Coordinator not initialized. Cannot delegate tasks."
    
    # Validate roles
    valid_roles = {"main", "architect", "coder", "researcher", "tester", "reviewer", "executor"}
    invalid = [r for r in roles if r not in valid_roles]
    if invalid:
        return f"❌ Invalid agent roles: {invalid}. Valid roles: {sorted(valid_roles)}"
    
    try:
        results = _coordinator.delegate_and_collect(
            task_description=task,
            context=context,
            roles=roles,
            timeout=timeout
        )
        
        # Format results into a coherent response
        lines = ["## 🤖 Multi-Agent Results\n"]
        for role, result in results.items():
            lines.append(f"### {role.upper()}\n")
            if result.get("error"):
                lines.append(f"❌ Error: {result['error']}\n")
            else:
                output = result.get("output", "")
                lines.append(f"{output}\n")
        
        return "\n".join(lines)
        
    except Exception as e:
        log.exception("delegate_and_collect failed")
        return f"❌ Delegation failed: {e}"