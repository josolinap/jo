"""Supervisor tree for agent process management.

Erlang/OTP inspired supervision: one_for_one, one_for_all, rest_for_one.
Restart intensity limits prevent infinite crash loops.

Following Principle 5 (Minimalism): under 250 lines.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional

from ouroboros.resilience.backoff import backoff_with_jitter

log = logging.getLogger(__name__)


class RestartStrategy(Enum):
    """Supervision restart strategies."""

    ONE_FOR_ONE = "one_for_one"
    ONE_FOR_ALL = "one_for_all"
    REST_FOR_ONE = "rest_for_one"


class ChildType(Enum):
    """Child process types."""

    PERMANENT = "permanent"
    TEMPORARY = "temporary"
    TRANSIENT = "transient"


@dataclass
class SupervisedChild:
    """A supervised child process."""

    name: str
    worker_fn: Callable
    child_type: ChildType = ChildType.PERMANENT
    restart_count: int = 0
    last_restart: float = 0.0
    is_running: bool = False


@dataclass
class AgentSupervisor:
    """Supervises agent workers with configurable restart strategies.

    Implements Erlang/OTP supervision patterns:
    - one_for_one: restart only crashed child
    - one_for_all: restart all children when one crashes
    - rest_for_one: restart crashed child and dependents

    Usage:
        sup = AgentSupervisor(strategy=RestartStrategy.ONE_FOR_ONE)
        sup.add_child("llm_client", llm_worker_fn)
        sup.add_child("tool_executor", tool_worker_fn)
        await sup.start()
    """

    strategy: RestartStrategy = RestartStrategy.ONE_FOR_ONE
    max_restarts: int = 5
    window_seconds: float = 60.0
    children: Dict[str, SupervisedChild] = field(default_factory=dict)
    restart_counts: Dict[str, deque] = field(default_factory=lambda: defaultdict(deque))
    _running: bool = False
    _escalation_handler: Optional[Callable] = None

    def add_child(
        self,
        name: str,
        worker_fn: Callable,
        child_type: ChildType = ChildType.PERMANENT,
    ) -> None:
        """Add a child to supervision tree."""
        self.children[name] = SupervisedChild(
            name=name,
            worker_fn=worker_fn,
            child_type=child_type,
        )

    def set_escalation_handler(self, handler: Callable) -> None:
        """Set handler for when restart limits are exceeded."""
        self._escalation_handler = handler

    async def start(self) -> None:
        """Start supervision tree."""
        self._running = True
        log.info(f"Supervisor starting with {len(self.children)} children")

        for name, child in self.children.items():
            child.is_running = True
            log.info(f"Started child: {name}")

    async def handle_failure(self, child_name: str, error: Exception) -> None:
        """Handle child failure according to strategy."""
        if child_name not in self.children:
            log.warning(f"Unknown child: {child_name}")
            return

        child = self.children[child_name]

        # Check restart intensity
        now = time.time()
        window = self.restart_counts[child_name]
        window.append(now)
        while window and window[0] < now - self.window_seconds:
            window.popleft()

        if len(window) > self.max_restarts:
            await self._escalate(child_name, error)
            return

        # Apply restart strategy
        if self.strategy == RestartStrategy.ONE_FOR_ONE:
            await self._restart_child(child_name)
        elif self.strategy == RestartStrategy.ONE_FOR_ALL:
            await self._restart_all()
        elif self.strategy == RestartStrategy.REST_FOR_ONE:
            await self._restart_dependents(child_name)

    async def _restart_child(self, name: str) -> None:
        """Restart a single child."""
        child = self.children.get(name)
        if not child:
            return

        child.restart_count += 1
        child.last_restart = time.time()

        delay = backoff_with_jitter(child.restart_count - 1)
        log.info(f"Restarting {name} (attempt {child.restart_count}) in {delay:.2f}s")
        await asyncio.sleep(delay)

        child.is_running = True

    async def _restart_all(self) -> None:
        """Restart all children (one_for_all strategy)."""
        for name in self.children:
            await self._restart_child(name)

    async def _restart_dependents(self, failed_name: str) -> None:
        """Restart failed child and all children started after it."""
        found = False
        for name in self.children:
            if name == failed_name:
                found = True
            if found:
                await self._restart_child(name)

    async def _escalate(self, child_name: str, error: Exception) -> None:
        """Escalate when restart limits exceeded."""
        log.error(
            f"Child {child_name} exceeded restart limit ({self.max_restarts} in {self.window_seconds}s). Escalating."
        )
        if self._escalation_handler:
            await self._escalation_handler(child_name, error)

    def get_status(self) -> Dict[str, Any]:
        """Get supervisor status."""
        return {
            "strategy": self.strategy.value,
            "running": self._running,
            "children": {
                name: {
                    "type": child.child_type.value,
                    "running": child.is_running,
                    "restart_count": child.restart_count,
                    "last_restart": child.last_restart,
                }
                for name, child in self.children.items()
            },
        }

    async def stop(self) -> None:
        """Stop supervision tree."""
        self._running = False
        for child in self.children.values():
            child.is_running = False
        log.info("Supervisor stopped")
