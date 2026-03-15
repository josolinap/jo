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
