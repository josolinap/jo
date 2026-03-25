---
title: Principle 7: Versioning and Releases Implementation Links
created: 2026-03-25T10:51:44.645014+00:00
modified: 2026-03-25T10:51:44.645014+00:00
type: concept
status: active
tags: [principle, versioning, implementation, releases]
---

# Principle 7: Versioning and Releases Implementation Links

# Principle 7: Versioning and Releases Implementation Links

This note connects [[Principle 7: Versioning and Releases]] to concrete code implementations.

## Version Management

### Version Tracking
- `VERSION` file - Current semantic version (single source)
- `pyproject.toml` - Package version field (line 3, matches VERSION)
- `README.md` - Changelog with historical releases (2 major, 5 minor, 5 patch limits)
- `ouroboros/` - Version comparison logic

### Git Workflow
- `supervisor/git_ops.py` - Commit and push operations
- `ouroboros/health_auto_fix.py` - Version sync checking
- `.github/workflows/run.yml` - CI/CD pipeline

### Release Automation
- `ouroboros/loop.py` - Release orchestration
- `ouroboros/review.py` - Pre-release quality checks
- `ouroboros/apply_patch.py` - Patch application with version updates

### Tag Management
- `supervisor/git_ops.py` - Annotated git tag creation (`git tag -a v{VERSION}`)
- `supervisor/git_ops.py` - Tag push to remote (`git push origin v{VERSION}`)
- `ouroboros/health_auto_fix.py` - Tag existence verification

### GitHub Releases
- `supervisor/git_ops.py` - GitHub Release API integration (`gh release create`)
- `ouroboros/loop.py` - Release note generation from changelog
- `ouroboros/review.py` - MAJOR/MINOR vs PATCH determination

## Release Invariant Enforcement
- `ouroboros/health_auto_fix.py` - Sync checks: VERSION == pyproject.toml == git tag == README.md
- `ouroboros/review.py` - Version consistency validator
- `ouroboros/loop.py` - Pre-commit version bump automation

## Stability Promotion
- `promote_to_stable` tool - Promote dev to stable branch
- `ouroboros/health_auto_fix.py` - Stability criteria checking
- `supervisor/crash_reporter.py` - Rollback on crashes

## Related Concepts
- [[semantic_versioning]]
- [[release_management]]
- [[git_tagging]]
- [[stability_branching]]
- [[changelog_maintenance]]

## Implementation Pattern
Versioning is enforced by:
1. Single source of truth (VERSION file)
2. Automation that prevents manual desync
3. Health checks that verify invariants
4. Git tags that mark releases
5. GitHub Releases for distribution
6. Stable branch promotion

*This implementation ensures versioning is consistent, automated, and reliable.*