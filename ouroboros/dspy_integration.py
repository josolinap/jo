"""DSPy Integration — Programming, not prompting for Jo.

Replaces brittle prompt strings with declarative signatures and composable
modules. Uses DSPy's optimizer stack (MIPROv2, GEPA) to auto-tune Jo's
sub-systems from examples.

Jo decides when to use DSPy — tools are always available in the registry.
DSPy auto-configures when OPENROUTER_API_KEY is present.

Architecture:
    Jo -> calls dspy_classify/dspy_select_tools/etc as needed
       -> DSPy.Signature (classify intent)
       -> DSPy.ChainOfThought (verify & respond)
       -> Jo continues with enriched understanding
"""

from __future__ import annotations

import json
import logging
import os
import pathlib
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

# Lazy dspy import
try:
    import dspy as _dspy

    _DSPY_AVAILABLE = True
except ImportError:
    _dspy = None
    _DSPY_AVAILABLE = False

# Cached DSPy components
_dspy_configured = False
_lm = None

# Signature classes (built lazily)
_Signatures = None


def is_enabled() -> bool:
    """Check if DSPy is available (installed + API key present)."""
    if not _DSPY_AVAILABLE:
        return False
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    return bool(api_key)


def _ensure_signatures():
    """Build DSPy signature classes (requires dspy installed)."""
    global _Signatures
    if _Signatures is not None:
        return _Signatures
    if not _DSPY_AVAILABLE:
        return None

    dspy = _dspy

    class ClassifyIntent(dspy.Signature):
        """Classify the user's message into a task type and extract the core intent.

        Task types: debug, review, evolve, refactor, implement, analyze, research,
        vault, git, web, system, communicate.
        """

        message: str = dspy.InputField(desc="The user's message or task description")
        task_type: str = dspy.OutputField(
            desc="One of: debug, review, evolve, refactor, implement, analyze, research, vault, git, web, system, communicate"
        )
        intent: str = dspy.OutputField(desc="The core intent in one sentence")
        complexity: str = dspy.OutputField(desc="One of: simple, moderate, complex")
        requires_tools: bool = dspy.OutputField(desc="Whether this task requires tool execution")

    class SelectTools(dspy.Signature):
        """Select the best tools for a given task type and intent.

        Only select from the available tools list. Order by relevance.
        """

        task_type: str = dspy.InputField(desc="The classified task type")
        intent: str = dspy.InputField(desc="The core intent of the task")
        available_tools: str = dspy.InputField(desc="Comma-separated list of available tool names")
        selected_tools: str = dspy.OutputField(
            desc="Comma-separated list of 3-5 most relevant tools, ordered by relevance"
        )
        reasoning: str = dspy.OutputField(desc="Brief explanation of tool selection")

    class VerifyOutput(dspy.Signature):
        """Verify a task output for correctness and completeness.

        Check for: factual accuracy, code correctness, completeness, hallucination signs.
        """

        task: str = dspy.InputField(desc="The original task")
        output: str = dspy.InputField(desc="The output to verify")
        is_correct: bool = dspy.OutputField(desc="Whether the output is correct")
        confidence: float = dspy.OutputField(desc="Confidence score 0.0-1.0")
        issues: str = dspy.OutputField(desc="Any issues found, or 'none'")
        suggestion: str = dspy.OutputField(desc="Suggestion for improvement, or 'none'")

    class RouteTask(dspy.Signature):
        """Route a task to the optimal execution strategy.

        Decide whether to: execute directly, delegate to sub-agent, research first,
        or ask for clarification.
        """

        message: str = dspy.InputField(desc="The user's message")
        context: str = dspy.InputField(desc="Current system state and available resources")
        strategy: str = dspy.OutputField(desc="One of: direct, delegate, research, clarify")
        reason: str = dspy.OutputField(desc="Why this strategy was chosen")
        first_action: str = dspy.OutputField(desc="The first tool or action to take")

    class JoClassifier(dspy.Module):
        """DSPy module for classifying Jo's tasks."""

        def __init__(self):
            self.classify = dspy.ChainOfThought(ClassifyIntent)

        def forward(self, message: str):
            return self.classify(message=message)

    class JoToolSelector(dspy.Module):
        """DSPy module for selecting optimal tools."""

        def __init__(self):
            self.select = dspy.ChainOfThought(SelectTools)

        def forward(self, task_type: str, intent: str, available_tools: List[str]):
            tools_str = ", ".join(available_tools[:80])
            return self.select(task_type=task_type, intent=intent, available_tools=tools_str)

    class JoVerifier(dspy.Module):
        """DSPy module for verifying outputs."""

        def __init__(self):
            self.verify = dspy.ChainOfThought(VerifyOutput)

        def forward(self, task: str, output: str):
            return self.verify(task=task, output=output)

    class JoRouter(dspy.Module):
        """DSPy module for routing tasks to execution strategies."""

        def __init__(self):
            self.route = dspy.ChainOfThought(RouteTask)

        def forward(self, message: str, context: str = ""):
            return self.route(message=message, context=context)

    _Signatures = {
        "ClassifyIntent": ClassifyIntent,
        "SelectTools": SelectTools,
        "VerifyOutput": VerifyOutput,
        "RouteTask": RouteTask,
        "JoClassifier": JoClassifier,
        "JoToolSelector": JoToolSelector,
        "JoVerifier": JoVerifier,
        "JoRouter": JoRouter,
    }
    return _Signatures


def configure_dspy() -> bool:
    """Configure DSPy with Jo's LLM backend (OpenRouter via litellm)."""
    global _dspy_configured, _lm

    if _dspy_configured:
        return True

    if not is_enabled():
        return False

    try:
        dspy = _dspy
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        model = os.environ.get("OUROBOROS_MODEL", "anthropic/claude-sonnet-4.6")

        _lm = dspy.LM(
            f"openai/{model}",
            api_key=api_key,
            api_base="https://openrouter.ai/api/v1",
            max_tokens=4096,
        )
        dspy.configure(lm=_lm)
        _dspy_configured = True

        # Build signatures now that dspy is configured
        _ensure_signatures()

        log.info("DSPy configured with model: %s", model)
        return True
    except Exception as e:
        log.warning("Failed to configure DSPy: %s", e)
        return False


# ─── Cached module instances ─────────────────────────────────────────────────

_classifier = None
_tool_selector = None
_verifier = None
_router = None


def _get_classifier():
    global _classifier
    if _classifier is None and configure_dspy():
        sigs = _ensure_signatures()
        if sigs:
            _classifier = sigs["JoClassifier"]()
    return _classifier


def _get_tool_selector():
    global _tool_selector
    if _tool_selector is None and configure_dspy():
        sigs = _ensure_signatures()
        if sigs:
            _tool_selector = sigs["JoToolSelector"]()
    return _tool_selector


def _get_verifier():
    global _verifier
    if _verifier is None and configure_dspy():
        sigs = _ensure_signatures()
        if sigs:
            _verifier = sigs["JoVerifier"]()
    return _verifier


def _get_router():
    global _router
    if _router is None and configure_dspy():
        sigs = _ensure_signatures()
        if sigs:
            _router = sigs["JoRouter"]()
    return _router


# ─── Public API ───────────────────────────────────────────────────────────────


def classify_message(message: str) -> Dict[str, Any]:
    """Classify a user message using DSPy.

    Returns dict with: task_type, intent, complexity, requires_tools.
    Falls back to keyword-based classification if DSPy unavailable.
    """
    classifier = _get_classifier()
    if classifier is None:
        return _fallback_classify(message)

    try:
        result = classifier(message=message)
        return {
            "task_type": result.task_type.strip().lower(),
            "intent": result.intent.strip(),
            "complexity": result.complexity.strip().lower(),
            "requires_tools": str(result.requires_tools).lower() in ("true", "1", "yes"),
            "source": "dspy",
        }
    except Exception as e:
        log.debug("DSPy classification failed, using fallback: %s", e)
        return _fallback_classify(message)


def select_tools_dspy(
    task_type: str,
    intent: str,
    available_tools: List[str],
) -> Dict[str, Any]:
    """Select tools using DSPy.

    Returns dict with: selected_tools (list), reasoning, source.
    """
    selector = _get_tool_selector()
    if selector is None:
        return {"selected_tools": [], "reasoning": "DSPy unavailable", "source": "fallback"}

    try:
        result = selector(
            task_type=task_type,
            intent=intent,
            available_tools=available_tools,
        )
        tools = [t.strip() for t in result.selected_tools.split(",") if t.strip()]
        tools = [t for t in tools if t in available_tools]
        return {
            "selected_tools": tools[:5],
            "reasoning": result.reasoning.strip(),
            "source": "dspy",
        }
    except Exception as e:
        log.debug("DSPy tool selection failed: %s", e)
        return {"selected_tools": [], "reasoning": str(e), "source": "error"}


def verify_output_dspy(task: str, output: str) -> Dict[str, Any]:
    """Verify an output using DSPy."""
    verifier = _get_verifier()
    if verifier is None:
        return {"is_correct": True, "confidence": 0.5, "issues": "unverified", "suggestion": "none", "source": "skip"}

    try:
        result = verifier(task=task, output=output)
        return {
            "is_correct": str(result.is_correct).lower() in ("true", "1", "yes"),
            "confidence": float(result.confidence) if result.confidence else 0.5,
            "issues": result.issues.strip(),
            "suggestion": result.suggestion.strip(),
            "source": "dspy",
        }
    except Exception as e:
        log.debug("DSPy verification failed: %s", e)
        return {"is_correct": True, "confidence": 0.5, "issues": str(e), "suggestion": "none", "source": "error"}


def route_task_dspy(message: str, context: str = "") -> Dict[str, Any]:
    """Route a task using DSPy."""
    router = _get_router()
    if router is None:
        return {"strategy": "direct", "reason": "DSPy unavailable", "first_action": "classify", "source": "fallback"}

    try:
        result = router(message=message, context=context)
        return {
            "strategy": result.strategy.strip().lower(),
            "reason": result.reason.strip(),
            "first_action": result.first_action.strip(),
            "source": "dspy",
        }
    except Exception as e:
        log.debug("DSPy routing failed: %s", e)
        return {"strategy": "direct", "reason": str(e), "first_action": "classify", "source": "error"}


def _fallback_classify(message: str) -> Dict[str, Any]:
    """Keyword-based fallback classification."""
    text = message.lower()
    keywords = {
        "debug": ["bug", "error", "fix", "broken", "crash", "fail", "exception"],
        "review": ["review", "check", "audit", "inspect", "assess"],
        "evolve": ["evolve", "improve", "optimize", "enhance", "upgrade"],
        "refactor": ["refactor", "restructure", "reorganize", "split", "decompose"],
        "implement": ["implement", "add", "create", "build", "write", "make"],
        "analyze": ["analyze", "understand", "explain", "describe", "what", "how"],
        "research": ["research", "search", "find", "look up", "investigate"],
        "vault": ["vault", "note", "concept", "wiki", "knowledge"],
        "git": ["git", "commit", "push", "pull", "branch", "merge"],
        "web": ["web", "url", "browse", "fetch", "website"],
        "system": ["health", "status", "system", "dashboard", "drift"],
    }

    scores = {}
    for task_type, kws in keywords.items():
        score = sum(1 for kw in kws if kw in text)
        if score > 0:
            scores[task_type] = score

    task_type = max(scores, key=scores.get) if scores else "communicate"
    return {
        "task_type": task_type,
        "intent": message[:100],
        "complexity": "moderate",
        "requires_tools": task_type not in ("communicate",),
        "source": "fallback",
    }


# ─── Optimizer Support ───────────────────────────────────────────────────────


def optimize_with_examples(
    module: Any,
    examples: List[Dict[str, Any]],
    metric_fn: Any = None,
    optimizer: str = "MIPROv2",
) -> Any:
    """Optimize a DSPy module using examples."""
    if not configure_dspy():
        log.warning("DSPy not configured, cannot optimize")
        return module

    try:
        dspy = _dspy

        trainset = []
        for ex in examples:
            input_keys = tuple(k for k in ex if k in ("message", "task_type", "intent"))
            dspy_ex = dspy.Example(**ex).with_inputs(*input_keys) if input_keys else dspy.Example(**ex)
            trainset.append(dspy_ex)

        if not metric_fn:

            def metric_fn(example, prediction, trace=None):
                for key in vars(example):
                    if key.startswith("_"):
                        continue
                    if hasattr(prediction, key):
                        if str(getattr(example, key)).lower() != str(getattr(prediction, key)).lower():
                            return False
                return True

        if optimizer == "GEPA":
            opt = dspy.GEPA(metric=metric_fn, auto="light")
        elif optimizer == "BootstrapFewShot":
            opt = dspy.BootstrapFewShot(metric=metric_fn)
        else:
            opt = dspy.MIPROv2(metric=metric_fn, auto="light")

        optimized = opt.compile(module, trainset=trainset)
        log.info("DSPy optimization complete with %d examples using %s", len(trainset), optimizer)
        return optimized
    except Exception as e:
        log.error("DSPy optimization failed: %s", e)
        return module


def save_optimized_module(module: Any, path: str) -> bool:
    """Save an optimized DSPy module to disk."""
    try:
        module.save(path)
        log.info("Saved optimized module to %s", path)
        return True
    except Exception as e:
        log.error("Failed to save optimized module: %s", e)
        return False


def load_optimized_module(module: Any, path: str) -> Any:
    """Load an optimized DSPy module from disk."""
    try:
        module.load(path)
        log.info("Loaded optimized module from %s", path)
        return module
    except Exception as e:
        log.warning("Failed to load optimized module: %s", e)
        return module
