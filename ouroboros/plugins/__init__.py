"""
Ouroboros — Plugin System.

Runtime-loadable plugins that extend Jo's capabilities.
Inspired by claw-code's plugin architecture.

Plugins can provide:
- Tools (via get_tools())
- Hooks (via get_hooks())
- Commands (via get_commands())

Plugin lifecycle:
- install: download and register plugin
- enable: activate plugin
- disable: deactivate plugin without removing
- uninstall: remove plugin completely
- reload: hot-reload plugin code
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import logging
import pathlib
import shutil
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

log = logging.getLogger(__name__)


class PluginStatus(Enum):
    INSTALLED = "installed"
    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"


@dataclass
class PluginInfo:
    name: str
    version: str
    description: str
    author: str
    status: PluginStatus
    path: str
    tools: List[str] = field(default_factory=list)
    hooks: List[str] = field(default_factory=list)
    commands: List[str] = field(default_factory=list)
    installed_at: str = ""
    enabled_at: str = ""
    error: Optional[str] = None


class PluginManager:
    """Manages runtime-loadable plugins."""

    def __init__(self, plugins_dir: pathlib.Path):
        self.plugins_dir = plugins_dir
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        self._registry: Dict[str, PluginInfo] = {}
        self._loaded_modules: Dict[str, Any] = {}
        self._load_manifest()

    def _manifest_path(self) -> pathlib.Path:
        return self.plugins_dir / "manifest.json"

    def _load_manifest(self) -> None:
        manifest_path = self._manifest_path()
        if manifest_path.exists():
            try:
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
                for name, info in data.items():
                    self._registry[name] = PluginInfo(
                        name=info["name"],
                        version=info.get("version", "0.0.0"),
                        description=info.get("description", ""),
                        author=info.get("author", ""),
                        status=PluginStatus(info.get("status", "installed")),
                        path=info.get("path", ""),
                        tools=info.get("tools", []),
                        hooks=info.get("hooks", []),
                        commands=info.get("commands", []),
                        installed_at=info.get("installed_at", ""),
                        enabled_at=info.get("enabled_at", ""),
                    )
            except Exception as e:
                log.warning("Failed to load plugin manifest: %s", e)

    def _save_manifest(self) -> None:
        data = {}
        for name, info in self._registry.items():
            data[name] = {
                "name": info.name,
                "version": info.version,
                "description": info.description,
                "author": info.author,
                "status": info.status.value,
                "path": info.path,
                "tools": info.tools,
                "hooks": info.hooks,
                "commands": info.commands,
                "installed_at": info.installed_at,
                "enabled_at": info.enabled_at,
            }
        self._manifest_path().write_text(json.dumps(data, indent=2), encoding="utf-8")

    def install(
        self, name: str, source_path: pathlib.Path, version: str = "0.0.0", description: str = "", author: str = ""
    ) -> str:
        if name in self._registry:
            return f"Plugin '{name}' already installed"

        plugin_dir = self.plugins_dir / name
        plugin_dir.mkdir(parents=True, exist_ok=True)

        if source_path.is_file():
            shutil.copy2(source_path, plugin_dir / "__init__.py")
        elif source_path.is_dir():
            for item in source_path.iterdir():
                if item.is_file():
                    shutil.copy2(item, plugin_dir / item.name)

        info = PluginInfo(
            name=name,
            version=version,
            description=description,
            author=author,
            status=PluginStatus.INSTALLED,
            path=str(plugin_dir),
            installed_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
        )

        discovered = self._discover_plugin(plugin_dir)
        info.tools = discovered.get("tools", [])
        info.hooks = discovered.get("hooks", [])
        info.commands = discovered.get("commands", [])

        self._registry[name] = info
        self._save_manifest()
        return f"Installed plugin '{name}' v{version} ({len(info.tools)} tools, {len(info.hooks)} hooks)"

    def uninstall(self, name: str) -> str:
        if name not in self._registry:
            return f"Plugin '{name}' not found"

        self.disable(name)
        plugin_dir = self.plugins_dir / name
        if plugin_dir.exists():
            shutil.rmtree(plugin_dir)

        del self._registry[name]
        self._save_manifest()
        return f"Uninstalled plugin '{name}'"

    def enable(self, name: str) -> str:
        if name not in self._registry:
            return f"Plugin '{name}' not found"

        info = self._registry[name]
        if info.status == PluginStatus.ENABLED:
            return f"Plugin '{name}' already enabled"

        try:
            plugin_dir = pathlib.Path(info.path)
            module = self._load_plugin_module(name, plugin_dir)
            if module:
                self._loaded_modules[name] = module
                info.status = PluginStatus.ENABLED
                info.enabled_at = time.strftime("%Y-%m-%dT%H:%M:%S")
                info.error = None
                self._save_manifest()
                return f"Enabled plugin '{name}'"
            else:
                info.status = PluginStatus.ERROR
                info.error = "Failed to load module"
                self._save_manifest()
                return f"Failed to enable plugin '{name}': module load failed"
        except Exception as e:
            info.status = PluginStatus.ERROR
            info.error = str(e)
            self._save_manifest()
            return f"Failed to enable plugin '{name}': {e}"

    def disable(self, name: str) -> str:
        if name not in self._registry:
            return f"Plugin '{name}' not found"

        info = self._registry[name]
        if info.status != PluginStatus.ENABLED:
            return f"Plugin '{name}' not enabled"

        self._loaded_modules.pop(name, None)
        info.status = PluginStatus.DISABLED
        self._save_manifest()
        return f"Disabled plugin '{name}'"

    def reload(self, name: str) -> str:
        if name not in self._registry:
            return f"Plugin '{name}' not found"

        info = self._registry[name]
        was_enabled = info.status == PluginStatus.ENABLED

        if was_enabled:
            self.disable(name)

        module_name = f"ouroboros.plugins.{name}"
        if module_name in sys.modules:
            importlib.reload(sys.modules[module_name])

        if was_enabled:
            return self.enable(name)
        return f"Reloaded plugin '{name}' (disabled)"

    def _load_plugin_module(self, name: str, plugin_dir: pathlib.Path):
        init_path = plugin_dir / "__init__.py"
        if not init_path.exists():
            return None

        spec = importlib.util.spec_from_file_location(f"ouroboros.plugins.{name}", init_path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            return module
        return None

    def _discover_plugin(self, plugin_dir: pathlib.Path) -> Dict[str, List[str]]:
        result = {"tools": [], "hooks": [], "commands": []}
        module = self._load_plugin_module(plugin_dir.name, plugin_dir)
        if not module:
            return result

        if hasattr(module, "get_tools"):
            try:
                tools = module.get_tools()
                result["tools"] = [t.name for t in tools] if tools else []
            except Exception:
                pass

        if hasattr(module, "get_hooks"):
            try:
                hooks = module.get_hooks()
                result["hooks"] = [h.name for h in hooks] if hooks else []
            except Exception:
                pass

        return result

    def list_plugins(self) -> str:
        if not self._registry:
            return "No plugins installed."

        lines = [f"## Plugins ({len(self._registry)} installed)"]
        for name, info in self._registry.items():
            status_icon = {
                PluginStatus.ENABLED: "✅",
                PluginStatus.DISABLED: "⏸️",
                PluginStatus.INSTALLED: "📦",
                PluginStatus.ERROR: "❌",
            }[info.status]
            lines.append(f"\n### {status_icon} {name} v{info.version}")
            lines.append(f"- **Status**: {info.status.value}")
            lines.append(f"- **Description**: {info.description or 'N/A'}")
            lines.append(f"- **Tools**: {len(info.tools)} ({', '.join(info.tools[:5])})")
            if info.error:
                lines.append(f"- **Error**: {info.error}")
        return "\n".join(lines)

    def get_enabled_tools(self) -> List[Any]:
        tools = []
        for name, module in self._loaded_modules.items():
            if hasattr(module, "get_tools"):
                try:
                    tools.extend(module.get_tools())
                except Exception as e:
                    log.warning("Failed to get tools from plugin '%s': %s", name, e)
        return tools

    def get_plugin_info(self, name: str) -> Optional[PluginInfo]:
        return self._registry.get(name)


def get_tools():
    from ouroboros.tools.registry import ToolEntry

    _managers: Dict[str, PluginManager] = {}

    def _get_manager(repo_dir: pathlib.Path) -> PluginManager:
        key = str(repo_dir)
        if key not in _managers:
            _managers[key] = PluginManager(repo_dir / "ouroboros" / "plugins")
        return _managers[key]

    def plugin_list(ctx) -> str:
        return _get_manager(ctx.repo_dir).list_plugins()

    def plugin_install(ctx, name: str, source: str, version: str = "0.0.0", description: str = "") -> str:
        source_path = ctx.repo_path(source)
        return _get_manager(ctx.repo_dir).install(name, source_path, version, description)

    def plugin_uninstall(ctx, name: str) -> str:
        return _get_manager(ctx.repo_dir).uninstall(name)

    def plugin_enable(ctx, name: str) -> str:
        return _get_manager(ctx.repo_dir).enable(name)

    def plugin_disable(ctx, name: str) -> str:
        return _get_manager(ctx.repo_dir).disable(name)

    def plugin_reload(ctx, name: str) -> str:
        return _get_manager(ctx.repo_dir).reload(name)

    return [
        ToolEntry(
            "plugin_list",
            {
                "name": "plugin_list",
                "description": "List all installed plugins and their status.",
                "parameters": {"type": "object", "properties": {}},
            },
            plugin_list,
        ),
        ToolEntry(
            "plugin_install",
            {
                "name": "plugin_install",
                "description": "Install a plugin from a local path.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Plugin name"},
                        "source": {"type": "string", "description": "Path to plugin source (file or directory)"},
                        "version": {"type": "string", "default": "0.0.0"},
                        "description": {"type": "string", "default": ""},
                    },
                    "required": ["name", "source"],
                },
            },
            plugin_install,
        ),
        ToolEntry(
            "plugin_uninstall",
            {
                "name": "plugin_uninstall",
                "description": "Uninstall a plugin.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Plugin name"},
                    },
                    "required": ["name"],
                },
            },
            plugin_uninstall,
        ),
        ToolEntry(
            "plugin_enable",
            {
                "name": "plugin_enable",
                "description": "Enable an installed plugin.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Plugin name"},
                    },
                    "required": ["name"],
                },
            },
            plugin_enable,
        ),
        ToolEntry(
            "plugin_disable",
            {
                "name": "plugin_disable",
                "description": "Disable a plugin without uninstalling.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Plugin name"},
                    },
                    "required": ["name"],
                },
            },
            plugin_disable,
        ),
        ToolEntry(
            "plugin_reload",
            {
                "name": "plugin_reload",
                "description": "Hot-reload a plugin's code.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Plugin name"},
                    },
                    "required": ["name"],
                },
            },
            plugin_reload,
        ),
    ]
