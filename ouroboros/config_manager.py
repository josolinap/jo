"""
Configuration Manager - Hot-reloadable configuration system.

Provides centralized configuration with:
- YAML-based config files (default.yaml, overrides.yaml)
- Runtime reloading without restart
- Schema validation
- Watcher pattern for components to react to changes
"""

from __future__ import annotations

import json
import logging
import pathlib
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import yaml

log = logging.getLogger(__name__)


@dataclass
class ConfigSchema:
    """JSON Schema for configuration validation."""
    version: str = "1.0"
    llm: Dict[str, Any] = field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "default_model": {"type": "string"},
            "temperature": {"type": "number", "minimum": 0, "maximum": 2},
            "max_tokens": {"type": "integer", "minimum": 1},
            "reasoning_effort": {"type": "string", "enum": ["low", "medium", "high", "xhigh"]}
        }
    })
    workers: Dict[str, Any] = field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "max_workers": {"type": "integer", "minimum": 1, "maximum": 50},
            "soft_timeout_sec": {"type": "integer", "minimum": 30},
            "hard_timeout_sec": {"type": "integer", "minimum": 60},
            "heartbeat_stale_sec": {"type": "integer", "minimum": 10},
            "queue_max_retries": {"type": "integer", "minimum": 0}
        }
    })
    budget: Dict[str, Any] = field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "total_budget_limit": {"type": "number", "minimum": 0},
            "evolution_budget_reserve": {"type": "number", "minimum": 0}
        }
    })
    hot_reload: Dict[str, Any] = field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "check_interval_sec": {"type": "integer", "minimum": 5, "maximum": 300},
            "vault_notification_enabled": {"type": "boolean"}
        }
    })
    evolution: Dict[str, Any] = field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "enabled_by_default": {"type": "boolean"},
            "auto_promote_after_evolutions": {"type": "integer", "minimum": 1}
        }
    })
    tools: Dict[str, Any] = field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "enabled_by_default": {"type": "array", "items": {"type": "string"}},
            "disabled": {"type": "array", "items": {"type": "string"}}
        }
    })
    context: Dict[str, Any] = field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "max_context_size": {"type": "integer", "minimum": 1024},
            "auto_summarize_at_percent": {"type": "integer", "minimum": 10, "maximum": 95}
        }
    })
    logging: Dict[str, Any] = field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "suppress_progress": {"type": "boolean"},
            "log_level": {"type": "string", "enum": ["DEBUG", "INFO", "WARNING", "ERROR"]}
        }
    })


class ConfigurationManager:
    """Singleton manager for hot-reloadable configuration."""

    _instance: Optional[ConfigurationManager] = None
    _lock: threading.RLock = threading.RLock()

    @classmethod
    def get_instance(cls, repo_dir: Optional[pathlib.Path] = None) -> ConfigurationManager:
        """Get singleton instance, optionally initializing with repo_dir."""
        with cls._lock:
            if cls._instance is None:
                if repo_dir is None:
                    raise ValueError("ConfigurationManager not initialized. Provide repo_dir.")
                cls._instance = cls(repo_dir)
            return cls._instance

    def __init__(self, repo_dir: pathlib.Path):
        self.repo_dir = repo_dir
        self.config_dir = repo_dir / "config"
        self._config: Dict[str, Any] = {}
        self._watchers: List[Callable[[Dict[str, Any]], None]] = []
        self._last_modified: Dict[str, float] = {}
        self._lock = threading.RLock()

        # Ensure config directory exists
        self.config_dir.mkdir(parents=True, exist_ok=True)

        # Load initial configuration
        self._load_all()
        self._validate_all()

        log.info("ConfigurationManager initialized with %d config files", len(self._config))

    def get(self, key: str, default: Any = None) -> Any:
        """Get config value using dot notation (e.g., 'workers.max_workers')."""
        with self._lock:
            parts = key.split('.')
            value = self._config
            for part in parts:
                if isinstance(value, dict) and part in value:
                    value = value[part]
                else:
                    return default
            return value

    def get_int(self, key: str, default: int) -> int:
        """Get config value as int."""
        val = self.get(key, default)
        return int(val) if val is not None else default

    def get_float(self, key: str, default: float) -> float:
        """Get config value as float."""
        val = self.get(key, default)
        return float(val) if val is not None else default

    def get_bool(self, key: str, default: bool) -> bool:
        """Get config value as bool."""
        val = self.get(key, default)
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            return val.lower() in ('true', 'yes', '1')
        return bool(val) if val is not None else default

    def get_str(self, key: str, default: str) -> str:
        """Get config value as string."""
        val = self.get(key, default)
        return str(val) if val is not None else default

    def get_list(self, key: str, default: List[str]) -> List[str]:
        """Get config value as list."""
        val = self.get(key, default)
        if isinstance(val, list):
            return val
        return default

    def reload_if_changed(self) -> bool:
        """Check config files for changes and reload if any modified.

        Returns:
            True if configuration was reloaded, False otherwise
        """
        with self._lock:
            changed = False
            config_files = [
                self.config_dir / "default.yaml",
                self.config_dir / "overrides.yaml"
            ]

            for config_file in config_files:
                if config_file.exists():
                    try:
                        mtime = config_file.stat().st_mtime
                        last_mtime = self._last_modified.get(str(config_file), 0)

                        if mtime > last_mtime:
                            log.info("Config file changed: %s", config_file)
                            self._load_file(config_file)
                            self._last_modified[str(config_file)] = mtime
                            changed = True
                    except Exception as e:
                        log.warning("Failed to check/load config file %s: %s", config_file, e)

            if changed:
                self._validate_all()
                self._notify_watchers()
                log.info("Configuration reloaded successfully")

            return changed

    def add_watcher(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Register a callback to be invoked when configuration changes.

        Args:
            callback: Function that receives the new full config dict
        """
        with self._lock:
            if callback not in self._watchers:
                self._watchers.append(callback)

    def remove_watcher(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Remove a previously registered watcher."""
        with self._lock:
            if callback in self._watchers:
                self._watchers.remove(callback)

    def _load_all(self) -> None:
        """Load all configuration files."""
        self._config = {}
        self._load_file(self.config_dir / "default.yaml")
        self._load_file(self.config_dir / "overrides.yaml")

        # Record initial mtimes
        for config_file in [self.config_dir / "default.yaml", self.config_dir / "overrides.yaml"]:
            if config_file.exists():
                self._last_modified[str(config_file)] = config_file.stat().st_mtime

    def _load_file(self, filepath: pathlib.Path) -> None:
        """Load and merge a YAML configuration file."""
        if not filepath.exists():
            return

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                if data and isinstance(data, dict):
                    self._deep_merge(self._config, data)
                    log.debug("Loaded config from %s", filepath)
        except yaml.YAMLError as e:
            log.error("YAML parse error in %s: %s", filepath, e)
        except Exception as e:
            log.error("Failed to load config from %s: %s", filepath, e)

    def _deep_merge(self, target: Dict[str, Any], source: Dict[str, Any]) -> None:
        """Deep merge source dict into target dict."""
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._deep_merge(target[key], value)
            else:
                target[key] = value

    def _validate_all(self) -> None:
        """Validate configuration against schema."""
        # Simple validation - check required sections and types
        # Full JSON Schema validation can be added if needed
        required_sections = ['llm', 'workers', 'budget', 'hot_reload', 'evolution', 'tools', 'context', 'logging']
        for section in required_sections:
            if section not in self._config:
                log.warning("Missing config section: %s, using defaults", section)
                self._config[section] = {}

    def _notify_watchers(self) -> None:
        """Call all registered watchers with new configuration."""
        # Make a copy to avoid mutations during iteration
        config_copy = json.loads(json.dumps(self._config))
        watchers = list(self._watchers)
        for callback in watchers:
            try:
                callback(config_copy)
            except Exception as e:
                log.warning("Config watcher callback failed: %s", e, exc_info=True)

    def _get_schema_dict(self) -> Dict[str, Any]:
        """Convert ConfigSchema to JSON Schema dict."""
        # Return simplified schema for validation
        return {
            "type": "object",
            "properties": {
                "llm": self._schema.llm,
                "workers": self._schema.workers,
                "budget": self._schema.budget,
                "hot_reload": self._schema.hot_reload,
                "evolution": self._schema.evolution,
                "tools": self._schema.tools,
                "context": self._schema.context,
                "logging": self._schema.logging
            }
        }

    def dump_config(self) -> str:
        """Return current configuration as YAML string."""
        return yaml.dump(self._config, default_flow_style=False, sort_keys=False)

    def get_raw(self) -> Dict[str, Any]:
        """Get raw configuration dict (read-only)."""
        with self._lock:
            return json.loads(json.dumps(self._config))


# Default configuration values as fallback
DEFAULT_CONFIG = {
    "llm": {
        "default_model": "anthropic/claude-sonnet-4",
        "temperature": 0.3,
        "max_tokens": 8192,
        "reasoning_effort": "medium"
    },
    "workers": {
        "max_workers": 5,
        "soft_timeout_sec": 600,
        "hard_timeout_sec": 1800,
        "heartbeat_stale_sec": 120,
        "queue_max_retries": 1
    },
    "budget": {
        "total_budget_limit": 50.0,
        "evolution_budget_reserve": 5.0
    },
    "hot_reload": {
        "check_interval_sec": 30,
        "vault_notification_enabled": True
    },
    "evolution": {
        "enabled_by_default": True,
        "auto_promote_after_evolutions": 3
    },
    "tools": {
        "enabled_by_default": ["*"],
        "disabled": []
    },
    "context": {
        "max_context_size": 128000,
        "auto_summarize_at_percent": 70
    },
    "logging": {
        "suppress_progress": True,
        "log_level": "INFO"
    }
}


def get_config_manager() -> ConfigurationManager:
    """Convenience function to get the singleton ConfigurationManager."""
    return ConfigurationManager.get_instance()