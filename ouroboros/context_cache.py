"""Cache-First Context — Intelligent caching for vault, codebase, and context scans.

Inspired by FACT (Fast Augmented Context Tools):
- Multi-tier caching (memory, disk, distributed)
- Intelligent TTL based on content volatility
- Cache-first: check cache before expensive operations

Replaces the pattern of re-scanning vault/codebase on every tool call.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """A cached result with metadata."""

    key: str
    value: Any
    created_at: float
    ttl_seconds: float
    hit_count: int = 0
    size_bytes: int = 0

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > self.ttl_seconds

    @property
    def age_seconds(self) -> float:
        return time.time() - self.created_at


class ContextCache:
    """Multi-tier cache for context building and tool results.

    Tiers:
        1. Memory (fastest, limited size)
        2. Disk (persistent across tasks)

    TTL strategy (from FACT):
        - Static content (vault structure): long TTL (300s)
        - Semi-dynamic (codebase graph): medium TTL (60s)
        - Dynamic (tool results): short TTL (30s)
        - Per-task (context enrichment): no cache
    """

    # TTL presets (seconds)
    TTL_STATIC = 300
    TTL_SEMI_DYNAMIC = 60
    TTL_DYNAMIC = 30
    TTL_SHORT = 10

    def __init__(
        self,
        max_memory_entries: int = 200,
        disk_cache_dir: Optional[Path] = None,
    ):
        self._memory: Dict[str, CacheEntry] = {}
        self._max_entries = max_memory_entries
        self._disk_dir = disk_cache_dir
        self._stats = {"hits": 0, "misses": 0, "evictions": 0}

    def get(self, key: str) -> Tuple[bool, Any]:
        """Get from cache. Returns (hit, value)."""
        # Check memory
        entry = self._memory.get(key)
        if entry and not entry.is_expired:
            entry.hit_count += 1
            self._stats["hits"] += 1
            return True, entry.value
        elif entry:
            del self._memory[key]

        # Check disk
        if self._disk_dir:
            disk_value = self._read_disk(key)
            if disk_value is not None:
                self._memory[key] = CacheEntry(
                    key=key,
                    value=disk_value,
                    created_at=time.time(),
                    ttl_seconds=self.TTL_STATIC,
                )
                self._stats["hits"] += 1
                return True, disk_value

        self._stats["misses"] += 1
        return False, None

    def set(self, key: str, value: Any, ttl: float = 60) -> None:
        """Store in cache with TTL."""
        entry = CacheEntry(
            key=key,
            value=value,
            created_at=time.time(),
            ttl_seconds=ttl,
            size_bytes=len(json.dumps(value, default=str)) if value else 0,
        )
        self._memory[key] = entry

        if self._disk_dir and ttl >= self.TTL_SEMI_DYNAMIC:
            self._write_disk(key, value)

        self._evict_if_needed()

    def cached(self, key: str, fn: Callable[[], Any], ttl: float = 60) -> Any:
        """Cache-first wrapper: return cached or compute and cache."""
        hit, value = self.get(key)
        if hit:
            return value
        value = fn()
        self.set(key, value, ttl=ttl)
        return value

    def invalidate(self, prefix: Optional[str] = None) -> int:
        """Invalidate entries. If prefix given, only matching keys."""
        if prefix is None:
            count = len(self._memory)
            self._memory.clear()
            return count

        to_remove = [k for k in self._memory if k.startswith(prefix)]
        for k in to_remove:
            del self._memory[k]
        return len(to_remove)

    def get_stats(self) -> Dict[str, Any]:
        total = self._stats["hits"] + self._stats["misses"]
        return {
            **self._stats,
            "entries": len(self._memory),
            "hit_rate": self._stats["hits"] / max(total, 1),
        }

    def _evict_if_needed(self) -> None:
        if len(self._memory) <= self._max_entries:
            return
        # Evict oldest + least-hit entries
        sorted_entries = sorted(
            self._memory.items(),
            key=lambda x: (x[1].hit_count, x[1].created_at),
        )
        to_evict = len(self._memory) - self._max_entries
        for key, _ in sorted_entries[:to_evict]:
            del self._memory[key]
            self._stats["evictions"] += 1

    def _disk_key(self, key: str) -> Path:
        safe = hashlib.sha256(key.encode()).hexdigest()[:16]
        return self._disk_dir / f"{safe}.json"

    def _write_disk(self, key: str, value: Any) -> None:
        try:
            self._disk_dir.mkdir(parents=True, exist_ok=True)
            self._disk_key(key).write_text(json.dumps(value, default=str), encoding="utf-8")
        except Exception:
            log.debug("Unexpected error", exc_info=True)

    def _read_disk(self, key: str) -> Optional[Any]:
        try:
            path = self._disk_key(key)
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            log.debug("Unexpected error", exc_info=True)
        return None


# Global singleton for shared caching across tool calls
_global_cache: Optional[ContextCache] = None


def get_cache(repo_dir: Optional[Path] = None) -> ContextCache:
    """Get or create the global context cache."""
    global _global_cache
    if _global_cache is None:
        disk_dir = repo_dir / ".jo_data" / "cache" if repo_dir else None
        _global_cache = ContextCache(disk_cache_dir=disk_dir)
    return _global_cache


def invalidate_cache(prefix: Optional[str] = None) -> int:
    """Invalidate global cache entries."""
    global _global_cache
    if _global_cache:
        return _global_cache.invalidate(prefix)
    return 0
