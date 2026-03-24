---
title: Hot Reload Configuration Architecture
created: 2026-03-24T09:33:10.724665+00:00
modified: 2026-03-24T09:33:10.724665+00:00
type: concept
status: active
tags: [architecture, hot-reload, configuration]
---

# Hot Reload Configuration Architecture

# Hot Reload Configuration Architecture

## Problem
Current configuration is static and scattered:
- Module-level constants in `supervisor/workers.py` (MAX_WORKERS, timeouts)
- Environment variables (OUROBOROS_SUPPRESS_PROGRESS, etc.)
- State file (budget limits) but no dynamic reloading
- Hardcoded values across modules

Need a unified, dynamically reloadable configuration system.

## Solution

### 1. Configuration File Structure

```
config/
├── default.yaml          # Default values (git-tracked)
├── overrides.yaml        # Environment overrides (git-tracked but changes local)
└── schema.json          # JSON Schema for validation
```

### 2. Configuration Manager Class

```python
# ouroboros/config_manager.py
class ConfigurationManager:
    """Singleton that manages hot-reloadable configuration."""

    def __init__(self, repo_dir: Path):
        self.repo_dir = repo_dir
        self.config_dir = repo_dir / "config"
        self._config: Dict[str, Any] = {}
        self._watchers: List[Callable] = []
        self._last_modified: Dict[str, float] = {}
        self._lock = threading.RLock()

        # Load initial configuration
        self._load_all()
        self._validate_all()

    def get(self, key: str, default: Any = None) -> Any:
        """Get config value with dot notation: 'workers.max_workers'"""
        parts = key.split('.')
        value = self._config
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return default
        return value

    def reload_if_changed(self) -> bool:
        """Check file mtimes and reload if any changed. Returns True if reloaded."""
        changed = False
        for config_file in [self.config_dir / "default.yaml", self.config_dir / "overrides.yaml"]:
            if config_file.exists():
                mtime = config_file.stat().st_mtime
                if self._last_modified.get(str(config_file), 0) < mtime:
                    self._load_file(config_file)
                    self._last_modified[str(config_file)] = mtime
                    changed = True

        if changed:
            self._validate_all()
            self._notify_watchers()

        return changed

    def add_watcher(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Register callback to be called when config changes."""
        self._watchers.append(callback)
```

### 3. Integration with Hot Reload Manager

Modify `HotReloadManager` to watch config files:

```python
# Extend SOFT_RELOAD_DIRS
SOFT_RELOAD_DIRS: Set[str] = {
    "vault/",
    "memory/",
    "docs/",
    "prompts/",
    "README.md",
    "config/",           # ADDED: Watch config directory
    ".github/",
    ".gitignore/",
    ".githooks/",
}

# In HotReloadManager._run(), after processing soft changes:
if "config/" in changed_files:
    # Trigger config reload
    try:
        from ouroboros.config_manager import get_config_manager
        cm = get_config_manager()
        if cm.reload_if_changed():
            notification = "Configuration reloaded"
            if notification and self.on_vault_change:
                self.on_vault_change(notification)
    except Exception as e:
        log.debug(f"Config reload failed: {e}")
```

### 4. Replace Module Constants

In `supervisor/workers.py`:

```python
# OLD:
# MAX_WORKERS: int = 5
# SOFT_TIMEOUT_SEC: int = 600

# NEW:
from ouroboros.config_manager import get_config_manager

_config = get_config_manager()
MAX_WORKERS = _config.get('workers.max_workers', 5)
SOFT_TIMEOUT_SEC = _config.get('workers.soft_timeout_sec', 600)
```

In `ouroboros/llm.py`:

```python
# Use config for defaults
_config = get_config_manager()
DEFAULT_TEMPERATURE = _config.get('llm.temperature', 0.3)
DEFAULT_MAX_TOKENS = _config.get('llm.max_tokens', 8192)
```

### 5. Config Schema

```json
{
  "version": "1.0",
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
    "vault_notification_enabled": true
  },
  "evolution": {
    "enabled_by_default": true,
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
    "suppress_progress": true,
    "log_level": "INFO"
  }
}
```

### 6. Config File Format (YAML)

```yaml
# config/default.yaml
llm:
  default_model: "anthropic/claude-sonnet-4"
  temperature: 0.3
  max_tokens: 8192
  reasoning_effort: "medium"

workers:
  max_workers: 5
  soft_timeout_sec: 600
  hard_timeout_sec: 1800
  heartbeat_stale_sec: 120

budget:
  total_budget_limit: 50.0
  evolution_budget_reserve: 5.0

hot_reload:
  check_interval_sec: 30
  vault_notification_enabled: true

evolution:
  enabled_by_default: true
  auto_promote_after_evolutions: 3
```

### 7. Runtime Config Update Process

1. User edits `config/overrides.yaml` (or any config file)
2. Git detects change, triggers hot-reload detection
3. HotReloadManager classifies as "soft" change (config/ is in SOFT_RELOAD_DIRS)
4. Manager calls config_manager.reload_if_changed()
5. ConfigManager reloads YAML files, merges with defaults
6. ConfigManager validates against schema
7. ConfigManager notifies watchers (registered components)
8. Components update their runtime values (e.g., workers re-read MAX_WORKERS)
9. System continues without restart

### 8. Dynamic Reconfiguration in Components

Components that need dynamic updates should:

```python
class ConfigurableComponent:
    def __init__(self):
        self._config = get_config_manager()
        self._config.add_watcher(self._on_config_changed)

    def _on_config_changed(self, new_config: Dict[str, Any]):
        """React to config changes."""
        # Update internal state
        self.max_workers = self._config.get('workers.max_workers', self.max_workers)
        # ... restart any background threads if needed
```

### 9. Immediate vs Deferred Changes

Some config changes require immediate action, others can wait:

- **Immediate**: logging level, suppress_progress
- **Deferred**: worker counts (applies to new workers only), timeouts (applies to new tasks)

Document which changes require restart vs hot-reload.

## Implementation Plan

1. Create config directory and default.yaml
2. Implement ConfigurationManager with file watching
3. Add JSON Schema validation
4. Integrate with HotReloadManager (add config/ to SOFT_RELOAD_DIRS)
5. Replace hardcoded constants with config lookups
6. Add config watchers to components that need dynamic updates
7. Test: edit config file, verify changes take effect without restart

## Benefits

- No restart needed for most operational parameter changes
- Centralized, version-controlled configuration
- Environment-specific overrides via overrides.yaml
- Schema validation prevents invalid configs
- Extensible: new config options just add to schema and use get()