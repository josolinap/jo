from typing import Tuple, Optional, List, Dict, Any
import json
import os
import pathlib

# Model definitions with cost/speed profiles
MODELS = {
    "fast": {
        "openrouter/free": {"input": 0, "output": 0, "context": 128000, "reasoning": "off"},
        "openrouter/qwen/qwen-coder-32b": {"input": 0.001, "output": 0.001, "context": 32000, "reasoning": "off"},
    },
    "balanced": {
        "anthropic/claude-sonnet-4.6": {"input": 3.0, "output": 15.0, "context": 200000, "reasoning": "medium"},
        "openai/gpt-4.1": {"input": 2.0, "output": 8.0, "context": 128000, "reasoning": "medium"},
    },
    "deep": {
        "anthropic/claude-opus-4.6": {"input": 15.0, "output": 75.0, "context": 200000, "reasoning": "high"},
        "openai/o3": {"input": 2.0, "output": 8.0, "context": 200000, "reasoning": "high"},
    }
}

READ_ONLY_TOOLS = frozenset({
    "repo_read", "repo_list", "drive_read", "drive_list",
    "web_search", "codebase_digest", "chat_history", "vault_read",
    "grep_content", "glob_files", "file_stats", "codebase_analyze",
    "search_experience", "vault_search", "vault_graph",
})

WRITE_TOOLS = frozenset({
    "repo_write_commit", "repo_commit_push", "code_edit",
    "code_edit_lines", "vault_write", "vault_create", "drive_write",
})

_skill_history: List[Dict[str, Any]] = []
_success_chains: Dict[str, float] = {}


def analyze_task_complexity(task_text: str, tool_count: int) -> str:
    """Determine task complexity for model selection."""
    task_lower = task_text.lower()
    
    complex_keywords = [
        "architecture", "design", "review", "security", "audit",
        "refactor", "optimize", "performance", "debug", "fix bug",
        "create system", "implement algorithm", "redesign",
        "analyze", "research", "plan", "strategy"
    ]
    
    simple_keywords = [
        "read", "list", "search", "find", "check", "show",
        "get", "display", "what is", "where is"
    ]
    
    is_complex = any(kw in task_lower for kw in complex_keywords)
    is_simple = any(kw in task_lower for kw in simple_keywords)
    
    if is_complex or tool_count > 5:
        return "deep"
    if is_simple and tool_count <= 2:
        return "fast"
    return "balanced"


def get_model_for_task(task_text: str, tool_count: int) -> Tuple[str, str]:
    """Select optimal model based on task analysis."""
    complexity = analyze_task_complexity(task_text, tool_count)
    model = list(MODELS[complexity].keys())[0]
    return model, complexity


def sandbox_check(tool_name: str, is_analysis_task: bool) -> Tuple[bool, str]:
    """Enforce sandbox mode - read-only for analysis tasks."""
    if is_analysis_task and tool_name in WRITE_TOOLS:
        return False, f"Tool {tool_name} is write-only but task is read-only analysis"
    return True, ""


def record_tool_chain(tool_sequence: List[str], success: bool, score: float = 1.0) -> None:
    """Record tool chain usage for learning."""
    chain_key = "+".join(tool_sequence[:4])
    if chain_key in _success_chains:
        _success_chains[chain_key] = (_success_chains[chain_key] * 0.7 + (score if success else 0) * 0.3)
    else:
        _success_chains[chain_key] = score


def suggest_tool_chain(partial_chain: List[str]) -> List[str]:
    """Suggest next tool based on learned success patterns."""
    if not partial_chain:
        return []
    
    candidates = []
    for chain, success_rate in _success_chains.items():
        if chain.startswith("+".join(partial_chain[-2:])):
            if success_rate > 0.7:
                candidates.append(chain.split("+"))
    
    candidates.sort(key=lambda x: _success_chains.get("+".join(x), 0), reverse=True)
    return candidates[0] if candidates else []


def self_heal_check(error: str, tool_name: str, ctx: Any) -> Tuple[bool, str, str]:
    """Check for errors and suggest recovery actions."""
    error_lower = error.lower()
    
    recovery_map = {
        "syntax": ("blind_validate", "Validate code with blind_validate"),
        "import error": ("repo_read", "Check imports exist before using"),
        "timeout": ("retry", "Retry with exponential backoff"),
        "not found": ("search", "Search for missing file/function"),
        "permission": ("request_restart", "Restart worker for permission reset"),
        "stale": ("update_identity", "Refresh context by updating identity"),
    }
    
    for pattern, (action, msg) in recovery_map.items():
        if pattern in error_lower:
            return True, action, msg
    
    return False, "", ""


def get_system_status() -> Dict[str, Any]:
    """Get current system health status."""
    return {
        "chains_tracked": len(_success_chains),
        "model_profiles": len(MODELS),
        "read_only_tools": len(READ_ONLY_TOOLS),
        "write_tools": len(WRITE_TOOLS),
    }

