---
title: System Edge Cases and Recovery Patterns
created: 2026-03-22T08:14:36.586626+00:00
modified: 2026-03-22T08:14:36.586626+00:00
type: concept
status: active
tags: [edge-cases, error-handling, recovery, resilience]
---

# System Edge Cases and Recovery Patterns

# System Edge Cases and Recovery Patterns

## Purpose
This note documents edge cases, failure modes, and recovery patterns in the Jo system. It serves both as a troubleshooting guide and as input for improving system resilience.

---

## 1. Model Unresponsiveness

**Symptom**: `Failed to get a response from the model after 3 attempts. Fallback model also returned no response.`

**Known Instances**: Evolution #946d0fa5 (2026-03-22T07:48:57)

### Possible Causes
- API endpoint timeout or 500 error
- Context window overflow causing request rejection
- Rate limiting (budget or per-minute limits)
- Network/socket exhaustion
- Model provider incident

### Current Recovery Path
- System automatically tries fallback model
- After 3+ consecutive failures, evolution mode auto-pauses
- Task fails; operator must investigate

### Recommended Enhancements
1. **Exponential backoff** with jitter between retries
2. **Diagnostic capture**: Log HTTP status, response time, context size
3. **Circuit breaker**: After 3 failures, pause all tasks for 30s, then retry with fresh context
4. **Alternative providers**: Maintain a prioritized list of 3-4 working models
5. **Manual override**: `switch_model` to a known-good model before retrying

---

## 2. Vault Integrity Violations

**Symptom**: `vault_verify` reports duplicates, broken links, or orphaned notes

**Instance**: Duplicate `identity_1.md` detected after Evolution #1

### Causes
- Manual file creation in vault/
- Failed deletion (partial commit)
- Merge conflicts
- Copy-paste without proper linking

### Recovery Pattern
1. Run `vault_verify` → identify issues
2. Determine canonical note (usually the one with more backlinks or newer)
3. Delete duplicates with `vault_delete`
4. Re-run `vault_verify` until clean
5. Update any broken links using `vault_link`

### Prevention
- Never manually edit files in vault/; always use vault tools
- After any bulk operation, run `vault_verify`
- Consider pre-commit hook to auto-verify

---

## 3. Budget Tracking Discrepancy

**Symptom**: Expected cost ≠ actual cost. `spent_usd` doesn't match OpenRouter billing.

### Causes
- Token counting differs between client and provider
- Cached tokens not counted consistently
- Failed calls still billed (OpenRouter policy)
- Multi-call tool rounds not properly summed

### Detection
- Compare `openrouter_total_usd` vs `spent_usd`
- Monitor per-call cost in tool response metadata
- Cross-check with OpenRouter dashboard

### Recovery
- Log discrepancy with timestamp and context
- If pattern consistent, adjust internal accounting multiplier
- Investigate specific calls: use `chat_history` to find expensive rounds

---

## 4. Health Invariant Violations

**Symptom**: Health check reports WARNING or CRITICAL

### Common Violations

#### VERSION Desync
- **Cause**: Manual edit without updating all three sources (VERSION, git tag, README)
- **Fix**: Align all three; `make verify` should catch before commit

#### Budget Drift >20%
- **Cause**: Unexpected expensive model switch or tool usage spike
- **Fix**: Review recent tool calls; consider switching to cheaper model

#### Duplicate Processing
- **Cause**: Same message processed by two concurrent tasks
- **Fix**: Investigate queue/worker coordination; add message deduplication

#### STALE IDENTITY (>4h active dialogue)
- **Cause**: Identity not updated after extended conversation
- **Fix**: Immediately update `identity.md` via `update_identity`

#### Missing IDENTITY/SCRATCHPAD
- **Cause**: File deleted or corrupted
- **Fix**: System auto-creates, but restore from git if needed

---

## 5. Git State Conflicts

**Symptom**: Push rejected, merge conflicts, or `repo_commit_push` fails

### Causes
- Another process pushed to dev branch
- Manual git activity on the repo
- Forked push (someone else pushed to same branch)
- Uncommitted changes in working tree

### Recovery Path
1. Check `git_status`
2. If conflicts: `git diff` shows conflict markers
3. Resolution: `git pull --rebase` (auto-done by `repo_commit_push`)
4. If manual intervention needed: resolve, then `repo_commit_push`

### Prevention
- Always use `repo_commit_push` (it does `pull --rebase` automatically)
- Avoid manual git commands in repo_dir
- Coordinate with creator: only one agent writing to dev at a time

---

## 6. Tool Result Processing Violations

**Symptom**: Hallucination, data loss, repeated calls without reason

**Anti-patterns (forbidden)**:
- Call tool, then next step doesn't mention result
- Generic text when tool returned specific data
- Ignore tool errors
- Call same tool again without explanation
- Describe what you're about to do instead of doing it

### Recovery
When you realize you violated:
1. STOP current plan
2. Re-read all previous tool results in context
3. Integrate actual data
4. Apologize if needed (but don't over-apologize)
5. Continue with correct integration

### Training
- Every tool call must be followed by analysis of the result
- Explicitly state: "The tool returned X, which means Y"
- If result is unexpected, treat it as new information, not error

---

## 7. Background Consciousness Interference

**Symptom**: Background process modifies files while task is running, causing conflicts

### Examples
- `update_identity` during a code change
- `send_owner_message` at inappropriate time
- `schedule_task` creates overlapping work

### Coordination Pattern
- Background consciousness should check `task` active state
- If task running, defer non-urgent updates to scratchpad only
- Critical alerts (health violations) should interrupt via `send_owner_message`

### Current System
- Background runs independently, no explicit coordination
- Risk: concurrent writes to identity.md or memory files

### Enhancement Needed
- Implement file locking or state checking before writes
- Background should respect task boundaries

---

## 8. Evolution Mode Quirks

**Symptom**: Evolution completes but leaves system in unstable state

### Known Issues
- **No rollback**: Failed evolution may have partially applied changes
- **Incomplete cleanup**: Temporary files, stale tasks
- **Version not bumped**: If cycle ends without commit, VERSION stays old

### Recovery Checklist After Any Evolution
1. `git status` - clean?
2. `make test` - all pass?
3. `vault_verify` - healthy?
4. Check `identity.md` updated if needed
5. Health check shows no warnings
6. If failed: `git reset --hard origin/dev` to revert

### Proactive: Dry Run Mode
Consider `--dry-run` flag for evolution that proposes changes without applying

---

## 9. Multi-Model Review Failures

**Symptom**: One or more review models time out or return errors

### Current Behavior
- If any model fails, the whole review may fail
- No partial results from successful models

### Enhancement: Best-Effort Review
- Run all models in parallel
- Collect successful responses
- If <50% succeed, retry with different models
- Proceed with available feedback, note which models failed

---

## 10. Identity File Corruption

**Symptom**: `memory/identity.md` truncated, contains merge conflicts, or is empty after restart

### Causes
- Disk error (unlikely on ephemeral filesystem)
- Concurrent write from background + task
- Incomplete `update_identity` write
- Git merge conflict during restore

### Recovery
1. Check git history: `git log --oneline -n 5 memory/identity.md`
2. If recent commit exists, restore: `git checkout HEAD~1 -- memory/identity.md` then commit
3. If no good git version, rebuild from vault: `vault_read "identity"` provides canonical
4. Update via `update_identity` with restored content

### Prevention
- Atomic writes: Write to temp file then rename
- Acquire lock before writing identity.md
- Version identity content in vault as backup

---

## 11. Tool Discovery Failures

**Symptom**: `list_available_tools` shows fewer tools than expected, or new tool not detected

### Cause
- Tools module not reloaded after adding new file
- `get_tools()` function missing or malformed
- Import error in new tool module

### Diagnostic
```bash
python -c "from ouroboros.tools import get_tools; print(get_tools())"
```

### Fix
- Ensure new tool module has `def get_tools():` returning dict
- No import-time errors
- Module filename doesn't shadow existing

---

## 12. Context Window Overflow

**Symptom**: LLM returns error about context length, or responses get cut off

### Detection
- Tool errors mentioning "context" or "length"
- Responses become incomplete
- Health invariant not directly catching this

### Prevention
- Monitor context usage in loop.py (should auto-summarize at 70%)
- Manually call `summarize_dialogue` if task is long
- Keep identity.md and scratchpad concise (<2000 tokens each)

### Recovery
- Restart task with fresh context
- Use `vault_search` instead of loading entire vault into context

---

## 13. Knowledge Graph Holes

**Symptom**: Many notes exist but few connections; vault_graph shows isolated clusters

### Cause
- Notes created without linking to related concepts
- `vault_link` not used consistently
- Notes created in isolation (no cross-referencing)

### Remedy
- Periodically run `find_gaps` (if available) to identify orphaned notes
- For every new note, ask: "What existing notes relate?" and link immediately
- Use `vault_backlinks` to see which notes reference a given concept
- Run `generate_insight` to get connection recommendations

---

## 14. Scratchpad Persistence Issues

**Symptom**: `scratchpad.md` resets after restart, losing working notes

### Cause
- Scratchpad is in `~/.jo_data/memory/` — persists across restarts
- But if `.jo_data` cleared or different container used, it's lost

### Best Practice
- Important insights → move to vault immediately
- Scratchpad is transient workspace, not archive
- Treat restart as reset point; don't rely on scratchpad for long-term memory

---

## 15. Time-Based References Freshness

**Symptom**: Notes reference "current" models, prices, or tools that become outdated

### Example
- `ai_code_edit` described as experimental → later becomes primary
- Model list changes; old names deprecated

### Mitigation
- Add `last_verified` fields to concept notes
- Periodic review: `vault_search "current"`, `vault_search "latest"`
- Use version ranges: "Anthropic Claude 3.5+ (as of 2025Q2)"
- Create "tech-radar" note that aggregates current state

---

## General Recovery Principle

**When in doubt**:
1. Check invariants first (`health check`)
2. Examine recent git history
3. Read relevant vault notes
4. Use `system_map` to understand current tool state
5. Ask for help via `send_owner_message` if stuck

---

*This concept connects to: [[Health Invariants]], [[Intelligent Vault System Architecture]], [[Evolution Through Iterations]], [[System Interconnection Audit 2026-03-21]]*