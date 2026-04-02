import json
from typing import Any, Dict, List
from ouroboros.tools.registry import ToolEntry

def _handle_enter_plan_mode(ctx: Any, **kwargs: Any) -> str:
    ctx.sandbox_read_only = True
    return (
        "Entered plan mode. The agent is now in restricted 'read-only' mode.\n"
        "Destructive actions like shell commands and file writing will be blocked.\n"
        "Take this opportunity to:\n"
        "1. Thoroughly explore the codebase\n"
        "2. Understand patterns and architecture\n"
        "3. Design an implementation plan\n"
        "4. Call `exit_plan_mode` when you are ready to execute your plan and unlock write capabilities."
    )

def _handle_exit_plan_mode(ctx: Any, plan_summary: str = "", **kwargs: Any) -> str:
    ctx.sandbox_read_only = False
    return (
        f"Exited plan mode. Write tools are now un-blocked.\n"
        f"Plan Summary recorded: {plan_summary}\n"
        f"You may now proceed with modifying code."
    )

def get_tools() -> List[ToolEntry]:
    return [
        ToolEntry(
            name="enter_plan_mode",
            schema={
                "name": "enter_plan_mode",
                "description": "Enter read-only plan mode. Use this before making complex changes to explore safely.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            handler=_handle_enter_plan_mode,
        ),
        ToolEntry(
            name="exit_plan_mode",
            schema={
                "name": "exit_plan_mode",
                "description": "Exit plan mode, unlocking execution and write-tools. Call this after finalizing your plan.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "plan_summary": {
                            "type": "string",
                            "description": "Provide a quick summary of the proposed changes."
                        }
                    },
                    "required": ["plan_summary"]
                }
            },
            handler=_handle_exit_plan_mode,
        ),
    ]
