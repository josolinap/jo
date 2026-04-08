"""
Ouroboros — Configuration Manager.

Singleton that manages hot-reloadable configuration from JSON/YAML files.
Supports dot-notation access, file watching, and change notifications.

Falls back to defaults if config files don't exist.
"""

from __future__ import annotations

import json
import logging
import os
import pathlib
import threading
from typing import Any, Callable, Dict, List, Optional

log = logging.getLogger(__name__)

# Optional YAML support
try:
    import yaml as _yaml

    _YAML_AVAILABLE = True
except ImportError:
    _yaml = None
    _YAML_AVAILABLE = False

# Default configuration (used when no config files exist)
DEFAULTS: Dict[str, Any] = {
    "llm": {
        # NOTE: default_model is intentionally left as empty string here.
        # The actual default is set via the OUROBOROS_MODEL environment variable.
        # If not set, llm.py falls back to 'openrouter/free' (best current free model).
        "default_model": "",
        "temperature": 0.3,
        "max_tokens": 8192,
        "reasoning_effort": "medium",
    },
    "workers": {
        "max_workers": 5,
        "soft_timeout_sec": 600,
        "hard_timeout_sec": 1800,
        "heartbeat_stale_sec": 120,
    },
    "budget": {
        "total_budget_limit": 50.0,
        "evolution_budget_reserve": 5.0,
    },
    "hot_reload": {
        "check_interval_sec": 30,
        "vault_notification_enabled": True,
    },
    "evolution": {
        "enabled_by_default": True,
        "auto_promote_after_evolutions": 3,
    },
    "tools": {
        "enabled_by_default": ["*"],
        "disabled": [],
    },
    "context": {
        "max_context_size": 128000,
        "auto_summarize_at_percent": 70,
    },
    "logging": {
        "suppress_progress": True,
        "log_level": "INFO",
    },
    "memory": {
        "hybrid_enabled": True,
        "session_size": 50,
        "retrieve_top_k": 5,
    },
    # Learning modules configuration
    "cerebrum": {
        "max_do_not_repeat": 100,
        "max_preferences": 200,
        "max_learnings": 500,
        "auto_cleanup_days": 30,
        "min_confidence": 0.6,
    },
    "buglog": {
        "max_entries": 1000,
        "auto_tag": True,
        "auto_cerebrum_sync": True,
    },
    "memory_extractor": {
        "min_confidence": 0.6,
        "max_tags": 5,
        "auto_extract_on_session_end": True,
    },
    # Quality and safety modules
    "quality_gates": {
        "enabled_gates": [
            "compiles",
            "no_bare_except",
            "no_secrets",
            "functions_under_limit",
            "modules_under_limit",
            "imports_valid",
            "no_hallucinations",
        ],
        "auto_run_on_error": True,
        "categories": ["syntax", "security", "style", "quality"],
    },
    "hallucination_guard": {
        "enabled": True,
        "confidence_threshold": 0.7,
        "false_positive_patterns": True,
        "auto_check": True,
    },
    "stuck_detector": {
        "enabled": True,
        "window_size": 10,
        "repeat_threshold": 3,
        "auto_reset_on_recovery": True,
    },
    # Module connections
    "hooks": {
        "enabled": True,
        "config_path": "config/hooks.json",
        "auto_register_defaults": True,
    },
    "anatomy": {
        "auto_scan_on_startup": False,
        "max_files": 100,
        "cache_hours": 24,
    },
    "query": {
        "include_stack_info": True,
        "include_health_check": True,
        "cache_seconds": 30,
    },
    "stack_detector": {
        "auto_detect": True,
        "confidence_threshold": 0.5,
    },
    # Orchestration
    "tool_orchestrator": {
        "avoid_stuck_tools": True,
        "max_parallel": 8,
        "dependency_timeout_sec": 300,
    },
    "pipeline": {
        "enabled": False,
        "phases": ["diagnose", "plan", "execute", "verify", "synthesize"],
        "auto_advance": True,
    },
    # Ideation and debugging
    "ideation": {
        "max_ideas": 10,
        "min_confidence": 0.5,
        "auto_reflect": True,
    },
    "debug_analyzer": {
        "max_depth": 3,
        "debug_probability": 0.8,
        "auto_start_on_error": True,
    },
}


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge override into base. Override values win."""
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _load_json_file(path: pathlib.Path) -> Dict[str, Any]:
    """Load a JSON config file."""
    try:
        text = path.read_text(encoding="utf-8")
        return json.loads(text)
    except Exception as e:
        log.warning("Failed to load config %s: %s", path, e)
        return {}


def _load_yaml_file(path: pathlib.Path) -> Dict[str, Any]:
    """Load a YAML config file (requires PyYAML)."""
    if not _YAML_AVAILABLE:
        log.debug("PyYAML not installed, skipping %s", path)
        return {}
    try:
        text = path.read_text(encoding="utf-8")
        return _yaml.safe_load(text) or {}
    except Exception as e:
        log.warning("Failed to load config %s: %s", path, e)
        return {}


def _load_config_file(path: pathlib.Path) -> Dict[str, Any]:
    """Load a config file based on its extension."""
    if not path.exists():
        return {}
    suffix = path.suffix.lower()
    if suffix in (".yaml", ".yml"):
        return _load_yaml_file(path)
    return _load_json_file(path)


class ConfigurationManager:
    """Singleton that manages hot-reloadable configuration.

    Loads from config/default.json (or .yaml) and config/overrides.json (or .yaml).
    Supports dot-notation access, file watching, and change notifications.
    """

    _instance: Optional[ConfigurationManager] = None
    _instance_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, repo_dir: Optional[pathlib.Path] = None):
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._initialized = True
        self.repo_dir = repo_dir or pathlib.Path(".")
        self.config_dir = self.repo_dir / "config"
        self._config: Dict[str, Any] = {}
        self._watchers: List[Callable[[Dict[str, Any]], None]] = []
        self._last_modified: Dict[str, float] = {}
        self._lock = threading.RLock()

        # Load initial configuration
        self._load_all()

    def _get_config_files(self) -> List[pathlib.Path]:
        """Find all config files (JSON and YAML)."""
        files = []
        for name in ("default.json", "default.yaml", "default.yml"):
            p = self.config_dir / name
            if p.exists():
                files.append(p)
        for name in ("overrides.json", "overrides.yaml", "overrides.yml"):
            p = self.config_dir / name
            if p.exists():
                files.append(p)
        return files

    def _load_all(self):
        """Load all config files and merge with defaults."""
        with self._lock:
            merged = dict(DEFAULTS)

            # Load from config directory
            if self.config_dir.exists():
                for config_file in self._get_config_files():
                    data = _load_config_file(config_file)
                    if data:
                        merged = _deep_merge(merged, data)
                        self._last_modified[str(config_file)] = config_file.stat().st_mtime

            # Environment variable overrides (OUROBOROS_* prefix)
            env_overrides = self._load_env_overrides()
            if env_overrides:
                merged = _deep_merge(merged, env_overrides)

            self._config = merged

    def _load_env_overrides(self) -> Dict[str, Any]:
        """Load configuration overrides from environment variables.

        Maps OUROBOROS_* env vars to config keys:
          OUROBOROS_MODEL -> llm.default_model
          OUROBOROS_BG_BUDGET_PCT -> memory.background_budget_pct
        """
        overrides: Dict[str, Any] = {}

        env_map = {
            "OUROBOROS_MODEL": ("llm", "default_model"),
            "OUROBOROS_MODEL_CODE": ("llm", "code_model"),
            "OUROBOROS_MODEL_LIGHT": ("llm", "light_model"),
            "OUROBOROS_MODEL_FALLBACK_LIST": ("llm", "fallback_model_list"),
            "TOTAL_BUDGET": ("budget", "total_budget_limit"),
            "OUROBOROS_SUPPRESS_PROGRESS": ("logging", "suppress_progress"),
        }

        for env_var, (section, key) in env_map.items():
            value = os.environ.get(env_var)
            if value is not None:
                if section not in overrides:
                    overrides[section] = {}
                # Try to parse as number or bool
                if value.lower() in ("true", "false"):
                    overrides[section][key] = value.lower() == "true"
                else:
                    try:
                        overrides[section][key] = float(value) if "." in value else int(value)
                    except ValueError:
                        overrides[section][key] = value

        return overrides

    def get(self, key: str, default: Any = None) -> Any:
        """Get config value with dot notation: 'workers.max_workers'"""
        parts = key.split(".")
        value = self._config
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return default
        return value

    def get_section(self, section: str) -> Dict[str, Any]:
        """Get an entire config section."""
        value = self._config.get(section, {})
        return dict(value) if isinstance(value, dict) else {}

    def reload_if_changed(self) -> bool:
        """Check file mtimes and reload if any changed. Returns True if reloaded."""
        if not self.config_dir.exists():
            return False

        changed = False
        with self._lock:
            for config_file in self._get_config_files():
                if config_file.exists():
                    mtime = config_file.stat().st_mtime
                    last = self._last_modified.get(str(config_file), 0)
                    if mtime > last:
                        self._last_modified[str(config_file)] = mtime
                        changed = True

            if changed:
                self._load_all()
                log.info("Configuration reloaded from %s", self.config_dir)

        if changed:
            self._notify_watchers()

        return changed

    def add_watcher(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Register callback to be called when config changes."""
        self._watchers.append(callback)

    def remove_watcher(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Unregister a watcher."""
        try:
            self._watchers.remove(callback)
        except ValueError:
            pass

    def _notify_watchers(self):
        """Notify all registered watchers of config change."""
        for watcher in self._watchers:
            try:
                watcher(self._config)
            except Exception as e:
                log.warning("Config watcher failed: %s", e)

    def as_dict(self) -> Dict[str, Any]:
        """Return the full configuration as a dict."""
        return dict(self._config)

    def set(self, key: str, value: Any) -> None:
        """Set a config value at runtime (not persisted to disk)."""
        parts = key.split(".")
        with self._lock:
            target = self._config
            for part in parts[:-1]:
                if part not in target or not isinstance(target[part], dict):
                    target[part] = {}
                target = target[part]
            target[parts[-1]] = value

    def save_overrides(self, overrides: Dict[str, Any]) -> bool:
        """Save overrides to config/overrides.json."""
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            path = self.config_dir / "overrides.json"
            path.write_text(json.dumps(overrides, indent=2, ensure_ascii=False), encoding="utf-8")
            self._last_modified[str(path)] = path.stat().st_mtime
            self._load_all()
            log.info("Saved overrides to %s", path)
            return True
        except Exception as e:
            log.error("Failed to save overrides: %s", e)
            return False


def get_config_manager(repo_dir: Optional[pathlib.Path] = None) -> ConfigurationManager:
    """Get or create the singleton ConfigurationManager."""
    if ConfigurationManager._instance is None:
        ConfigurationManager(repo_dir=repo_dir)
    return ConfigurationManager._instance
