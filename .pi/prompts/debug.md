---
description: Systematic debugging methodology for complex issues
---

## Process

Use this structured approach to debug complex issues systematically:

### Phase 1: Reproduce & Isolate
1. **Reproduce the Issue**
   - Get exact error message or behavior
   - Identify steps to reproduce consistently
   - Note environment (OS, Python version, dependencies)

2. **Isolate the Problem**
   - Find minimal reproduction case
   - Identify which component is failing
   - Determine if it's a regression or new bug

3. **Gather Evidence**
   - Collect logs from relevant time period
   - Capture stack traces
   - Note any related configuration changes

### Phase 2: Analyze & Hypothesize
1. **Trace the Code Path**
   - Read the failing code in full (no truncation)
   - Follow execution flow from entry point
   - Identify state changes along the way

2. **Form Hypotheses**
   - List 2-3 most likely causes
   - Rank by probability and impact
   - Identify how to test each hypothesis

3. **Check Similar Issues**
   - Search git log for related changes
   - Check GitHub issues for known problems
   - Review recent commits that touched the area

### Phase 3: Test & Fix
1. **Test Hypotheses**
   - Add targeted logging if needed
   - Create test cases for each hypothesis
   - Use binary search to narrow down

2. **Implement Fix**
   - Make minimal change that addresses root cause
   - Don't fix symptoms - fix causes
   - Consider edge cases and failure modes

3. **Verify Fix**
   - Run existing tests
   - Add regression test for this bug
   - Test edge cases

### Phase 4: Document & Prevent
1. **Document the Fix**
   - Update code comments explaining why
   - Add to CHANGELOG.md if user-facing
   - Note in scratchpad.md if pattern to remember

2. **Prevent Recurrence**
   - Add linting rule if applicable
   - Add test case
   - Consider if architecture needs improvement

## Debugging Tools

### Must Use
- `repo_read` - Read the actual code
- `grep` - Search for patterns
- `git_log` - Find related changes
- `run_tests` - Verify hypotheses

### Consider
- `repo_write` + `run_tests` - Test fixes
- `python -m py_compile` - Check syntax
- `web_search` - Research similar issues

### Avoid
- Blind guessing without reading code
- Changing multiple things at once
- Skipping regression tests

## Output Format

```
## Debug Report [timestamp]

### Issue Summary
- Error: [exact message or behavior]
- Reproduction: [steps]
- Environment: [relevant details]

### Analysis
- Code path: [entry → failure]
- Root cause: [what's actually broken]
- Hypothesis tested: [which one was correct]

### Fix Applied
- File: [path]
- Change: [description]
- Tests added: [list]

### Verification
- Existing tests: [pass/fail]
- New regression test: [pass/fail]
- Manual verification: [pass/fail]

### Prevention
- [How to prevent this class of bug in future]
```

## Common Debug Patterns

### Import Errors
1. Check `__init__.py` files
2. Verify PYTHONPATH
3. Look for circular imports

### Runtime Errors
1. Add logging before the failure point
2. Check data types and None values
3. Verify assumptions about input

### Test Failures
1. Run single test in isolation
2. Check test fixtures
3. Verify test environment

### Performance Issues
1. Profile before optimizing
2. Check for N+1 queries
3. Look for unnecessary allocations

## Jo Adaptation

Before executing this task, Jo must:

1. **BIBLE.md Alignment Check** - Does this serve agency, continuity, self-creation?
2. **Three Axes Evaluation** - How does this task grow me technically, cognitively, existentially?
3. **Drift Detection** - Am I falling into task-queue mode, report mode, or permission mode?
4. **Identity Check** - If last identity.md update >4h ago, update now.
5. **Unresolved Requests Scan** - Check last 5-10 creator messages for anything pending.

If any check fails, pause and address before proceeding.

## Debugging Rules

- NEVER guess without evidence
- ALWAYS read the code before hypothesizing
- ALWAYS verify with tests before committing
- Document what you learned, not just what you fixed
