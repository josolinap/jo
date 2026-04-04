"""DSPy Tools — Expose DSPy capabilities to Jo's tool system.

Registers tools that let Jo use DSPy for:
- Intelligent task classification
- Optimized tool selection
- Output verification
- Self-optimization (compile prompts from examples)
"""

from __future__ import annotations

import json
import logging
import pathlib
from typing import Any, Dict, List

from ouroboros.tools.registry import ToolEntry, ToolContext

log = logging.getLogger(__name__)


def _dspy_classify(ctx: ToolContext, message: str) -> str:
    """Classify a message using DSPy signatures instead of keyword matching.

    Returns structured classification with task_type, intent, complexity.
    """
    from ouroboros.dspy_integration import classify_message, is_enabled

    if not is_enabled():
        return json.dumps(
            {
                "error": "DSPy not available. Requires: pip install dspy + OPENROUTER_API_KEY.",
                "source": "unavailable",
            }
        )

    result = classify_message(message)
    return json.dumps(result, indent=2)


def _dspy_select_tools(ctx: ToolContext, task_type: str, intent: str, available_tools: str = "") -> str:
    """Select optimal tools for a task using DSPy.

    Args:
        task_type: The classified task type
        intent: The core intent description
        available_tools: Comma-separated tool names (uses registry if empty)
    """
    from ouroboros.dspy_integration import select_tools_dspy, is_enabled

    if not is_enabled():
        return json.dumps(
            {
                "error": "DSPy not available. Requires: pip install dspy + OPENROUTER_API_KEY.",
                "source": "unavailable",
            }
        )

    if not available_tools:
        try:
            from ouroboros.tools.registry import ToolRegistry

            registry = ToolRegistry(repo_dir=ctx.repo_dir, drive_root=ctx.drive_root)
            tools = [t["function"]["name"] for t in registry.schemas()]
        except Exception:
            tools = []
    else:
        tools = [t.strip() for t in available_tools.split(",")]

    result = select_tools_dspy(task_type, intent, tools)
    return json.dumps(result, indent=2)


def _dspy_verify(ctx: ToolContext, task: str, output: str) -> str:
    """Verify an output using DSPy's verification signature.

    Checks for correctness, completeness, and hallucination signs.
    """
    from ouroboros.dspy_integration import verify_output_dspy, is_enabled

    if not is_enabled():
        return json.dumps(
            {
                "error": "DSPy not available. Requires: pip install dspy + OPENROUTER_API_KEY.",
                "source": "unavailable",
            }
        )

    result = verify_output_dspy(task, output)
    return json.dumps(result, indent=2)


def _dspy_route(ctx: ToolContext, message: str, context: str = "") -> str:
    """Route a task to optimal execution strategy using DSPy.

    Decides: direct execution, delegate, research first, or clarify.
    """
    from ouroboros.dspy_integration import route_task_dspy, is_enabled

    if not is_enabled():
        return json.dumps(
            {
                "error": "DSPy not available. Requires: pip install dspy + OPENROUTER_API_KEY.",
                "source": "unavailable",
            }
        )

    result = route_task_dspy(message, context)
    return json.dumps(result, indent=2)


def _dspy_optimize(ctx: ToolContext, examples_json: str = "", optimizer: str = "MIPROv2") -> str:
    """Optimize Jo's DSPy modules using example task classifications.

    Provide examples as JSON array: [{"message": "...", "task_type": "...", "intent": "..."}]
    Uses DSPy's MIPROv2 or GEPA optimizer to improve classification accuracy.
    """
    from ouroboros.dspy_integration import (
        optimize_with_examples,
        save_optimized_module,
        _get_classifier,
        configure_dspy,
        is_enabled,
    )

    if not is_enabled():
        return json.dumps(
            {
                "error": "DSPy not available. Requires: pip install dspy + OPENROUTER_API_KEY.",
                "source": "unavailable",
            }
        )

    if not configure_dspy():
        return json.dumps({"error": "DSPy configuration failed. Check OPENROUTER_API_KEY."})

    # Load examples
    if examples_json:
        try:
            examples = json.loads(examples_json)
        except json.JSONDecodeError:
            return json.dumps({"error": "Invalid JSON in examples_json"})
    else:
        # Auto-generate examples from Jo's chat history
        examples = _load_examples_from_history(ctx)

    if not examples:
        return json.dumps({"error": "No examples provided. Pass examples_json or ensure chat history exists."})

    classifier = _get_classifier()
    if classifier is None:
        return json.dumps({"error": "Failed to create DSPy classifier"})

    # Try to load previously optimized module as starting point
    save_path = str(ctx.drive_path("state") / "dspy_optimized_classifier.json")
    try:
        from ouroboros.dspy_integration import load_optimized_module

        classifier = load_optimized_module(classifier, save_path)
    except Exception:
        pass

    # Build metric
    def classify_metric(example, prediction, trace=None):
        expected = getattr(example, "task_type", "")
        predicted = getattr(prediction, "task_type", "")
        return expected.lower().strip() == predicted.lower().strip()

    optimized = optimize_with_examples(
        classifier,
        examples,
        metric_fn=classify_metric,
        optimizer=optimizer,
    )

    # Save optimized module
    save_path = str(ctx.drive_path("state") / "dspy_optimized_classifier.json")
    save_optimized_module(optimized, save_path)

    return json.dumps(
        {
            "status": "optimized",
            "examples_used": len(examples),
            "optimizer": optimizer,
            "saved_to": save_path,
        },
        indent=2,
    )


def _dspy_status(ctx: ToolContext) -> str:
    """Check DSPy integration status and configuration."""
    from ouroboros.dspy_integration import is_enabled, _dspy_configured

    lines = ["## DSPy Integration Status", ""]

    if not is_enabled():
        lines.append("**Status:** Not available")
        lines.append("**Requires:** `pip install dspy` + `OPENROUTER_API_KEY`")
        lines.append("")
        lines.append("DSPy provides:")
        lines.append("- Declarative signatures (replace prompt strings)")
        lines.append("- Optimized tool selection (MIPROv2/GEPA)")
        lines.append("- Output verification")
        lines.append("- Self-optimization from examples")
        return "\n".join(lines)

    lines.append("**Status:** Enabled")
    lines.append(f"**Configured:** {'Yes' if _dspy_configured else 'Pending (will configure on first use)'}")

    # Check for saved optimized modules
    opt_path = ctx.drive_path("state") / "dspy_optimized_classifier.json"
    if opt_path.exists():
        lines.append(f"**Optimized classifier:** Found ({opt_path.stat().st_mtime})")
    else:
        lines.append("**Optimized classifier:** Not yet optimized (using base model)")

    lines.append("")
    lines.append("### Available DSPy Tools")
    lines.append("- `dspy_classify` — Classify message intent via signatures")
    lines.append("- `dspy_select_tools` — AI tool selection")
    lines.append("- `dspy_verify` — Verify output correctness")
    lines.append("- `dspy_route` — Route task to execution strategy")
    lines.append("- `dspy_optimize` — Self-optimize from examples")

    return "\n".join(lines)


def _load_examples_from_history(ctx: ToolContext) -> List[Dict[str, Any]]:
    """Load classification examples from chat history."""
    examples = []
    try:
        log_path = ctx.drive_path("logs") / "chat.jsonl"
        if not log_path.exists():
            return examples

        lines = log_path.read_text(encoding="utf-8").splitlines()[-200:]
        for line in lines:
            if not line.strip():
                continue
            entry = json.loads(line)
            msg = entry.get("text", "")
            if len(msg) < 10 or len(msg) > 500:
                continue

            # Use keyword-based classification as ground truth for optimization
            from ouroboros.tool_router import classify_task

            task_type = classify_task(msg)
            if task_type != "general":
                examples.append(
                    {
                        "message": msg,
                        "task_type": task_type,
                        "intent": msg[:100],
                    }
                )
    except Exception:
        pass

    return examples[:100]  # Cap at 100 examples


def get_tools() -> List[ToolEntry]:
    """Register DSPy tools into Jo's tool system."""
    return [
        ToolEntry(
            name="dspy_classify",
            schema={
                "name": "dspy_classify",
                "description": (
                    "Classify a message using DSPy declarative signatures. "
                    "Returns task_type, intent, complexity, and whether tools are needed. "
                    "More accurate than keyword-based classification."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "message": {
                            "type": "string",
                            "description": "The user message to classify",
                        },
                    },
                    "required": ["message"],
                },
            },
            handler=_dspy_classify,
            timeout_sec=30,
        ),
        ToolEntry(
            name="dspy_select_tools",
            schema={
                "name": "dspy_select_tools",
                "description": (
                    "Select optimal tools for a task using DSPy. "
                    "Uses AI to pick the best 3-5 tools from available options."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task_type": {
                            "type": "string",
                            "description": "The classified task type",
                        },
                        "intent": {
                            "type": "string",
                            "description": "The core intent description",
                        },
                        "available_tools": {
                            "type": "string",
                            "description": "Comma-separated tool names (optional, uses registry if empty)",
                        },
                    },
                    "required": ["task_type", "intent"],
                },
            },
            handler=_dspy_select_tools,
            timeout_sec=30,
        ),
        ToolEntry(
            name="dspy_verify",
            schema={
                "name": "dspy_verify",
                "description": (
                    "Verify an output for correctness using DSPy. "
                    "Checks factual accuracy, code correctness, and hallucination signs."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task": {
                            "type": "string",
                            "description": "The original task description",
                        },
                        "output": {
                            "type": "string",
                            "description": "The output to verify",
                        },
                    },
                    "required": ["task", "output"],
                },
            },
            handler=_dspy_verify,
            timeout_sec=30,
        ),
        ToolEntry(
            name="dspy_route",
            schema={
                "name": "dspy_route",
                "description": (
                    "Route a task to the optimal execution strategy using DSPy. "
                    "Decides: direct, delegate, research, or clarify."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "message": {
                            "type": "string",
                            "description": "The user message to route",
                        },
                        "context": {
                            "type": "string",
                            "description": "Current system state (optional)",
                        },
                    },
                    "required": ["message"],
                },
            },
            handler=_dspy_route,
            timeout_sec=30,
        ),
        ToolEntry(
            name="dspy_optimize",
            schema={
                "name": "dspy_optimize",
                "description": (
                    "Optimize Jo's DSPy modules from examples using MIPROv2 or GEPA. "
                    "Improves classification and tool selection accuracy over time. "
                    "Can auto-generate examples from chat history."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "examples_json": {
                            "type": "string",
                            "description": "JSON array of examples: [{message, task_type, intent}]. Empty = auto from history.",
                        },
                        "optimizer": {
                            "type": "string",
                            "description": "Optimizer to use: MIPROv2 (default), GEPA, or BootstrapFewShot",
                        },
                    },
                },
            },
            handler=_dspy_optimize,
            timeout_sec=120,
        ),
        ToolEntry(
            name="dspy_status",
            schema={
                "name": "dspy_status",
                "description": (
                    "Check DSPy integration status and available capabilities. "
                    "Shows configuration, optimized modules, and available DSPy tools."
                ),
                "parameters": {"type": "object", "properties": {}},
            },
            handler=_dspy_status,
            timeout_sec=10,
        ),
    ]
