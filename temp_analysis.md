# Analysis of ouroboros/loop.py

## Functions Exported:
- _get_pricing() -> Dict[str, Tuple[float, float, float]]
- _estimate_cost(
- _handle_text_response(
- _check_budget_limits(
- _maybe_inject_self_check(
- _setup_dynamic_tools(
- _handle_list_tools(
- _handle_enable_tools(
- _drain_incoming_messages(
- _emit_llm_usage_event(
- _call_llm_with_retry(
- _maybe_build_task_graph(
- run_llm_loop(

## Dependencies:
Based on codebase_impact analysis, loop.py depends on:
- ouroboros.llm
- ouroboros.memory  
- ouroboros.tools.registry
- ouroboros.context
- ouroboros.temporal_learning

## Complexity:
- File size: ~1500 lines
- Functions: 13 functions
- Main function: run_llm_loop (primary entry point)
- Private functions: 12 helper functions prefixed with _
