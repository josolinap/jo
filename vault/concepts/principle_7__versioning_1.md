---
title: principle_7__versioning
created: 2026-03-28T09:40:56.319411+00:00
modified: 2026-03-28T09:40:56.319411+00:00
type: concept
status: active
---

# principle_7__versioning

# principle_7__versioning

**Principle 7**: Versioning and Releases — Versions are milestones, not counters.

## Full Text from BIBLE.md

Versions are reserved for major milestones only.

- VERSION file in the project root.
- `pyproject.toml` version field must match VERSION.
- MAJOR — Breaking changes to philosophy/architecture or major feature releases.
- MINOR — Reserved for significant capability additions.
- PATCH — Not used for routine changes.

### Version Philosophy

Versions are **milestones**, not counters. A version bump represents:
- A meaningful shift in capability
- A philosophical evolution
- A major architectural change
- A stable release point worth marking

Routine fixes, improvements, and minor features do NOT require version bumps.
The version number should be **stable for extended periods**.

### Release Invariant

Four version sources are **always in sync**:
`VERSION` == `pyproject.toml` version == latest git tag == version in `README.md`.
Discrepancy is a bug that must be fixed immediately.

### Git Tags

- Major releases are accompanied by an **annotated** git tag: `v{VERSION}`.
- Format: `git tag -a v{VERSION} -m "v{VERSION}: description"`.
- Tag is pushed to remote: `git push origin v{VERSION}`.

### GitHub Releases

- MAJOR releases create a GitHub Release (via GitHub API or `gh release create`).
- The release contains a description of significant changes.
- Routine updates do NOT create GitHub Releases.

## Implementation in Jo

Versioning is enforced through:
- **Invariant checking**: Automated synchronization of version sources
- **Semantic versioning**: MAJOR.MINOR.PATCH with clear criteria
- **Release process**: Automated tagging and GitHub release creation
- **Change categorization**: Distinguishing milestone-worthy changes from routine fixes

## Related Links
- [[evolution_cycle]] - Version bumps as evolution milestones
- [[release_process]] - Technical implementation of versioning
- [[principle_1__continuity]] - Version stability as continuity