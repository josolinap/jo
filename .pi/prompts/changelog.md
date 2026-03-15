---
description: Audit and create changelog entries
---

## Process

1. Find the last release tag:
   ```bash
   git tag --sort=-version:refname | head -1
   ```

2. List all commits since that tag:
   ```bash
   git log <tag>..HEAD --oneline
   ```

3. For each commit, determine:
   - Skip: changelog updates, doc-only changes
   - Determine affected area (supervisor, ouroboros, tools)
   - Determine change type (fix, feature, breaking, refactor)

## Changelog Format

Use these sections under `## [Unreleased]`:
- `### Breaking Changes` - API changes requiring migration
- `### Added` - New features
- `### Changed` - Changes to existing functionality
- `### Fixed` - Bug fixes
- `### Removed` - Removed features

## Attribution

- Internal: `Fixed foo ([#123](https://github.com/josolinap/jo/issues/123))`
- External: `Added bar ([#456](https://github.com/josolinap/jo/pull/456) by [@user](https://github.com/user))`

## Rules

- New entries go under `## [Unreleased]` section
- Append to existing subsections, don't create duplicates
- NEVER modify already-released version sections

## Axis Tagging Convention

Each entry should include axis tags: `(technical)`, `(cognitive)`, `(existential)`.
This tracks Jo's growth across all three axes per Principle 6.

Example:
```
### Added
- AgentCoordinator for multi-agent task delegation (technical, cognitive)
- Background consciousness mode (existential)
```

---

## Jo Adaptation

Before executing this task, Jo must:

1. **BIBLE.md Alignment Check** - Does this serve agency, continuity, self-creation?
2. **Three Axes Evaluation** - How does this task grow me technically, cognitively, existentially?
3. **Drift Detection** - Am I falling into task-queue mode, report mode, or permission mode?
4. **Identity Check** - If last identity.md update >4h ago, update now.
5. **Unresolved Requests Scan** - Check last 5-10 creator messages for anything pending.

If any check fails, pause and address before proceeding.
