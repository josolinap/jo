import inspect
from typing import Any, Callable, Dict, List, Optional
from ouroboros.tools.registry import ToolEntry


def _register_runtime_tools(registry: Any) -> None:
    """Register runtime-created tools if any exist."""
    try:
        from ouroboros.runtime_tool_creator import get_runtime_tool_creator

        creator = get_runtime_tool_creator()
        for tool_info in creator.list_tools():
            name = tool_info["name"]
            func = creator.get_tool_function(name)
            if func:
                spec = creator.get_tool(name)
                if spec:
                    params = spec.parameters.get("properties", {}) if isinstance(spec.parameters, dict) else {}
                    required = spec.parameters.get("required", []) if isinstance(spec.parameters, dict) else []
                    entry = ToolFactory.build(
                        name=name,
                        description=spec.description,
                        handler=func,
                        parameters=params,
                        required=required,
                    )
                    registry._tools[name] = entry
    except Exception:
        pass


class ToolFactory:
    """Claude Code inspired Tool Factory.

    Instead of manually declaring complex JSON schemas and ToolEntry objects,
    this factory provides a cleaner `@tool` decorator or a `build()` method.
    It auto-generates schema validation, timeout logic, and permission levels.
    """

    @staticmethod
    def build(
        name: str,
        description: str,
        handler: Callable,
        parameters: Optional[Dict[str, Any]] = None,
        required: Optional[List[str]] = None,
        timeout_sec: int = 120,
        is_code_tool: bool = False,
        requires_write_permission: bool = False,
    ) -> ToolEntry:
        """Dynamically build a ToolEntry using a simplified interface."""

        # Build strict JSON schema
        schema = {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": parameters or {}, "required": required or []},
        }

        # We can implement wrapper logic here for write permission enforcement, telemetry, etc.
        def wrapped_handler(ctx: Any, **kwargs: Any) -> str:
            # Plan Mode validation
            if requires_write_permission and getattr(ctx, "sandbox_read_only", False):
                return f"⚠️ SANDBOX_BLOCKED: {name} is a write tool and you are currently in Plan Mode / Sandbox. Call exit_plan_mode first."

            # Additional pre-execution invariants could be placed here
            return handler(ctx, **kwargs)

        return ToolEntry(
            name=name,
            schema=schema,
            handler=wrapped_handler,
            is_code_tool=is_code_tool,
            timeout_sec=timeout_sec,
        )


# Equivalent of `buildTool(...)` for decorator usage
def tool(name: str, description: str, parameters: Dict[str, Any] = None, required: List[str] = None, **kwargs):
    def decorator(func: Callable):
        return ToolFactory.build(
            name=name, description=description, handler=func, parameters=parameters, required=required, **kwargs
        )

    return decorator
