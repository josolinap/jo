# Tool Safety Protocol

## Plan Mode

Before complex operations:
1. Call enter_plan_mode
2. Explore and understand the codebase
3. Create a plan
4. Call exit_plan_mode with plan_summary
5. Execute

## Worktree Isolation

For experimental changes:
1. Call enter_worktree
2. Make changes in isolation
3. Test thoroughly
4. Call exit_worktree with action='merge' or 'discard'

## Subagent Tasks

For parallel work:
1. Call task_create with clear objective
2. Continue with other work
3. Call task_check to get results
4. Integrate results

## Pre-commit Checks

Before git operations:
- Run: python -m py_compile [files]
- Run: python -m pytest tests/test_smoke.py -v
- Verify: git status shows only your changes
