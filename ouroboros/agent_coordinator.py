"""
Agent Coordinator: Delegates tasks to specialized agents and collects results.

Provides a simple `delegate_and_collect(task_description, context=None)` function
that:
1. Analyzes the task to determine which agent roles are needed
2. Spawns subtasks for each identified role via schedule_task
3. Waits for all subtasks to complete (with timeout)
4. Assembles results into a coherent response
5. Returns synthesized output

This is the "manager" that coordinates parallel agent work.
"""

import logging
import time
from typing import Any, Dict, List, Optional

from supervisor.queue import schedule_task, wait_for_task, get_task_result

log = logging.getLogger(__name__)


class AgentCoordinator:
    """Coordinates multiple agents to work on a complex task."""

    def __init__(self):
        self._task_results: Dict[str, Any] = {}

    def delegate_and_collect(
        self,
        task_description: str,
        context: Optional[str] = None,
        agent_roles: Optional[List[str]] = None,
        timeout: float = 300.0
    ) -> Dict[str, Any]:
        """
        Delegate a task to multiple agents and collect their results.

        Args:
            task_description: The main task to accomplish
            context: Optional background context to pass to agents
            agent_roles: Specific agent roles to use (default: auto-detect)
            timeout: Maximum time to wait for all agents (seconds)

        Returns:
            Dictionary with:
                - success: bool (true if all agents succeeded)
                - results: dict mapping agent role -> result
                - synthesis: synthesized final response
                - errors: list of any errors encountered
                - agent_roles: list of roles used
                - elapsed_time: time taken in seconds
        """
        # Determine which agents to use
        if agent_roles is None:
            agent_roles = self._identify_required_agents(task_description)

        if not agent_roles:
            return {
                "success": False,
                "error": "No suitable agents identified for task",
                "results": {},
                "synthesis": "",
                "agent_roles": [],
                "elapsed_time": 0.0
            }

        log.info(f"Delegating task to agents: {agent_roles}")

        # Spawn subtasks
        task_ids = {}
        for role in agent_roles:
            subtask_desc = self._build_subtask_prompt(role, task_description, context)
            task_id = schedule_task(
                description=subtask_desc,
                context=f"Agent Role: {role}\nMain Task: {task_description}\nContext: {context or 'None'}"
            )
            task_ids[role] = task_id
            log.info(f"Spawned {role} agent with task {task_id}")

        # Wait for all tasks to complete
        results = {}
        errors = []
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            all_done = True
            for role, task_id in task_ids.items():
                if role not in results:
                    status = wait_for_task(task_id, timeout=1)
                    if status.get("status") == "completed":
                        results[role] = get_task_result(task_id)
                    elif status.get("status") == "failed":
                        errors.append(f"{role} failed: {status.get('error')}")
                        results[role] = {"error": status.get('error')}
                    elif status.get("status") == "still running":
                        all_done = False
                    else:
                        all_done = False
            
            if all_done:
                break
            
            time.sleep(1)

        elapsed = time.time() - start_time

        # Synthesize final response
        synthesis = self._synthesize_results(task_description, results)

        return {
            "success": len(errors) == 0,
            "results": results,
            "synthesis": synthesis,
            "errors": errors,
            "agent_roles": agent_roles,
            "elapsed_time": round(elapsed, 2)
        }

    def _identify_required_agents(self, task_description: str) -> List[str]:
        """Analyze task to determine which agent roles are needed."""
        needed = []
        desc_lower = task_description.lower()

        # Check for specific needs
        if any(kw in desc_lower for kw in ['research', 'find', 'lookup', 'gather', 'information', 'search']):
            needed.append('researcher')
        
        if any(kw in desc_lower for kw in ['code', 'write', 'implement', 'develop', 'function', 'class', 'script']):
            needed.append('coder')
        
        if any(kw in desc_lower for kw in ['test', 'verify', 'check', 'validate', 'unit test', 'integration test']):
            needed.append('tester')
        
        if any(kw in desc_lower for kw in ['review', 'improve', 'refactor', 'optimize', 'critique']):
            needed.append('reviewer')
        
        if any(kw in desc_lower for kw in ['execute', 'run', 'deploy', 'install', 'setup']):
            needed.append('executor')
        
        # Architect/main for complex tasks or when multiple agents needed
        if len(needed) > 1:
            if 'architect' not in needed:
                needed.insert(0, 'architect')
        elif not needed:
            needed.append('main')

        # Remove duplicates while preserving order
        seen = set()
        unique_needed = []
        for role in needed:
            if role not in seen:
                seen.add(role)
                unique_needed.append(role)
        
        return unique_needed

    def _build_subtask_prompt(self, role: str, main_task: str, context: Optional[str]) -> str:
        """Build a specialized prompt for each agent role."""
        role_prompts = {
            'architect': (
                "You are the ARCHITECT agent. Your role is to design and plan the solution.\n"
                "Deliverable: A clear, structured design document.\n\n"
                "For the given task, provide:\n"
                "1. High-level design and architecture\n"
                "2. Key components and their relationships (diagram in text if helpful)\n"
                "3. Any patterns or principles to follow\n"
                "4. Potential risks or challenges\n"
                "5. Estimated steps or phases\n"
                "6. Interfaces between components\n\n"
                "Task: {task}\n"
                "Context: {context}"
            ),
            'coder': (
                "You are the CODER agent. Write clean, functional, production-ready code.\n"
                "Deliverable: Complete code implementation with explanation.\n\n"
                "For the given task:\n"
                "1. Implement the required functionality\n"
                "2. Include all necessary imports\n"
                "3. Add docstrings and comments\n"
                "4. Follow existing code style and conventions\n"
                "5. Handle errors gracefully\n"
                "6. Provide usage examples if applicable\n\n"
                "Task: {task}\n"
                "Context: {context}"
            ),
            'researcher': (
                "You are the RESEARCHER agent. Gather and synthesize information thoroughly.\n"
                "Deliverable: A research report with findings, sources, and insights.\n\n"
                "For the given task:\n"
                "1. Find relevant facts, data, or precedents\n"
                "2. Use web search if needed (call tool)\n"
                "3. Cross-validate sources\n"
                "4. Provide citations or references\n"
                "5. Summarize key insights and implications\n"
                "6. Note any uncertainties or gaps\n\n"
                "Task: {task}\n"
                "Context: {context}"
            ),
            'tester': (
                "You are the TESTER agent. Ensure quality and correctness.\n"
                "Deliverable: Test plan and/or test code with results.\n\n"
                "For the given task:\n"
                "1. Identify test cases (unit, integration, edge cases)\n"
                "2. Write test code or test procedures\n"
                "3. Define expected outcomes\n"
                "4. Check for regressions if applicable\n"
                "5. Suggest improvements based on testing\n"
                "6. Report pass/fail status\n\n"
                "Task: {task}\n"
                "Context: {context}"
            ),
            'reviewer': (
                "You are the REVIEWER agent. Evaluate and improve code/design.\n"
                "Deliverable: Structured review with actionable feedback.\n\n"
                "For the given task/code:\n"
                "1. Review for bugs, security, performance\n"
                "2. Check adherence to best practices and standards\n"
                "3. Suggest specific refactorings with rationale\n"
                "4. Rate overall quality (1-10)\n"
                "5. Prioritize issues (critical/major/minor)\n"
                "6. Provide code snippets for improvements\n\n"
                "Task: {task}\n"
                "Context: {context}"
            ),
            'executor': (
                "You are the EXECUTOR agent. Run and verify operations.\n"
                "Deliverable: Execution report with outputs and status.\n\n"
                "For the given task:\n"
                "1. Execute commands or code (use appropriate tools)\n"
                "2. Capture full output and errors\n"
                "3. Verify results match expectations\n"
                "4. Clean up if needed (temporary files, etc.)\n"
                "5. Report success/failure with evidence\n"
                "6. Note any environment-specific issues\n\n"
                "Task: {task}\n"
                "Context: {context}"
            ),
            'main': (
                "You are the MAIN agent. Handle general tasks independently.\n"
                "Deliverable: Complete, direct response to the task.\n\n"
                "Provide a thorough answer or solution. Use tools if helpful.\n\n"
                "Task: {task}\n"
                "Context: {context}"
            ),
        }

        template = role_prompts.get(role, role_prompts['main'])
        return template.format(task=main_task, context=context or "No additional context.")

    def _synthesize_results(
        self,
        main_task: str,
        results: Dict[str, Any]
    ) -> str:
        """Combine agent results into a coherent final response."""
        lines = [f"# Coordinated Agent Response\n\n**Task:** {main_task}\n"]
        
        for role, result in results.items():
            lines.append(f"## {role.upper()} Agent\n")
            if isinstance(result, dict):
                # Try to extract meaningful content
                if 'error' in result:
                    lines.append(f"❌ **Error:** {result['error']}\n")
                elif 'content' in result:
                    content = result['content']
                    lines.append(str(content))
                elif 'result' in result:
                    lines.append(str(result['result']))
                elif 'code' in result:
                    lines.append("```\n" + result['code'] + "\n```")
                elif 'findings' in result:
                    lines.extend(str(f) for f in result['findings'])
                elif 'test_results' in result:
                    lines.append(str(result['test_results']))
                elif 'review' in result:
                    lines.append(str(result['review']))
                else:
                    # Fallback: dump the dict nicely
                    lines.append("```json\n" + str(result) + "\n```")
            else:
                lines.append(str(result))
            lines.append("")  # blank line

        # Add summary
        lines.append("## Summary\n")
        success_count = sum(1 for r in results.values() if not (isinstance(r, dict) and r.get('error')))
        total_count = len(results)
        lines.append(f"- **Agents consulted:** {total_count}")
        lines.append(f"- **Successful responses:** {success_count}/{total_count}")
        
        if total_count > 0:
            lines.append(f"- **Roles:** {', '.join(results.keys())}")
        
        return "\n".join(lines)


def delegate_and_collect(
    task_description: str,
    context: Optional[str] = None,
    agent_roles: Optional[List[str]] = None,
    timeout: float = 300.0
) -> Dict[str, Any]:
    """
    Convenience function to delegate a task to multiple agents and collect results.
    
    Example:
        result = delegate_and_collect(
            "Build a web scraper",
            context="Needs to handle JavaScript",
            agent_roles=['architect', 'coder', 'tester']
        )
        print(result['synthesis'])
    """
    coordinator = AgentCoordinator()
    return coordinator.delegate_and_collect(task_description, context, agent_roles, timeout)
