"""Graceful degradation matrix for tool/dependency failures.

Classifies dependencies by criticality and defines failure responses.
Bulkhead pattern isolates resource pools.

Following Principle 5 (Minimalism): under 200 lines.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

log = logging.getLogger(__name__)


class DependencyClass(Enum):
    """Dependency criticality classification."""

    CRITICAL = "critical"
    IMPORTANT = "important"
    OPTIONAL = "optional"


@dataclass
class DependencyConfig:
    """Configuration for a dependency."""

    name: str
    dependency_class: DependencyClass
    failure_response: str
    max_concurrent: int = 5


@dataclass
class GracefulDegradation:
    """Manages graceful degradation when dependencies fail.

    Classifies dependencies and provides appropriate failure responses:
    - Critical: fail fast, surface error
    - Important: degrade, continue with reduced capability
    - Optional: log and continue

    Usage:
        gd = GracefulDegradation()
        gd.register("llm_api", DependencyClass.CRITICAL, "fail_fast")
        gd.register("web_search", DependencyClass.IMPORTANT, "use_cache")
    """

    dependencies: Dict[str, DependencyConfig] = field(default_factory=dict)
    disabled: Set[str] = field(default_factory=set)
    reasons: Dict[str, str] = field(default_factory=dict)
    semaphores: Dict[str, asyncio.Semaphore] = field(default_factory=dict)

    def register(
        self,
        name: str,
        dep_class: DependencyClass,
        failure_response: str,
        max_concurrent: int = 5,
    ) -> None:
        """Register a dependency with its classification."""
        self.dependencies[name] = DependencyConfig(
            name=name,
            dependency_class=dep_class,
            failure_response=failure_response,
            max_concurrent=max_concurrent,
        )
        self.semaphores[name] = asyncio.Semaphore(max_concurrent)

    def disable(self, name: str, reason: str) -> None:
        """Disable a dependency due to failure."""
        self.disabled.add(name)
        self.reasons[name] = reason
        log.warning(f"Dependency '{name}' disabled: {reason}")

    def enable(self, name: str) -> None:
        """Re-enable a previously disabled dependency."""
        self.disabled.discard(name)
        self.reasons.pop(name, None)
        log.info(f"Dependency '{name}' re-enabled")

    def is_available(self, name: str) -> bool:
        """Check if dependency is available."""
        return name not in self.disabled

    def should_fail_fast(self, name: str) -> bool:
        """Check if failure should cause immediate failure."""
        config = self.dependencies.get(name)
        if config is None:
            return False
        return config.dependency_class == DependencyClass.CRITICAL

    def get_failure_response(self, name: str) -> str:
        """Get the appropriate failure response for a dependency."""
        config = self.dependencies.get(name)
        if config is None:
            return "continue"
        return config.failure_response

    async def execute(self, name: str, fn: Callable, *args: Any, **kwargs: Any) -> Any:
        """Execute function with dependency protection.

        Args:
            name: Dependency name
            fn: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result or degradation response
        """
        if not self.is_available(name):
            config = self.dependencies.get(name)
            if config and config.dependency_class == DependencyClass.CRITICAL:
                raise DependencyUnavailableError(
                    f"Critical dependency '{name}' is unavailable: {self.reasons.get(name)}"
                )
            log.debug(f"Skipping unavailable dependency: {name}")
            return None

        semaphore = self.semaphores.get(name)
        if semaphore:
            async with semaphore:
                try:
                    return await fn(*args, **kwargs) if asyncio.iscoroutinefunction(fn) else fn(*args, **kwargs)
                except Exception as e:
                    self._handle_failure(name, e)
                    raise
        else:
            try:
                return await fn(*args, **kwargs) if asyncio.iscoroutinefunction(fn) else fn(*args, **kwargs)
            except Exception as e:
                self._handle_failure(name, e)
                raise

    def _handle_failure(self, name: str, error: Exception) -> None:
        """Handle dependency failure based on classification."""
        config = self.dependencies.get(name)
        if config is None:
            return

        if config.dependency_class == DependencyClass.CRITICAL:
            self.disable(name, str(error))
        elif config.dependency_class == DependencyClass.IMPORTANT:
            log.warning(f"Important dependency '{name}' failed: {error}")
        else:
            log.debug(f"Optional dependency '{name}' failed: {error}")

    def get_status(self) -> Dict[str, Any]:
        """Get degradation status."""
        return {
            "mode": "degraded" if self.disabled else "full",
            "registered": len(self.dependencies),
            "disabled": list(self.disabled),
            "reasons": dict(self.reasons),
            "by_class": {
                cls.value: sum(1 for d in self.dependencies.values() if d.dependency_class == cls)
                for cls in DependencyClass
            },
        }


class DependencyUnavailableError(Exception):
    """Raised when a critical dependency is unavailable."""

    pass


# Pre-configured degradation matrix for Jo
def create_default_degradation() -> GracefulDegradation:
    """Create default degradation matrix for Jo's dependencies."""
    gd = GracefulDegradation()

    # Critical: must work
    gd.register("llm_api", DependencyClass.CRITICAL, "fail_fast", max_concurrent=5)
    gd.register("git_operations", DependencyClass.CRITICAL, "fail_fast", max_concurrent=3)

    # Important: degrade but continue
    gd.register("vault", DependencyClass.IMPORTANT, "use_memory", max_concurrent=5)
    gd.register("web_search", DependencyClass.IMPORTANT, "use_cache", max_concurrent=3)

    # Optional: skip if unavailable
    gd.register("browser", DependencyClass.OPTIONAL, "skip", max_concurrent=2)
    gd.register("analytics", DependencyClass.OPTIONAL, "skip", max_concurrent=1)

    return gd
